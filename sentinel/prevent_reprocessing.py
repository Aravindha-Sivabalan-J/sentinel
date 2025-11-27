#!/usr/bin/env python3
"""
Minimal script to prevent reprocessing of saved files.
Run this before starting Celery workers.
"""
import os, sys, django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinel.settings')
django.setup()

from core.models import MediaFile
from celery.result import AsyncResult
from sentinel.celery import app

def prevent_reprocessing():
    # Revoke tasks for saved files WITHOUT changing their status
    saved_files = MediaFile.objects.filter(status='saved', task_id__isnull=False).exclude(task_id='')
    
    for media_file in saved_files:
        try:
            AsyncResult(media_file.task_id, app=app).revoke(terminate=False)
            print(f"✅ Revoked task for saved file: {media_file.filename}")
        except:
            pass
    
    # Update processed files to saved
    MediaFile.objects.filter(status='processed').update(status='saved')
    print("✅ Updated processed files to saved status")
    
    # Revoke tasks for processed files
    processed_files = MediaFile.objects.filter(status='saved', task_id__isnull=False).exclude(task_id='')
    for media_file in processed_files:
        try:
            AsyncResult(media_file.task_id, app=app).revoke(terminate=False)
        except:
            pass

if __name__ == "__main__":
    prevent_reprocessing()