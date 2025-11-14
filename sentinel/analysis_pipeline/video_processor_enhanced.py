"""
Enhanced video processor that saves:
1. Annotated video with bounding boxes
2. Face crops for each known person
3. Timestamps for each known person
4. Transcription
"""

import os
import cv2
import logging
import numpy as np
from collections import defaultdict
from django.core.files.base import ContentFile
from django.conf import settings

from .detector import detect_faces
from .dual_embedder import DualEmbedder
from .dual_vector_db import DualChromaDBManager
from .transcriber import eat_video

logger = logging.getLogger(__name__)

# Initialize
embedder = DualEmbedder()
db = DualChromaDBManager()

MEDIA_ROOT = getattr(settings, "MEDIA_ROOT", "media")


def process_video_with_db(video_path, task_id, media_file):
    """
    Process video and save all artifacts to database
    """
    from core.models import DetectedPerson, TimestampLog, Transcript
    
    logger.info(f"[{task_id}] Starting enhanced video processing")
    
    # Update progress
    media_file.progress = 5
    media_file.save()
    
    # 1. Transcribe audio
    logger.info(f"[{task_id}] Transcribing audio...")
    transcript_result = eat_video(video_path)
    transcript_text = transcript_result.get("text", "") if isinstance(transcript_result, dict) else str(transcript_result)
    
    # Save transcript
    Transcript.objects.update_or_create(
        media_file=media_file,
        defaults={'full_text': transcript_text}
    )
    
    media_file.progress = 20
    media_file.save()
    
    # 2. Process video frames
    logger.info(f"[{task_id}] Processing video frames...")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Cannot open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Setup annotated video writer
    annotated_dir = os.path.join(MEDIA_ROOT, "results", "annotated", task_id)
    os.makedirs(annotated_dir, exist_ok=True)
    annotated_path = os.path.join(annotated_dir, f"annotated_{os.path.basename(video_path)}")
    
    # Use H.264 codec for browser compatibility
    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264
    out = cv2.VideoWriter(annotated_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        # Fallback to mp4v if H.264 not available
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(annotated_path, fourcc, fps, (width, height))
    
    # Track persons and their appearances
    person_data = defaultdict(lambda: {
        'face_crops': [],
        'timestamps': [],
        'current_start': None,
        'embeddings': {'arcface': None, 'facenet': None}
    })
    
    frame_idx = 0
    process_every_n_frames = max(1, int(fps / 2))  # Process 2 frames per second
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = frame_idx / fps
            
            # Process every N frames
            if frame_idx % process_every_n_frames == 0:
                faces = detect_faces(frame)
                
                detected_in_frame = set()
                
                for face in faces:
                    if 'box' not in face or 'aligned_face' not in face:
                        continue
                    
                    x1, y1, x2, y2 = map(int, face['box'])
                    aligned_rgb = face['aligned_face']
                    
                    if aligned_rgb is None or aligned_rgb.size == 0:
                        continue
                    
                    # Get embeddings
                    arc_emb, fn_emb = embedder.get_dual_embeddings(aligned_rgb)
                    
                    if arc_emb is None or fn_emb is None:
                        continue
                    
                    # Search in database
                    match_id, distance, metadata = db.search_person(
                        arc_emb, fn_emb, k=5, arc_threshold=0.30, fn_threshold=0.30
                    )
                    
                    # Only process KNOWN persons (matched against DB)
                    if match_id != "NO MATCH FOUND":
                        detected_in_frame.add(match_id)
                        
                        # Draw bounding box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, match_id, (x1, y1 - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
                        # Save face crop (limit to 5 per person)
                        if len(person_data[match_id]['face_crops']) < 5:
                            face_crop = frame[y1:y2, x1:x2]
                            if face_crop.size > 0:
                                person_data[match_id]['face_crops'].append(face_crop.copy())
                        
                        # Store embeddings
                        if person_data[match_id]['embeddings']['arcface'] is None:
                            person_data[match_id]['embeddings']['arcface'] = arc_emb
                            person_data[match_id]['embeddings']['facenet'] = fn_emb
                        
                        # Track timestamp
                        if person_data[match_id]['current_start'] is None:
                            person_data[match_id]['current_start'] = current_time
                
                # Close timestamp intervals for persons not in current frame
                for person_id in person_data:
                    if person_id not in detected_in_frame:
                        if person_data[person_id]['current_start'] is not None:
                            person_data[person_id]['timestamps'].append({
                                'start': person_data[person_id]['current_start'],
                                'end': current_time
                            })
                            person_data[person_id]['current_start'] = None
            
            # Write annotated frame
            out.write(frame)
            
            frame_idx += 1
            
            # Update progress (20% to 80%) and check if stopped
            if frame_idx % 100 == 0:
                media_file.refresh_from_db()
                if media_file.status == 'stopped':
                    logger.info(f"[{task_id}] Processing stopped by user")
                    cap.release()
                    out.release()
                    raise Exception("Processing stopped by user")
                
                progress = 20 + int((frame_idx / total_frames) * 60)
                media_file.progress = min(progress, 80)
                media_file.save()
        
        # Close any open timestamp intervals
        final_time = frame_idx / fps
        for person_id in person_data:
            if person_data[person_id]['current_start'] is not None:
                person_data[person_id]['timestamps'].append({
                    'start': person_data[person_id]['current_start'],
                    'end': final_time
                })
    
    finally:
        cap.release()
        out.release()
    
    media_file.progress = 85
    media_file.save()
    
    # 3. Save to database
    logger.info(f"[{task_id}] Saving to database...")
    
    # Save annotated video path
    rel_path = os.path.relpath(annotated_path, MEDIA_ROOT)
    media_file.annotated_video.name = rel_path
    media_file.save()
    
    # Save detected persons
    for person_id, data in person_data.items():
        # Create DetectedPerson
        detected_person = DetectedPerson.objects.create(
            media_file=media_file,
            identity=person_id,
            confidence=0.9  # Average confidence
        )
        
        # Save embeddings
        if data['embeddings']['arcface'] is not None:
            detected_person.arcface_embedding = data['embeddings']['arcface'].tobytes()
            detected_person.facenet_embedding = data['embeddings']['facenet'].tobytes()
        
        # Save face crops
        if data['face_crops']:
            # Save first face crop as thumbnail
            crop = data['face_crops'][0]
            _, buffer = cv2.imencode('.jpg', crop)
            detected_person.face_thumbnail.save(
                f"{person_id}_{task_id}.jpg",
                ContentFile(buffer.tobytes()),
                save=True
            )
        
        # Save timestamps
        for ts in data['timestamps']:
            TimestampLog.objects.create(
                detected_person=detected_person,
                start_time=ts['start'],
                end_time=ts['end']
            )
    
    media_file.progress = 95
    media_file.save()
    
    logger.info(f"[{task_id}] ✅ Processing complete")
    
    # Return results
    results = {
        "status": "ok",
        "video_path": rel_path,
        "transcript": transcript_text,
        "persons": {
            pid: {
                "timestamps": data['timestamps'],
                "face_count": len(data['face_crops'])
            }
            for pid, data in person_data.items()
        }
    }
    
    return results
