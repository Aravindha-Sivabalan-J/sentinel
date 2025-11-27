import os
import django
import shutil

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinel.settings')
django.setup()

from core.models import MediaFile, DetectedPerson, TimestampLog, Transcript
from django.conf import settings

# Delete all database records
print("Deleting database records...")
TimestampLog.objects.all().delete()
DetectedPerson.objects.all().delete()
Transcript.objects.all().delete()
MediaFile.objects.all().delete()
print("✅ Database cleaned")

# Delete media files
media_root = settings.MEDIA_ROOT
dirs_to_clean = [
    'results',
    'media_files',
    'thumbnails',
    'face_crops',
    'incoming'
]

for dir_name in dirs_to_clean:
    dir_path = os.path.join(media_root, dir_name)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
        os.makedirs(dir_path, exist_ok=True)
        print(f"✅ Cleaned {dir_name}/")

print("\n🎉 Media database reset complete!")
