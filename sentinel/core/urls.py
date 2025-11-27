from django.urls import path
from . import views
from . import live_views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("analyze-image/", views.analyze_image_view, name="analyze_image"),
    path("results/<str:task_id>/", views.results_page, name="results_page"),
    path("task-status/<uuid:task_id>/", views.task_status, name="task_status"),
    path("enroll/", views.enroll_view, name="enroll_person"),
    path("youtube-download/", views.youtube_download_view, name="youtube_download_page"),
    path("audio-to-text/", views.audio_to_text_view, name="audio_to_text_page"),
    path("download-youtube/", views.download_youtube_video, name="download_youtube"),
    path("upload-audio/", views.upload_audio_to_db, name="upload_audio"),
    path("upload-media-to-db/", views.upload_media_to_db, name="upload_media_to_db"),
    path("get-db-media/", views.get_db_media, name="get_db_media"),
    path("process-db-media/", views.process_db_media, name="process_db_media"),
    path("view-db/", views.view_db, name="view_db"),
    path("api/get-all-media/", views.get_all_media, name="get_all_media"),
    path("api/search-media/", views.search_media_files, name="search_media_files"),
    path("search-media/", views.search_media_view, name="search_media"),
    path("view-media/<int:media_file_id>/", views.view_media, name="view_media"),
    path("stop-processing/<int:media_file_id>/", views.stop_processing, name="stop_processing"),
    path("restart-processing/<int:media_file_id>/", views.restart_processing, name="restart_processing"),
    path("live-detection/", live_views.live_detection_view, name="live_detection"),
    path("live-feed/", live_views.live_feed, name="live_feed"),
    path("live-faces/", live_views.live_faces, name="live_faces"),
]