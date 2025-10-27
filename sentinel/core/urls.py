from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("results/<str:task_id>/", views.results_page, name="results_page"),
    path("task-status/<uuid:task_id>/", views.task_status, name="task_status"),
    path("enroll/", views.enroll_view, name="enroll_person"),
    path("download-youtube/", views.download_youtube_video, name="download_youtube"),
    path("upload-audio/", views.upload_audio_to_db, name="upload_audio"),
    path("get-db-media/", views.get_db_media, name="get_db_media"),
    path("process-db-media/", views.process_db_media, name="process_db_media"),
]