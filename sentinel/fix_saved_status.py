#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinel.settings')
django.setup()

from core.models import MediaFile

# Fix files that should be saved but are showing as stopped
stopped_files = MediaFile.objects.filter(status='stopped')
for mf in stopped_files:
    if mf.annotated_video and mf.annotated_video.name:
        mf.status = 'saved'
        mf.save()
        print(f"✅ Fixed: {mf.filename} -> saved")

# Update processed to saved
MediaFile.objects.filter(status='processed').update(status='saved')
print("✅ All processed files updated to saved")
