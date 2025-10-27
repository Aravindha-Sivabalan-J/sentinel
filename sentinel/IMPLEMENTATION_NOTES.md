# SENTINEL - New Features Implementation

## Summary of Changes

This implementation adds four new features to the SENTINEL application as specified in the requirements:

### Feature 1: YouTube Video Download & Database Storage
- Added input field and button on home page to download YouTube videos
- Uses `yt-dlp` library to download videos
- Prompts user for video name
- Stores video metadata in SQLite database (Video model)
- Videos saved to `media/media_files/videos/`

### Feature 2: Upload and Process Videos from Database
- Added "Upload from DB" button that opens a modal
- Modal displays all videos and audio files from database
- Shows name, type (video/audio), date, and select button
- Video selection: processes through complete existing pipeline
- Audio selection: processes directly through transcription (skips video-to-audio extraction)
- Returns results in existing format

### Feature 3: Audio File Upload with Preprocessing & Database Storage
- Added audio file upload field (accepts .mp3, .wav, .flac, .m4a)
- Preprocesses audio before saving:
  - Converts to 16kHz sample rate
  - Converts to WAV format with 16-bit PCM encoding
  - Mono channel
- Uses ffmpeg for conversion
- Stores preprocessed audio in database (AudioFile model)
- Audio files saved to `media/media_files/audio/`

### Feature 4: Enroll Button
- Added "Go to Enrollment" button on home page
- Links to existing enrollment page

## Files Modified

1. **core/models.py**
   - Added `Video` model with fields: name, file_path, download_date
   - Added `AudioFile` model with fields: name, file_path, upload_date

2. **core/views.py**
   - Added `download_youtube_video()` - handles YouTube video downloads
   - Added `upload_audio_to_db()` - handles audio upload and preprocessing
   - Added `get_db_media()` - returns list of all videos and audio from DB
   - Added `process_db_media()` - processes selected media from database

3. **core/urls.py**
   - Added URL patterns for new endpoints:
     - `/download-youtube/`
     - `/upload-audio/`
     - `/get-db-media/`
     - `/process-db-media/`

4. **templates/home.html**
   - Complete redesign with 5 sections:
     - Upload Image/Video (existing)
     - Download YouTube Video (new)
     - Upload Audio to Database (new)
     - Process Media from Database (new)
     - Enroll New Person (new)
   - Added modal for database media selection
   - Added JavaScript for AJAX requests and UI interactions

5. **core/migrations/0002_video_audiofile.py**
   - Migration file for new models

## Database Schema

### Videos Table
```sql
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Audio Files Table
```sql
CREATE TABLE audio_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Technical Implementation Details

### Storage Strategy
- Videos: `media/media_files/videos/`
- Audio: `media/media_files/audio/`
- File paths stored in database (not BLOBs for efficiency)
- ChromaDB used for face embeddings (unchanged)
- SQLite3 used for video/audio metadata

### Audio Preprocessing
Command used: `ffmpeg -i input -ar 16000 -ac 1 -acodec pcm_s16le -y output.wav`
- Sample rate: 16000 Hz
- Channels: 1 (mono)
- Encoding: PCM 16-bit little-endian
- Format: WAV

### Processing Pipeline Integration
- Video from DB: Routes through `process_video_task.delay()` (existing Celery task)
- Audio from DB: Calls `eat_video()` directly (transcription only)
- No modifications to existing processing logic
- Maintains identical response format

### Error Handling
- All endpoints return JSON responses with success/error status
- Frontend displays user-friendly error messages
- Database errors handled gracefully
- File cleanup on errors (temp files removed)
- Loading indicators during async operations

## Dependencies Required

Ensure these are installed:
- `yt-dlp` - for YouTube video downloads
- `ffmpeg` - for audio preprocessing
- Django models and migrations already handle database operations

## Setup Instructions

1. Run migrations:
   ```bash
   python manage.py migrate
   ```

2. Ensure directories exist (already created):
   ```bash
   mkdir -p media/media_files/videos
   mkdir -p media/media_files/audio
   ```

3. Install dependencies if not present:
   ```bash
   pip install yt-dlp
   # ffmpeg should be installed system-wide
   ```

## API Endpoints

### POST /download-youtube/
Downloads YouTube video and saves to database
- Parameters: `youtube_url`, `video_name`
- Returns: JSON with success/error

### POST /upload-audio/
Uploads and preprocesses audio file
- Parameters: `audio_file` (file), `audio_name`
- Returns: JSON with success/error

### GET /get-db-media/
Returns all videos and audio from database
- Returns: JSON array of media items

### POST /process-db-media/
Processes selected media from database
- Parameters: `media_id`, `media_type`
- Returns: JSON with task_id (video) or transcript (audio)

## UI Features

- Clean, sectioned layout
- AJAX-based operations (no page reloads)
- Modal for media selection
- Loading indicators
- Success/error messages
- Row highlighting on selection
- Responsive design

## Notes

- All features implemented as specified
- No modifications to existing processing pipeline
- File paths stored in DB (not BLOBs)
- ChromaDB for embeddings, SQLite3 for media metadata
- Follows Django best practices
- CSRF protection enabled
- Minimal code approach maintained
