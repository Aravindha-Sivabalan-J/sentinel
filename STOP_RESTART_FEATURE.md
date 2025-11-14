# Stop and Restart Processing Feature

## Overview
Added stop and restart processing buttons to the view-db page for managing media file processing.

## Changes Made

### 1. Models (`core/models.py`)
- Added `'stopped'` status to `MediaFile.STATUS_CHOICES`

### 2. Views (`core/views.py`)
Added two new view functions:

#### `stop_processing(request, media_file_id)`
- Revokes the Celery task using `AsyncResult(task_id).revoke(terminate=True)`
- Updates media file status to `'stopped'`
- Returns JSON response

#### `restart_processing(request, media_file_id)`
- Finds the original video file in incoming or media_files directory
- Creates new Celery task with `process_video_task.delay()`
- Updates media file with new task_id and status `'processing'`
- Resets progress to 0
- Returns JSON response

### 3. URLs (`core/urls.py`)
Added two new URL patterns:
- `/stop-processing/<int:media_file_id>/`
- `/restart-processing/<int:media_file_id>/`

### 4. Template (`templates/view_db.html`)
- Added CSS for `stopped` status (red background)
- Added CSS for `btn-danger` (red button)
- Added CSS for `btn-group` (button layout)
- Added "Stop" button for files with `processing` status
- Added "Restart" button for files with `stopped` or `failed` status
- Added JavaScript functions:
  - `stopProcessing(id)` - Calls stop API with confirmation
  - `restartProcessing(id)` - Calls restart API with confirmation
  - `getCookie(name)` - Gets CSRF token for POST requests

## How It Works

### Stop Processing
1. User clicks "Stop" button on a processing file
2. Confirmation dialog appears
3. If confirmed, sends POST request to `/stop-processing/<id>/`
4. Backend revokes the Celery task (terminates it)
5. Updates database status to `'stopped'`
6. Page refreshes to show updated status

### Restart Processing
1. User clicks "Restart" button on a stopped/failed file
2. Confirmation dialog appears
3. If confirmed, sends POST request to `/restart-processing/<id>/`
4. Backend locates original video file
5. Creates new Celery task
6. Updates database with new task_id and `'processing'` status
7. Page refreshes to show updated status

## Migration Required

Run the following command to apply the database changes:

```bash
cd sentinel
python manage.py makemigrations
python manage.py migrate
```

## Features

✅ Stop processing button appears only for files currently processing
✅ Restart button appears for stopped or failed files
✅ Confirmation dialogs prevent accidental actions
✅ CSRF protection for all POST requests
✅ Auto-refresh every 5 seconds to show updated status
✅ Persistent task system ensures other files continue processing
✅ Stopped files can be restarted at any time

## Notes

- Stopping a file terminates the Celery task immediately
- The next file in the queue will start processing automatically
- Restarting creates a completely new task (doesn't resume from where it stopped)
- Original video files must be available in `media/incoming/` or `media/media_files/videos/` for restart to work
