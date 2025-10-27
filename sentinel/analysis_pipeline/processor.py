import os
import logging
import cv2
import numpy as np
import json
from django.conf import settings
from .detector import detect_faces
from .embedder import ArcFaceEmbedder
from .vector_db import ChromaDBManager
from .tracker import track_faces_in_video
from .transcriber import eat_video
from .preprocess import canonical_align_and_blob

MEDIA_ROOT = getattr(settings, "MEDIA_ROOT", os.path.join(os.path.dirname(__file__), "..", "media"))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

embedder = ArcFaceEmbedder()
db = ChromaDBManager()


def log_embedding_debug(tag: str, emb):
    if emb is None:
        logger.warning("[%s] embedding is None", tag)
        return
    a = np.asarray(emb, dtype=np.float32).flatten()
    n = float(np.linalg.norm(a))
    prefix = ", ".join(f"{float(x):.6f}" for x in a[:16])
    logger.info("[%s] emb shape=%s dtype=%s norm=%.6f first16=[%s]",
                tag, a.shape, a.dtype, n, prefix)


def expand_box(box, image_shape, margin=0.2):
    h, w = image_shape[:2]
    x1, y1, x2, y2 = box
    bw = x2 - x1
    bh = y2 - y1
    mx = bw * margin
    my = bh * margin
    nx1 = int(max(0, x1 - mx))
    ny1 = int(max(0, y1 - my))
    nx2 = int(min(w, x2 + mx))
    ny2 = int(min(h, y2 + my))
    return nx1, ny1, nx2, ny2


def is_blurry(img, thresh=60):
    if img is None or img.size == 0:
        return True
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return var < thresh


def enroll_person(image_path, person_id, metadata):
    try:
        logger.info(f"[DEBUG] Starting enrollment for {person_id}, image_path={image_path}")
        faces = detect_faces(image_path)
        if len(faces) != 1:
            logger.info(f"[DEBUG] Early exit: faces={faces}")
            logger.error(f"enrollment failed for {image_path}, expected only 1 face, found {len(faces)}")
            return False

        image = cv2.imread(image_path)
        if image is None:
            logger.info("[DEBUG] Early exit: image read failed")
            logger.error(f"unable to read image at {image_path}")
            return False

        face_landmarks = faces[0]['landmarks']

        # produce canonical blob and aligned image
        blob, aligned_rgb = canonical_align_and_blob(image, landmarks=face_landmarks)
        import pathlib

        dbg_dir = pathlib.Path("/tmp/face_debug")
        dbg_dir.mkdir(parents=True, exist_ok=True)

        dbg_path = dbg_dir / f"{person_id}.jpg"
        try:
            # aligned_rgb is RGB; convert to BGR for OpenCV
            img_to_write = cv2.cvtColor(aligned_rgb, cv2.COLOR_RGB2BGR)
            success = cv2.imwrite(str(dbg_path), img_to_write)
            if success:
                logger.info(f"[DEBUG_FILE] Saved aligned face for {person_id} at {dbg_path}")
            else:
                logger.error(f"[DEBUG_FILE] Failed to save aligned face for {person_id}")
        except Exception as e:
            logger.exception(f"[DEBUG_FILE] Exception while saving face debug: {e}")


        log_embedding_debug(f"ENROLL_PREBLOB:{person_id}", blob.shape if blob is not None else None)

        embedding = embedder.get_embedding(blob)
        logger.info(f"[DEBUG] Face crop shape={blob.shape if isinstance(blob, np.ndarray) else 'unknown'}")
        logger.info(
            f"[DEBUG] Embedding norm={np.linalg.norm(embedding):.6f}, "
            f"first10={embedding[:10]}"
        )
        log_embedding_debug(f"ENROLL:{person_id}", embedding)

        if embedding is None:
            logger.error(f"unable to generate embedding for image in {image_path}")
            return False

        db.add_person(person_id=person_id, embedding=embedding, metadata=metadata)
        logger.info(f"enrollment succesfull for person Id : {person_id}")
        return True

    except Exception as e:
        logger.error(f"ERROR : {e}")
        return False


