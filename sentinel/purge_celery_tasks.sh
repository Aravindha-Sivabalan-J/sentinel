#!/bin/bash
# Prevent reprocessing of saved files

echo "🛡️ Preventing reprocessing..."
python prevent_reprocessing.py

echo "🧹 Purging pending tasks..."
celery -A sentinel purge -f

echo "✅ Safe to start Celery!"
