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
        # CHECK: If status is 'stopped', don't process
        media_file.refresh_from_db()
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