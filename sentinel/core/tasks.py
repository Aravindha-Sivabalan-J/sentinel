import os
import json
import logging
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# Ensure results directory exists
MEDIA_ROOT = getattr(settings, "MEDIA_ROOT", os.path.join(settings.BASE_DIR, "media"))
RESULTS_DIR = os.path.join(MEDIA_ROOT, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# @shared_task(bind=True, acks_late=False, reject_on_worker_lost=False)
# def process_video_task(self, video_path):
#     """
#     Celery task wrapper around analysis_pipeline.processor.process_video.
#     Ensures results are written to JSON in RESULTS_DIR with task_id in filename.
#     """
#     task_id = self.request.id
#     try:
#         # Run the pipeline with this task_id
#         results = process_video(video_path, task_id=task_id)

#         # Save results to JSON (Celery backend also stores minimal info)
#         result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
#         with open(result_path, "w", encoding="utf-8") as fh:
#             json.dump(results, fh, ensure_ascii=False, indent=2)

#         return {"status": "ok", "result_path": result_path}

#     except Exception as e:
#         # Write error info to JSON so frontend polling can stop gracefully
#         err_obj = {"status": "error", "error": str(e)}
#         result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
#         with open(result_path, "w", encoding="utf-8") as fh:
#             json.dump(err_obj, fh, ensure_ascii=False, indent=2)
#         raise

@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True)
def process_audio_task(self, audio_path, media_file_id=None):
    """
    Process audio file and save transcript to database
    """
    from core.models import MediaFile, Transcript
    from analysis_pipeline.transcriber import eat_video
    
    task_id = self.request.id
    result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
    
    # Get MediaFile record
    if media_file_id:
        try:
            media_file = MediaFile.objects.get(id=media_file_id)
        except MediaFile.DoesNotExist:
            media_file = None
    else:
        media_file = None
    
    if not media_file:
        media_file = MediaFile.objects.create(
            filename=os.path.basename(audio_path),
            video_path=audio_path,
            status='processing',
            task_id=task_id
        )
        media_file_id = media_file.id
    else:
        # CRITICAL CHECK: If already processed and saved, skip entirely
        media_file.refresh_from_db()
        if media_file.status == 'saved':
            logger.info(f"Task {task_id} skipped - audio file already processed and saved")
            # Return existing results if available
            if os.path.exists(result_path):
                with open(result_path, 'r', encoding='utf-8') as f:
                    existing_results = json.load(f)
                return existing_results
            return {"status": "saved", "message": "Audio file already processed and saved", "media_file_id": media_file_id}
        
        if media_file.status == 'stopped':
            logger.info(f"Task {task_id} skipped - file was stopped")
            return {"status": "stopped", "message": "Processing was stopped by user"}
        
        media_file.status = 'processing'
        media_file.task_id = task_id
        media_file.save()
    
    try:
        logger.info(f"Starting audio processing: {audio_path}")
        
        # Update progress
        media_file.progress = 20
        media_file.save()
        
        # Transcribe audio (audio models loaded and unloaded inside eat_video)
        transcript_result = eat_video(audio_path)
        transcript_text = transcript_result.get("text", "") if isinstance(transcript_result, dict) else str(transcript_result)
        transcript_segments = transcript_result.get("segments", []) if isinstance(transcript_result, dict) else []
        
        media_file.progress = 80
        media_file.save()
        
        # Save transcript
        Transcript.objects.update_or_create(
            media_file=media_file,
            defaults={'full_text': transcript_text}
        )
        
        # Update status
        media_file.status = 'processed'
        media_file.progress = 100
        media_file.save()
        
        # Save audio file path to MediaFile
        rel_audio_path = os.path.relpath(audio_path, MEDIA_ROOT)
        media_file.annotated_video.name = rel_audio_path
        media_file.save()
        
        # Save results to JSON
        # Compute fast, approximate sentence-level timestamps from segment timestamps.
        transcript_sentences = []
        try:
            import re

            if transcript_segments and isinstance(transcript_segments, list):
                for seg in transcript_segments:
                    text = seg.get("text", "")
                    start = float(seg.get("start", 0) or 0)
                    end = float(seg.get("end", start) or start)
                    duration = max(0.0, end - start)

                    # Split segment text into sentences (simple rule-based split).
                    # This is approximate but fast: split on sentence end punctuation.
                    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
                    if not sentences:
                        # If no sentence boundaries found, keep full segment as one sentence
                        transcript_sentences.append({"text": text, "start": start, "end": end})
                        continue

                    # Distribute duration across sentences proportionally by word count.
                    word_counts = [len(s.split()) for s in sentences]
                    total_words = sum(word_counts) or 1
                    cursor = start
                    for s_text, wc in zip(sentences, word_counts):
                        frac = float(wc) / float(total_words)
                        s_dur = duration * frac
                        s_start = cursor
                        s_end = cursor + s_dur
                        transcript_sentences.append({"text": s_text, "start": round(s_start, 3), "end": round(s_end, 3)})
                        cursor = s_end
            else:
                # No segment timestamps available: fallback to a single sentence with no timing
                if transcript_text:
                    transcript_sentences.append({"text": transcript_text, "start": 0.0, "end": 0.0})
        except Exception:
            # On any error, fall back to single block transcript
            transcript_sentences = [{"text": transcript_text, "start": 0.0, "end": 0.0}]

        results = {
            "status": "ok",
            "transcript": transcript_text,
            "transcript_segments": transcript_segments,
            "transcript_sentences": transcript_sentences,
            "persons": {},
            "video_path": None,
            "audio_path": rel_audio_path,
            "audio_only": True,
            "is_audio": True
        }
        
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        
        media_file.status = 'saved'
        media_file.save()
        
        logger.info(f"✅ Audio processing complete: {task_id}")
        return {"status": "ok", "result_path": result_path, "media_file_id": media_file_id}

    except Exception as e:
        logger.exception(f"Audio processing failed: {e}")
        
        if media_file:
            media_file.refresh_from_db()
            if media_file.status == 'stopped':
                logger.info(f"Task {task_id} was stopped by user")
                err_obj = {"status": "stopped", "error": "Processing stopped by user"}
                with open(result_path, "w", encoding="utf-8") as fh:
                    json.dump(err_obj, fh, ensure_ascii=False, indent=2)
                return {"status": "stopped", "message": "Processing stopped by user"}
            else:
                media_file.status = 'failed'
                media_file.save()
        
        err_obj = {"status": "error", "error": str(e)}
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(err_obj, fh, ensure_ascii=False, indent=2)
        raise

