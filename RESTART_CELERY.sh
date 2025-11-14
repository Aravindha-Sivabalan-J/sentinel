#!/bin/bash
# Script to restart Celery worker

echo "Stopping Celery worker..."
pkill -f "celery.*worker" || echo "No Celery worker running"

sleep 2

echo "Starting Celery worker..."
cd /home/cannyminds/Desktop/SENTINEL/sentinel
celery -A sentinel worker --loglevel=info