def prepare_face_for_arcface(face_crop):
    if face_crop is None or face_crop.size == 0:
        return None

    # Resize to 112x112
    face_resized = cv2.resize(face_crop, (112, 112))

    # Convert BGR -> RGB once
    face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)

    # Convert to float32
    face_rgb = face_rgb.astype(np.float32)

    # HWC -> CHW (3, 112, 112)
    face_chw = np.transpose(face_rgb, (2, 0, 1))

    # Add batch dim -> (1, 3, 112, 112)
    input_blob = np.expand_dims(face_chw, axis=0).astype(np.float32)

    return input_blob


def process_video(video_path, task_id="preview"):
    import traceback

    logger.info(f"Starting video analysis: {video_path} (task_id={task_id})")

    base_results_dir = os.path.join("media", "results")
    os.makedirs(base_results_dir, exist_ok=True)

    faces_dir = os.path.join(base_results_dir, "faces", task_id)
    os.makedirs(faces_dir, exist_ok=True)

    annotated_video_path = os.path.join(base_results_dir, f"{task_id}_annotated.mp4")
    result_path = os.path.join(base_results_dir, f"{task_id}.json")

    cap = None
    out = None
    fps = 25.0
    persons = {}
    frames_written = 0
    
    # Track identity memory: {track_id: {"identity": person_id, "last_seen": frame_idx, "confidence_history": []}}
    track_memory = {}
    GRACE_PERIOD_FRAMES = 75  # ~2.5 seconds at 30fps
    PROCESS_EVERY_N_FRAMES = 2  # Process every 2nd frame for speed

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap or not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps and video_fps > 0:
            fps = float(video_fps)
        logger.info(f"Video FPS detected: {fps}")

        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        logger.info("Calling track_faces_in_video(...)")
        gen = track_faces_in_video(video_path)

        for yielded in gen:
            frame_idx = None
            frame = None
            tracks = None

            if isinstance(yielded, tuple) and len(yielded) == 2:
                a, b = yielded
                if isinstance(a, (int, np.integer)):
                    frame_idx = int(a)
                    tracks = b
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if not ret:
                        continue
                elif isinstance(a, np.ndarray):
                    frame = a
                    tracks = b
                    frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                else:
                    continue
            elif isinstance(yielded, tuple) and len(yielded) == 3:
                frame_idx, maybe_frame, maybe_tracks = yielded
                if isinstance(maybe_frame, np.ndarray):
                    frame = maybe_frame
                    tracks = maybe_tracks
                else:
                    tracks = maybe_frame
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
                    ret, frame = cap.read()
                    if not ret:
                        continue
            else:
                continue

            if frame is None:
                continue
            if not isinstance(tracks, (list, tuple)):
                tracks = []

            if out is None:
                height, width = frame.shape[:2]
                out = cv2.VideoWriter(annotated_video_path, fourcc, fps, (width, height))

            # Skip frames for speed (still write all frames, just don't process faces every frame)
            process_faces = (frame_idx % PROCESS_EVERY_N_FRAMES == 0)

            for t in tracks:
                if not isinstance(t, dict):
                    continue

                tid = t.get("id") or t.get("track_id") or f"track_{frame_idx}_{tracks.index(t)}"
                box = t.get("box") or t.get("bbox") or t.get("bbox_xyxy")
                if not box or len(box) < 4:
                    continue

                x1, y1, x2, y2 = map(int, box[:4])
                x1, y1 = max(0, x1), max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)
                if x2 <= x1 or y2 <= y1:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop is None or crop.size == 0:
                    continue

                # Use cached identity if not processing this frame
                if not process_faces:
                    if tid in track_memory:
                        label = track_memory[tid]["identity"]
                        meta = track_memory[tid].get("metadata", {"name": label})
                    else:
                        continue
                else:
                    # Detect and align face from crop
                    faces = detect_faces(crop)
                    if not faces:
                        # No face detected, but track exists - use memory if available
                        if tid in track_memory and (frame_idx - track_memory[tid]["last_seen"]) <= GRACE_PERIOD_FRAMES:
                            label = track_memory[tid]["identity"]
                            meta = track_memory[tid].get("metadata", {"name": label})
                        else:
                            continue
                    else:
                        aligned_rgb = faces[0]["aligned_face"]
                        if aligned_rgb is None or aligned_rgb.size == 0:
                            # Face detected but alignment failed - use memory
                            if tid in track_memory and (frame_idx - track_memory[tid]["last_seen"]) <= GRACE_PERIOD_FRAMES:
                                label = track_memory[tid]["identity"]
                                meta = track_memory[tid].get("metadata", {"name": label})
                            else:
                                continue
                        else:
                            emb = embedder.get_embedding(aligned_rgb)
                            
                            if emb is None:
                                # Embedding failed - use memory
                                if tid in track_memory and (frame_idx - track_memory[tid]["last_seen"]) <= GRACE_PERIOD_FRAMES:
                                    label = track_memory[tid]["identity"]
                                    meta = track_memory[tid].get("metadata", {"name": label})
                                else:
                                    continue
                            else:
                                match_id, distance, metadata = db.search_person(emb, k=5, threshold=0.30)

                                if match_id == "NO MATCH FOUND":
                                    # No match - check if we have memory for this track
                                    if tid in track_memory and (frame_idx - track_memory[tid]["last_seen"]) <= GRACE_PERIOD_FRAMES:
                                        label = track_memory[tid]["identity"]
                                        meta = track_memory[tid].get("metadata", {"name": label})
                                    else:
                                        # Grace period expired or new track - mark as unknown
                                        label = f"Unknown_{tid}"
                                        meta = {"name": label}
                                        track_memory[tid] = {"identity": label, "last_seen": frame_idx, "metadata": meta}
                                else:
                                    # Successful match - update memory
                                    label = match_id
                                    meta = metadata or {}
                                    track_memory[tid] = {"identity": label, "last_seen": frame_idx, "metadata": meta}

                # Save face crop and update person records
                if label not in persons:
                    persons[label] = {"metadata": meta, "timestamps": [], "faces": []}
                    crop_filename = f"{label}.jpg"
                    crop_path = os.path.join(faces_dir, crop_filename)
                    if not os.path.exists(crop_path) and crop is not None and crop.size > 0:
                        cv2.imwrite(crop_path, crop)
                        rel = os.path.relpath(crop_path, "media").replace("\\", "/")
                        persons[label]["faces"].append(rel)

                ts_list = persons[label]["timestamps"]
                current_time = round((frame_idx if frame_idx is not None else cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0) / fps, 2)
                merge_gap = 0.5
                if ts_list and current_time <= ts_list[-1]["end"] + merge_gap:
                    ts_list[-1]["end"] = round(max(ts_list[-1]["end"], current_time), 2)
                else:
                    ts_list.append({"start": current_time, "end": current_time})

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, max(0, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            out.write(frame)
            frames_written += 1

        if out:
            out.release()
        cap.release()
        cv2.destroyAllWindows()

        try:
            transcript_data = eat_video(video_path)
            transcript_text = transcript_data.get("text", "")
            transcript_segments = transcript_data.get("segments", [])
        except Exception as e:
            logger.exception("Transcription failed: %s", e)
            transcript_text = ""
            transcript_segments = []

        results = {
            "video_path": os.path.relpath(annotated_video_path, MEDIA_ROOT).replace("\\", "/"),
            "persons": persons,
            "transcript": transcript_text,
            "transcript_segments": transcript_segments
        }

        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)

        logger.info("Video processing done. Results saved to %s", result_path)
        return results

    except Exception as e:
        logger.exception("Error in process_video (task_id=%s): %s", task_id, e)
        error_json = {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
        try:
            with open(result_path, "w", encoding="utf-8") as fh:
                json.dump(error_json, fh, indent=2)
        except Exception:
            logger.exception("Failed to write error JSON to %s", result_path)
        if out:
            try:
                out.release()
            except Exception:
                pass
        if cap:
            try:
                cap.release()
            except Exception:
                pass
        cv2.destroyAllWindows()
        raise
