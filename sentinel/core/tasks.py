import os
import json
from celery import shared_task
from django.conf import settings

# Import your pipeline processor
from analysis_pipeline.processor import process_video

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

@shared_task(bind=True)
def process_video_task(self, video_path):
    """
    Celery task wrapper around analysis_pipeline.processor.process_video.
    Ensures results are written to JSON in RESULTS_DIR with task_id in filename.
    """
    task_id = self.request.id
    result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
    
    # **KEY FIX: Check if result already exists**
    if os.path.exists(result_path):
        try:
            with open(result_path, "r", encoding="utf-8") as fh:
                existing_result = json.load(fh)
            # If it's a valid completed result, return it
            if existing_result.get("status") == "ok" or "video_path" in existing_result:
                print(f"Task {task_id} already completed successfully, returning existing result")
                return {"status": "ok", "result_path": result_path, "message": "Previously completed"}
        except Exception as e:
            print(f"Error reading existing result file: {e}, proceeding with fresh processing")
            # If file is corrupt, continue with processing
    
    try:
        # Run the pipeline with this task_id
        results = process_video(video_path, task_id=task_id)

        # Save results to JSON (Celery backend also stores minimal info)
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)

        return {"status": "ok", "result_path": result_path}

    except Exception as e:
        # Write error info to JSON so frontend polling can stop gracefully
        err_obj = {"status": "error", "error": str(e)}
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(err_obj, fh, ensure_ascii=False, indent=2)
        raise