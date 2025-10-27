#!/bin/bash
# Purge all pending Celery tasks
celery -A sentinel purge -f
