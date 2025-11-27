# Unified Upload Page - Implementation Guide

## Overview
The new unified upload page combines three upload methods into a single, streamlined interface:
1. **Local Files** (Audio + Video)
2. **YouTube Download**
3. **Quick Image Analysis**

## Features

### 1. Local Files Tab
- **Combined Upload**: Single endpoint for both audio and video files
- **Supported Formats**:
  - Video: MP4, AVI, MOV, MKV, WEBM
  - Audio: MP3, WAV, FLAC, M4A
- **Features**:
  - Drag & drop support
  - File type validation
  - Real-time upload progress
  - Auto-redirect to database view after upload

### 2. YouTube Tab
- Download videos directly from YouTube URLs
- Automatic processing for face detection and transcription
- Progress tracking
- Auto-redirect to database view

### 3. Quick Image Tab
- Instant face recognition without database storage
- Fast analysis for single images
- Immediate results display
- Supports JPG, PNG, BMP

## Technical Implementation

### Backend Endpoint Reuse
Both audio and video files use the **same backend endpoint**:
```python
# views.py:301-387
def upload_media_to_db(request):
    # Handles both .mp3/.wav/audio AND .mp4/.avi/video
    # Automatically detects file type and processes accordingly
```

### Frontend Architecture
```
unified_upload.html
├── Tab Navigation (JavaScript-based switching)
├── Tab 1: Local Files
│   ├── File input with drag & drop
│   ├── Name input
│   └── Upload button → /upload-media-to-db/
├── Tab 2: YouTube
│   ├── URL input
│   ├── Name input
│   └── Download button → /download-youtube/
└── Tab 3: Quick Image
    ├── Image file input
    └── Analyze button → / (POST, home_view)
```

### Routing Changes
```python
# core/urls.py:6
path("", views.home_view, name="home")
# Now renders unified_upload.html instead of home.html
```

### Key Files Modified
1. **templates/unified_upload.html** (NEW)
   - Tabbed interface with 3 sections
   - Drag & drop file upload
   - Real-time feedback
   - Mobile responsive

2. **core/views.py:29-35**
   - Changed `render(request, "home.html")` to `render(request, "unified_upload.html")`

## User Experience Flow

### Upload Audio/Video Files
1. User selects "Local Files" tab (default)
2. Drags file or clicks to browse
3. File name displays below
4. Enters descriptive name
5. Clicks "Upload & Process"
6. Loading indicator shows
7. Success message appears
8. Auto-redirects to "View Database" page (2 seconds)

### Download from YouTube
1. User clicks "YouTube" tab
2. Pastes YouTube URL
3. Enters video name
4. Clicks "Download & Process"
5. Download progress shows
6. Success message appears
7. Auto-redirects to "View Database" page

### Quick Image Analysis
1. User clicks "Quick Image" tab
2. Selects image file
3. Clicks "Analyze Image"
4. Results displayed on image_result.html page

## Advantages of Unified Approach

### For Users
✅ Single page for all upload needs
✅ Intuitive tabbed interface
✅ Consistent UI/UX across all upload types
✅ Less navigation required
✅ Clear visual feedback

### For Developers
✅ Reduced code duplication
✅ Single endpoint for audio + video
✅ Easier maintenance
✅ Consistent error handling
✅ Better code organization

## API Endpoints Used

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|---------|
| `/upload-media-to-db/` | POST | Upload audio/video to DB | Local Files tab |
| `/download-youtube/` | POST | Download from YouTube | YouTube tab |
| `/` (home_view) | POST | Quick image analysis | Quick Image tab |

## Browser Compatibility
- Modern browsers (Chrome, Firefox, Safari, Edge)
- Drag & drop supported on desktop
- Mobile responsive design
- File type validation via HTML5

## Migration Notes
Old templates are preserved:
- `home.html` - Original upload page
- `audio_to_text.html` - Original audio upload
- `youtube_download.html` - Original YouTube download

These can be used as fallbacks or for comparison, but the main route now uses `unified_upload.html`.

## Customization
To modify tab names or add new tabs:
1. Update tab navigation in `unified_upload.html:400-420`
2. Add new tab content section following existing pattern
3. Create corresponding `switchTab()` handler if needed

## Testing Checklist
- [ ] Upload MP4 video file
- [ ] Upload MP3 audio file
- [ ] Download YouTube video
- [ ] Upload quick analysis image
- [ ] Test drag & drop
- [ ] Test error messages
- [ ] Test auto-redirect
- [ ] Test mobile responsiveness
- [ ] Verify all file types accepted
- [ ] Check CSRF token handling
