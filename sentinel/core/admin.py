from django.contrib import admin
from .models import MediaFile, Transcript, DetectedPerson, TimestampLog

admin.site.register(MediaFile)
admin.site.register(Transcript)
admin.site.register(DetectedPerson)
admin.site.register(TimestampLog)
