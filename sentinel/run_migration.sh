#!/bin/bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python manage.py makemigrations
python manage.py migrate
