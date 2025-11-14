#!/usr/bin/env python3
from analysis_pipeline.dual_vector_db import DualChromaDBManager

db = DualChromaDBManager()

arc_count = db.arcface_collection.count()
fn_count = db.facenet_collection.count()

print(f"ArcFace collection: {arc_count} people enrolled")
print(f"FaceNet collection: {fn_count} people enrolled")

if arc_count > 0:
    arc_data = db.arcface_collection.get()
    print(f"\nEnrolled people IDs:")
    for person_id in arc_data['ids']:
        print(f"  - {person_id}")
