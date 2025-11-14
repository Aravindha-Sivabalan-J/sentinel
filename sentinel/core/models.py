# sentinel/core/models.py

from django.db import models
import os

# This model will store information about each uploaded file.
class MediaFile(models.Model):
    # Defines the different states the analysis can be in.
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('saved', 'Saved'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped'),
    ]
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    filename = models.CharField(max_length=255, blank=True)
    video_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    task_id = models.CharField(max_length=255, blank=True, null=True)
    annotated_video = models.FileField(upload_to='results/annotated/%Y/%m/%d/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    progress = models.IntegerField(default=0)

    # This is a special Django method. When we save a MediaFile object,
    # this code will run automatically to extract the filename.
    def save(self, *args, **kwargs):
        if not self.filename:
            self.filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"File: {self.filename}"

# This model will store the final text transcript of a video.
class Transcript(models.Model):
    media_file = models.OneToOneField(MediaFile, on_delete=models.CASCADE, related_name='transcript')
    full_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcript for {self.media_file.filename}"

# This model will store information about each unique face identified in a file.
class DetectedPerson(models.Model):
    media_file = models.ForeignKey(MediaFile, on_delete=models.CASCADE, related_name='detected_persons')
    identity = models.CharField(max_length=255, blank=True, null=True, default='Unknown')
    confidence = models.FloatField(default=0.0)
    face_thumbnail = models.ImageField(upload_to='thumbnails/%Y/%m/%d/')
    arcface_embedding = models.BinaryField(blank=True, null=True)
    facenet_embedding = models.BinaryField(blank=True, null=True)

    def __str__(self):
        return f"{self.identity} in {self.media_file.filename}"

# This model will store the specific time intervals a person appears in a video.
class TimestampLog(models.Model):
    detected_person = models.ForeignKey(DetectedPerson, on_delete=models.CASCADE, related_name='timestamps')
    start_time = models.FloatField()
    end_time = models.FloatField()

    def __str__(self):
        return f"{self.detected_person.identity} from {self.start_time:.2f}s to {self.end_time:.2f}s"

# Model for storing downloaded YouTube videos
class Video(models.Model):
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    download_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.download_date}"

# Model for storing uploaded audio files
class AudioFile(models.Model):
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.upload_date}"