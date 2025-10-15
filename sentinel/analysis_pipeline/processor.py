import os

from django.conf import settings
MEDIA_ROOT = getattr(settings, "MEDIA_ROOT", os.path.join(os.path.dirname(__file__), "..", "media"))

from .preprocess import canonical_align_and_blob

import logging, cv2, numpy as np, os
from .detector import detect_faces
from .embedder import ArcFaceEmbedder
from .vector_db import ChromaDBManager
from .tracker import track_faces_in_video
from .transcriber import eat_video
import json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

embedder = ArcFaceEmbedder()

db = ChromaDBManager()

import cv2
import numpy as np


logger = logging.getLogger(__name__)

def log_embedding_debug(tag: str, emb):
    if emb is None:
        logger.warning("[%s] embedding is None", tag)
        return
    a = np.asarray(emb, dtype=np.float32).flatten()
    n = float(np.linalg.norm(a))
    # show first 16 dims for quick visual diff
    prefix = ", ".join(f"{float(x):.6f}" for x in a[:16])
    logger.info("[%s] emb shape=%s dtype=%s norm=%.6f first16=[%s]",
                tag, a.shape, a.dtype, n, prefix)


def expand_box(box, image_shape, margin=0.2):
    """
    box: x1,y1,x2,y2
    margin: fraction to expand each side (0.2 => +20%)
    """
    h, w = image_shape[:2]
    x1,y1,x2,y2 = box
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
    """
    Simple blur detector using variance of Laplacian.
    Lower -> blurrier. Tune threshold. 60 is a starting point.
    """
    if img is None or img.size == 0:
        return True
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return var < thresh

def normalize_image_for_arcface(img):
    """
    Make sure this matches the ArcFace ONNX model preprocessing.
    Typical ArcFace expectation: (112,112,3) RGB, maybe [0,255] or [0,1].
    Check your ONNX author. If your model expects 0~255, don't divide by 255.
    If it expects -1..1 or 0..1, adjust here.
    For safety we return uint8 image (0..255) as embedder currently expects.
    """
    # Convert to RGB
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img


def enroll_person(image_path, person_id, metadata):
    try:
        faces = detect_faces(image_path)
        if len(faces) != 1:
            logger.error(f"enrollment failed for {image_path}, expected only 1 face, found {len(faces)}")
            return False
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"unable to read image at {image_path}")
            return False
        
        face_landmarks = faces[0]['landmarks']
        # produce canonical blob and aligned image
        blob, aligned_rgb = canonical_align_and_blob(image, landmarks=face_landmarks)
        log_embedding_debug(f"ENROLL_PREBLOB:{person_id}", blob.shape if blob is not None else None)

        blob = cv2.cvtColor(blob, cv2.COLOR_BGR2RGB)


        embedding = embedder.get_embedding(blob)

        # embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
        log_embedding_debug(f"ENROLL:{person_id}", embedding)
        if embedding is None:
            logger.error(f"unable to generate embedding for image in {image_path}")
            return False

        db.add_person(
            person_id=person_id,
            embedding=embedding,
            metadata=metadata
        )

        logger.info(f"enrollment succesfull for person Id : {person_id}")
        return True
    except Exception as e:
        logger.error(f"ERROR : {e}")
        return False

def prepare_face_for_arcface(face_crop):
    """
    Convert face crop to correct ArcFace ONNX format: (1, 3, 112, 112)
    """
    import cv2, numpy as np

    if face_crop is None or face_crop.size == 0:
        return None

    # Resize to 112x112
    face_resized = cv2.resize(face_crop, (112, 112))

    # Convert BGR -> RGB
    face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)

    # Normalize to float32
    face_rgb = face_rgb.astype(np.float32)

    # HWC -> CHW (3, 112, 112)
    face_chw = np.transpose(face_rgb, (2, 0, 1))

    # Add batch dim -> (1, 3, 112, 112)
    input_blob = np.expand_dims(face_chw, axis=0).astype(np.float32)

    return input_blob

# def process_video(video_path, task_id="preview"):
#     """
#     Robust video processing wrapper:
#       - Works with track_faces_in_video that yields either (frame_idx, tracks)
#         or (frame, tracks) (or (frame_idx, frame, tracks)).
#       - Writes an annotated mp4 and a results JSON in media/results/
#     """
#     import traceback
#     import numpy as np

#     logger.info(f"Starting video analysis: {video_path} (task_id={task_id})")

