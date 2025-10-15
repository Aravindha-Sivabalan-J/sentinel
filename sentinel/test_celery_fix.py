#!/usr/bin/env python3
"""
Quick test to verify Celery task imports work correctly
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinel.settings')
sys.path.append(os.path.dirname(__file__))
django.setup()

try:
    from core.tasks import process_video_task
    print("✅ Successfully imported process_video_task")
    
    # Test if analysis_pipeline imports work
    from analysis_pipeline.processor import process_video
    print("✅ Successfully imported process_video from analysis_pipeline")
    
    from analysis_pipeline.tracker import track_faces_in_video
    print("✅ Successfully imported track_faces_in_video")
    
    from analysis_pipeline.transcriber import eat_video
    print("✅ Successfully imported eat_video")
    
    print("\n🎉 All imports successful! Celery task should work now.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Other error: {e}")
    sys.exit(1)