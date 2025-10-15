#!/usr/bin/env python3
"""
Simple test to verify analysis_pipeline imports work
"""
import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

try:
    from analysis_pipeline.processor import process_video
    print("✅ Successfully imported process_video from analysis_pipeline")
    
    from analysis_pipeline.tracker import track_faces_in_video
    print("✅ Successfully imported track_faces_in_video")
    
    from analysis_pipeline.transcriber import eat_video
    print("✅ Successfully imported eat_video")
    
    from analysis_pipeline.detector import detect_faces
    print("✅ Successfully imported detect_faces")
    
    from analysis_pipeline.embedder import ArcFaceEmbedder
    print("✅ Successfully imported ArcFaceEmbedder")
    
    from analysis_pipeline.vector_db import MilvusDBManager
    print("✅ Successfully imported MilvusDBManager")
    
    print("\n🎉 All analysis_pipeline imports successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"❌ Other error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)