#     base_results_dir = os.path.join("media", "results")
#     os.makedirs(base_results_dir, exist_ok=True)

#     faces_dir = os.path.join(base_results_dir, "faces", task_id)
#     os.makedirs(faces_dir, exist_ok=True)

#     annotated_video_path = os.path.join(base_results_dir, f"{task_id}_annotated.mp4")
#     result_path = os.path.join(base_results_dir, f"{task_id}.json")

#     cap = None
#     out = None
#     fps = 25.0
#     persons = {}
#     frames_written = 0

#     try:
#         # Open capture to allow seeking when generator yields frame indices
#         cap = cv2.VideoCapture(video_path)
#         if not cap or not cap.isOpened():
#             raise RuntimeError(f"Could not open video: {video_path}")

#         # get FPS if available
#         video_fps = cap.get(cv2.CAP_PROP_FPS)
#         if video_fps and video_fps > 0:
#             fps = float(video_fps)
#         logger.info(f"Video FPS detected: {fps}")

#         # Video writer will be initialized lazily once we have a real frame
#         fourcc = cv2.VideoWriter_fourcc(*"avc1")  # safe choice for .mp4

#         logger.info("Calling track_faces_in_video(...)")
#         gen = track_faces_in_video(video_path)

#         # iterate robustly over whatever the generator yields
#         for yielded in gen:
#             # normalize into (frame_idx, frame, tracks)
#             frame_idx = None
#             frame = None
#             tracks = None

#             # Case A: generator yields (frame_idx, tracks)
#             if isinstance(yielded, tuple) and len(yielded) == 2:
#                 a, b = yielded
#                 # if first element is int => it's frame index
#                 if isinstance(a, (int, np.integer)):
#                     frame_idx = int(a)
#                     tracks = b
#                     # seek + read the frame at that index
#                     cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
#                     ret, frame = cap.read()
#                     if not ret:
#                         logger.warning(f"Failed to read frame at idx {frame_idx}, skipping")
#                         continue
#                 # if first element is ndarray => generator gives the frame directly
#                 elif isinstance(a, np.ndarray):
#                     frame = a
#                     tracks = b
#                     # attempt to get current read position as index
#                     frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
#                 else:
#                     logger.warning("Unrecognized tuple[0] type from generator: %s", type(a))
#                     continue

#             # Case B: generator yields (frame_idx, frame, tracks)
#             elif isinstance(yielded, tuple) and len(yielded) == 3:
#                 frame_idx, maybe_frame, maybe_tracks = yielded
#                 # try to detect whether maybe_frame is frame or tracks
#                 if isinstance(maybe_frame, np.ndarray):
#                     frame = maybe_frame
#                     tracks = maybe_tracks
#                 else:
#                     # fallback: treat second as tracks and seek using frame_idx
#                     tracks = maybe_frame
#                     cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
#                     ret, frame = cap.read()
#                     if not ret:
#                         logger.warning(f"Failed to read frame at idx {frame_idx} (3-tuple path)")
#                         continue
#             else:
#                 # generator yielded something unexpected (e.g., an int alone)
#                 logger.warning("track_faces_in_video yielded unexpected item: %s", type(yielded))
#                 continue

#             # sanity: ensure we have frame and tracks
#             if frame is None:
#                 logger.warning("No frame obtained for index %s — skipping", frame_idx)
#                 continue
#             if not isinstance(tracks, (list, tuple)):
#                 # allow generator to yield empty track list
#                 tracks = []

#             # initialize VideoWriter lazily when we have first valid frame
#             if out is None:
#                 height, width = frame.shape[:2]
#                 out = cv2.VideoWriter(annotated_video_path, fourcc, fps, (width, height))
#                 logger.info("Initialized VideoWriter: %s (%dx%d @ %.2ffps)", annotated_video_path, width, height, fps)

#             # process each track (t is expected to be a dict-like with 'box' and an id)
#             for t in tracks:
#                 if not isinstance(t, dict):
#                     continue

#                 # accept commonly used keys for id
#                 tid = t.get("id") or t.get("track_id") or f"track_{frame_idx}_{tracks.index(t)}"
#                 # accept commonly used keys for bounding box
#                 box = t.get("box") or t.get("bbox") or t.get("bbox_xyxy")
#                 if not box or len(box) < 4:
#                     continue

