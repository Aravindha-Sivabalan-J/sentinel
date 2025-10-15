# import os
# from celery import Celery

# # set default Django settings
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel.settings")

# app = Celery("sentinel")

# # load settings from Django's settings.py, using CELERY_ prefix
# app.config_from_object("django.conf:settings", namespace="CELERY")

# # auto-discover tasks in all installed apps
# app.autodiscover_tasks()


import os
from celery import Celery
from kombu import Queue

# set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel.settings")

app = Celery("sentinel")

# load settings from Django's settings.py, using CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# **KEY FIX: Configure task queues for better handling**
app.conf.task_default_queue = 'default'
app.conf.task_queues = (
    Queue('default'),
    Queue('video_processing', routing_key='video_processing'),
)

# auto-discover tasks in all installed apps
app.autodiscover_tasks()

# **KEY FIX: Add connection recovery settings**
app.conf.broker_connection_retry_on_startup = True