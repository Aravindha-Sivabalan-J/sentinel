from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("results/<str:task_id>/", views.results_page, name="results_page"),
    path("task-status/<uuid:task_id>/", views.task_status, name="task_status"),
    path("enroll/", views.enroll_view, name="enroll_person"),
]