#                 # clamp coords
#                 x1, y1, x2, y2 = map(int, box[:4])
#                 x1, y1 = max(0, x1), max(0, y1)
#                 x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
#                 if x2 <= x1 or y2 <= y1:
#                     continue

#                 crop = frame[y1:y2, x1:x2]
#                 if crop is None or crop.size == 0:
#                     continue

#                 # prepare for embedder
#                 input_blob = prepare_face_for_arcface(crop)
#                 if input_blob is None:
#                     continue

#                 emb = embedder.get_embedding(input_blob)
#                 if emb is None:
#                     continue

#                 # Search DB (threshold tuned)
#                 match_id, distance, metadata = db.search_person(emb, k=5, threshold=1.0)
#                 if match_id == "NO MATCH FOUND":
#                     label = f"Unknown_{tid}"
#                     meta = {"name": label}
#                     match_id = label
#                 else:
#                     label = match_id
#                     meta = metadata or {}

#                 # create person entry if new and save ONE representative crop
#                 if label not in persons:
#                     persons[label] = {"metadata": meta, "timestamps": [], "faces": []}
#                     crop_filename = f"{label}.jpg"
#                     crop_path = os.path.join(faces_dir, crop_filename)
#                     if not os.path.exists(crop_path):
#                         cv2.imwrite(crop_path, crop)
#                         # store path relative to media folder (frontend expects this)
#                         rel = os.path.relpath(crop_path, "media").replace("\\", "/")
#                         persons[label]["faces"].append(rel)

#                 # compute times and merge intervals (merge gap: 0.5s)
#                 ts_list = persons[label]["timestamps"]
#                 current_time = round((frame_idx if frame_idx is not None else cap.get(cv2.CAP_PROP_POS_MSEC)/1000.0) / fps, 2)
#                 merge_gap = 0.5
#                 if ts_list and current_time <= ts_list[-1]["end"] + merge_gap:
#                     ts_list[-1]["end"] = round(max(ts_list[-1]["end"], current_time), 2)
#                 else:
#                     ts_list.append({"start": current_time, "end": current_time})

#                 # draw annotations
#                 cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
#                 cv2.putText(frame, label, (x1, max(0, y1 - 10)),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

#             # write annotated frame
#             out.write(frame)
#             frames_written += 1

#             # lightweight heartbeat log every N frames
#             if frames_written % 50 == 0:
#                 logger.info("Processed %d frames (task=%s)", frames_written, task_id)

#         # done iterating generator
#         if out:
#             out.release()
#             logger.info("Released VideoWriter after writing %d frames", frames_written)

#         cap.release()
#         cv2.destroyAllWindows()

#         try:
#             transcript = eat_video(video_path)
#         except Exception as e:
#             logger.exception("Transcription failed, continuing without transcript: %s", e)
#             transcript = ""

#         results = {
#             "video_path": os.path.relpath(annotated_video_path, MEDIA_ROOT).replace("\\", "/"),
#             "persons": persons,
#             "transcript": transcript
#         }

#         with open(result_path, "w", encoding="utf-8") as fh:
#             json.dump(results, fh, indent=2)

#         logger.info("Video processing done. Results saved to %s", result_path)
#         return results

#     except Exception as e:
#         logger.exception("Error in process_video (task_id=%s): %s", task_id, e)
#         # always write an error JSON so frontend stops polling and shows error
#         error_json = {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
#         try:
#             with open(result_path, "w", encoding="utf-8") as fh:
#                 json.dump(error_json, fh, indent=2)
#         except Exception:
#             logger.exception("Failed to write error JSON to %s", result_path)
#         # ensure resources cleaned
#         if out:
#             try:
#                 out.release()
#             except Exception:
#                 pass
#         if cap:
#             try:
#                 cap.release()
#             except Exception:
#                 pass
#         cv2.destroyAllWindows()
#         raise