@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True)
def process_video_task(self, video_path, media_file_id=None):
    """
    Persistent video processing task with database status tracking.
    Resumes on restart/crash.
    """
    from core.models import MediaFile
    from analysis_pipeline.video_processor_enhanced import process_video_with_db
    
    task_id = self.request.id
    result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
    
    # Get or create MediaFile record
    if media_file_id:
        try:
            media_file = MediaFile.objects.get(id=media_file_id)
        except MediaFile.DoesNotExist:
            media_file = None
    else:
        media_file = None
    
    # Create MediaFile if doesn't exist
    if not media_file:
        media_file = MediaFile.objects.create(
            filename=os.path.basename(video_path),
            status='processing',
            task_id=task_id
        )
        media_file_id = media_file.id
    else:
        # CRITICAL CHECK: If already processed and saved, skip entirely
        media_file.refresh_from_db()
        if media_file.status == 'saved':
            logger.info(f"Task {task_id} skipped - file already processed and saved")
            # Return existing results if available
            if os.path.exists(result_path):
                with open(result_path, 'r', encoding='utf-8') as f:
                    existing_results = json.load(f)
                return existing_results
            return {"status": "saved", "message": "File already processed and saved", "media_file_id": media_file_id}
        
        # CHECK: If status is 'stopped', don't process
        if media_file.status == 'stopped':
            logger.info(f"Task {task_id} skipped - file was stopped")
            return {"status": "stopped", "message": "Processing was stopped by user"}
        
        media_file.status = 'processing'
        media_file.task_id = task_id
        media_file.save()
    
    try:
        logger.info(f"Starting video processing: {video_path}")
        
        # Run the enhanced pipeline
        results = process_video_with_db(
            video_path=video_path,
            task_id=task_id,
            media_file=media_file
        )
        
        # Update status
        media_file.status = 'processed'
        media_file.progress = 100
        media_file.save()
        
        # Save results to JSON
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        
        # Mark as saved
        media_file.status = 'saved'
        media_file.save()
        
        logger.info(f"✅ Video processing complete: {task_id}")
        return {"status": "ok", "result_path": result_path, "media_file_id": media_file_id}

    except Exception as e:
        logger.exception(f"Video processing failed: {e}")
        
        # Check if it was stopped by user
        if media_file:
            media_file.refresh_from_db()
            if media_file.status == 'stopped':
                logger.info(f"Task {task_id} was stopped by user")
                err_obj = {"status": "stopped", "error": "Processing stopped by user"}
                with open(result_path, "w", encoding="utf-8") as fh:
                    json.dump(err_obj, fh, ensure_ascii=False, indent=2)
                return {"status": "stopped", "message": "Processing stopped by user"}
            else:
                # Update status to failed
                media_file.status = 'failed'
                media_file.save()
        
        # Write error info
        err_obj = {"status": "error", "error": str(e)}
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(err_obj, fh, ensure_ascii=False, indent=2)
        raise