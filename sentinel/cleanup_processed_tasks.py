#!/usr/bin/env python3
"""
Cleanup script to prevent reprocessing of already saved files.
Run this before starting Celery workers to clean up any stale tasks.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinel.settings')
django.setup()

from core.models import MediaFile
from celery.result import AsyncResult
from sentinel.celery import app as celery_app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_processed_tasks():
    """
    Clean up tasks for files that are already processed and saved.
    This prevents reprocessing when Celery restarts.
    """
    logger.info("🧹 Starting cleanup of processed tasks...")
    
    # Get all media files that are already saved but have task_ids
    saved_files = MediaFile.objects.filter(
        status='saved',
        task_id__isnull=False
    ).exclude(task_id='')
    
    cleaned_count = 0
    
    for media_file in saved_files:
        try:
            # Revoke the task to prevent it from running
            result = AsyncResult(media_file.task_id, app=celery_app)
            if result.state in ['PENDING', 'RETRY', 'RECEIVED']:
                result.revoke(terminate=True)
                logger.info(f"✅ Revoked task {media_file.task_id} for saved file: {media_file.filename}")
                cleaned_count += 1
            else:
                logger.info(f"ℹ️  Task {media_file.task_id} already completed/failed for: {media_file.filename}")
                
        except Exception as e:
            logger.warning(f"⚠️  Could not revoke task {media_file.task_id}: {e}")
    
    # Also check for files with 'processed' status that should be 'saved'
    processed_files = MediaFile.objects.filter(status='processed')
    for media_file in processed_files:
        # Check if results exist
        if media_file.annotated_video and media_file.annotated_video.name:
            media_file.status = 'saved'
            media_file.save()
            logger.info(f"✅ Updated status to 'saved' for: {media_file.filename}")
            cleaned_count += 1
    
    logger.info(f"🎉 Cleanup complete! Processed {cleaned_count} files.")
    return cleaned_count

def purge_all_pending_tasks():
    """
    Purge all pending tasks from the Celery queue.
    Use with caution - this will cancel ALL pending tasks.
    """
    logger.info("🚨 PURGING ALL PENDING TASKS...")
    try:
        celery_app.control.purge()
        logger.info("✅ All pending tasks purged from queue")
    except Exception as e:
        logger.error(f"❌ Failed to purge tasks: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup processed tasks')
    parser.add_argument('--purge-all', action='store_true', 
                       help='Purge ALL pending tasks (use with caution)')
    
    args = parser.parse_args()
    
    if args.purge_all:
        purge_all_pending_tasks()
    
    cleanup_processed_tasks()