def process_video(video_path, task_id="preview"):
    """
    Robust video processing wrapper with transcript highlighting support.
    """
    import traceback
    import numpy as np

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

            for t in tracks:
                if not isinstance(t, dict):
                    continue

                tid = t.get("id") or t.get("track_id") or f"track_{frame_idx}_{tracks.index(t)}"
                box = t.get("box") or t.get("bbox") or t.get("bbox_xyxy")
                if not box or len(box) < 4:
                    continue

                x1, y1, x2, y2 = map(int, box[:4])
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                if x2 <= x1 or y2 <= y1:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop is None or crop.size == 0:
                    continue

                
                input_blob = prepare_face_for_arcface(crop)
                if input_blob is None:
                    continue

                emb = embedder.get_embedding(input_blob)
                # if emb is not None:
                #     emb = np.asarray(emb, dtype=np.float32).flatten()
                #     emb /= np.linalg.norm(emb) + 1e-10

                log_embedding_debug(f"QUERY:frame{frame_idx:05d}", emb)
                if emb is None:
                    continue

                match_id, distance, metadata = db.search_person(emb, k=5, threshold=0.55)
                if distance is not None:
                    logger.info(f"[COMPARE] frame={frame_idx} query_emb with best_match={match_id}, distance={distance:.4f}")
                else:
                    logger.info(f"[COMPARE] frame={frame_idx} query_emb with best_match={match_id}, distance=None")

                # logger.info(f"[COMPARE] frame={frame_idx} query_emb with best_match={match_id}, distance={distance:.4f}")
                if match_id == "NO MATCH FOUND":
                    label = f"Unknown_{tid}"
                    meta = {"name": label}
                    match_id = label
                else:
                    label = match_id
                    meta = metadata or {}

                if label not in persons:
                    persons[label] = {"metadata": meta, "timestamps": [], "faces": []}
                    crop_filename = f"{label}.jpg"
                    crop_path = os.path.join(faces_dir, crop_filename)
                    if not os.path.exists(crop_path):
                        cv2.imwrite(crop_path, crop)
                        rel = os.path.relpath(crop_path, "media").replace("\\", "/")
                        persons[label]["faces"].append(rel)

                ts_list = persons[label]["timestamps"]
                current_time = round((frame_idx if frame_idx is not None else cap.get(cv2.CAP_PROP_POS_MSEC)/1000.0) / fps, 2)
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
            try: out.release()
            except Exception: pass
        if cap:
            try: cap.release()
            except Exception: pass
        cv2.destroyAllWindows()
        raise










































# if __name__ == '__main__':
#     # --- Setup ---
#     # Build robust, absolute paths to our test files
#     SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
#     enrollment_image = os.path.join(SCRIPT_DIR, '..', 'test_images', 'test_image_sengo.jpg')
#     test_video_path = os.path.join(SCRIPT_DIR, '..', 'test_images', 'testo_video.mp4')
    
#     # Define the person in our test image
#     person_id = "test_person_01"
#     person_metadata = {'name': 'Mr.sengotaiyan', 'role': 'EX-Minister'}

#     # --- 1. Clear the database for a clean test run ---
#     print("--- Clearing the production_db for a fresh test ---")
#     # Re-initialize the manager to ensure we're using the correct path
#     db_manager = MilvusDBManager(db_path="production_db")
#     all_ids = db_manager.collection.get()['ids']
#     if all_ids:  # only attempt deletion if IDs exist
#         db_manager.collection.delete(ids=all_ids)
#     print(f"Database count is now: {db_manager.collection.count()}")

#     # --- 2. Enroll the known person ---
#     print(f"\n--- Enrolling '{person_metadata['name']}' ---")
#     enroll_success = enroll_person(enrollment_image, person_id, person_metadata)

#     if enroll_success:
#         print(f"\n--- Enrollment successful for {person_id} ---")
#         print(f"Database count is now: {db_manager.collection.count()}")
        
#         # --- 3. Process the video to find the person and get the transcript ---
#         print("\n--- Starting full video analysis ---")
#         results = process_video(test_video_path)

#         # --- 4. Print the final, structured results ---
#         print("\n\n--- ✅ FINAL ANALYSIS RESULTS ---")
#         print("\n--- Identified Persons & Timestamps ---")
#         if results and results['persons']:
#             for person_id, data in results['persons'].items():
#                 print(f"\n  - Person ID: {person_id}")
#                 print(f"    Metadata: {data['metadata']}")
#                 print(f"    Appearances:")
#                 for ts in data['timestamps']:
#                     start = ts.get('start_time', 'N/A')
#                     end = ts.get('end_time', 'N/A')
#                     print(f"      - Start: {start:.2f}s, End: {end:.2f}s")
#         else:
#             print("  No persons were identified in the video.")

#         print("\n--- Full Video Transcript ---")
#         print(f"  '{results.get('transcript', 'No transcript available.')}'")
#     else:
#         print("\n--- ❌ Enrollment failed. Cannot proceed with video processing test. ---")