# Audio Transcription Results Page Update

## Problem
When selecting an audio file from the "Upload from DB" modal:
- Modal remained open during processing
- Transcription displayed in alert popup
- No proper results page for audio-only transcription

## Solution
Audio transcription now follows the same flow as video processing:
1. Modal closes immediately after selection
2. Redirects to results page
3. Displays transcription in the results page UI

## Changes Made

### 1. core/views.py - `process_db_media()`
- Audio transcription now saves results to JSON file (same as video)
- Generates unique task_id for audio results
- Returns task_id instead of transcript text
- Result JSON includes `audio_only: true` flag

### 2. core/views.py - `task_status()`
- Now checks for results file FIRST (before Celery task)
- Handles audio-only results that don't have Celery tasks
- Maintains backward compatibility with video processing

### 3. templates/home.html - `selectMedia()`
- Simplified logic: both video and audio redirect to results page
- Modal closes before redirect
- Removed alert popup for audio transcription

### 4. templates/results.html - `renderResults()`
- Detects `audio_only` flag in results
- Shows "Audio transcription only (no video)" message
- Hides video player for audio-only results
- Displays transcript in same UI as video results

## Result Format

### Audio-Only Result JSON:
```json
{
  "status": "ok",
  "transcript": "transcribed text here...",
  "persons": {},
  "video_path": null,
  "audio_only": true
}
```

### Video Result JSON (unchanged):
```json
{
  "status": "ok",
  "transcript": "transcribed text here...",
  "persons": {...},
  "video_path": "media/results/task_id_annotated.mp4",
  "transcript_segments": [...]
}
```

## User Experience

### Before:
1. Click "Upload from DB"
2. Select audio file
3. Modal stays open with "Processing..." button
4. Alert popup shows transcription
5. Must close alert and modal manually

### After:
1. Click "Upload from DB"
2. Select audio file
3. Modal closes immediately
4. Redirects to results page
5. Transcription displayed in clean UI
6. Consistent experience with video processing

## Benefits
- Consistent UI/UX for both video and audio
- Better presentation of transcription results
- No modal/alert management needed
- Results are saved and can be revisited
- Professional appearance
