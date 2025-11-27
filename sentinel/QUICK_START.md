# 🚀 Quick Start Guide - Unified Upload Page

## What's New?

You now have a **single unified page** for all media uploads instead of three separate pages!

### Before ❌
- `/` → Upload video/image
- `/youtube-download/` → Download YouTube
- `/audio-to-text/` → Upload audio

### After ✅
- `/` → **Everything in one place with tabs!**
  - Tab 1: Local Files (audio + video combined)
  - Tab 2: YouTube
  - Tab 3: Quick Image

---

## 📋 Files Modified

### Created
- ✅ `templates/unified_upload.html` - New unified interface

### Modified
- ✅ `core/views.py` (lines 29-35) - Updated home_view()

### Unchanged (Backend works the same!)
- ✅ `core/urls.py` - All routes work as before
- ✅ `core/tasks.py` - Celery tasks unchanged
- ✅ `core/models.py` - Database models unchanged

---

## 🎯 How to Use

### Option 1: Upload Local Files (Video or Audio)

1. Navigate to home page (`http://localhost:8000/`)
2. You'll see **"Local Files"** tab by default
3. **Drag and drop** your file OR **click to browse**
4. Supported formats:
   - Video: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`
   - Audio: `.mp3`, `.wav`, `.flac`, `.m4a`
5. Enter a descriptive name
6. Click **"Upload & Process"**
7. Wait for success message
8. Auto-redirects to database view

**Backend**: Uses `/upload-media-to-db/` endpoint (handles BOTH audio and video)

---

### Option 2: Download from YouTube

1. Click **"YouTube"** tab
2. Copy a YouTube URL (e.g., `https://youtube.com/watch?v=...`)
3. Paste it in the URL field
4. Enter a name for the video
5. Click **"Download & Process"**
6. Wait for download to complete
7. Auto-redirects to database view

**Backend**: Uses `/download-youtube/` endpoint

---

### Option 3: Quick Image Analysis

1. Click **"Quick Image"** tab
2. Select an image file (`.jpg`, `.png`, `.bmp`)
3. Click **"Analyze Image"**
4. Instantly see face detection results
5. No database storage - just quick analysis

**Backend**: Traditional form POST to `/` (home_view)

---

## 🔧 Testing Checklist

Run through these tests to verify everything works:

### Test 1: Upload Video File
```bash
1. Go to http://localhost:8000/
2. Default "Local Files" tab should be active
3. Drag and drop a .mp4 file
4. File name should display below
5. Enter name: "Test Video"
6. Click "Upload & Process"
7. Should see loading indicator
8. Success message appears
9. Redirects to /view-db/ after 2 seconds
10. Check database - file should be "processing"
```

### Test 2: Upload Audio File
```bash
1. Go to http://localhost:8000/
2. Click "Local Files" tab (if not already active)
3. Select a .mp3 audio file
4. File name displays
5. Enter name: "Test Audio"
6. Click "Upload & Process"
7. Loading indicator shows
8. Success message appears
9. Auto-redirect to database view
10. File should be processing with transcription
```

### Test 3: YouTube Download
```bash
1. Go to http://localhost:8000/
2. Click "YouTube" tab
3. Paste: https://youtube.com/watch?v=dQw4w9WgXcQ
4. Enter name: "Test YouTube"
5. Click "Download & Process"
6. Wait for download (may take 10-30 seconds)
7. Success message appears
8. Auto-redirect to database
9. Video should be downloaded and processing
```

### Test 4: Quick Image
```bash
1. Go to http://localhost:8000/
2. Click "Quick Image" tab
3. Select a .jpg image with faces
4. Click "Analyze Image"
5. Should redirect to results page
6. Should show detected faces immediately
7. No database storage (this is instant analysis)
```

### Test 5: Drag & Drop
```bash
1. Go to http://localhost:8000/
2. Open file explorer
3. Drag a video file onto the upload area
4. File should be selected automatically
5. File name displays
6. Complete upload as normal
```

### Test 6: Error Handling
```bash
1. Try uploading without selecting file
   → Should show error: "Please select a file"

2. Try uploading without entering name
   → Should show error: "Please enter a name for the file"

3. Try YouTube download with invalid URL
   → Should show error from backend

4. Try uploading unsupported file type
   → Browser should prevent selection (HTML5 validation)
```

---

## 🐛 Troubleshooting

### Issue: Page shows old home.html instead of new unified page

**Solution:**
```bash
# Clear Django template cache
rm -rf __pycache__/
python manage.py collectstatic --noinput

# Restart server
python manage.py runserver
```

---

### Issue: Upload button disabled or not working

**Check:**
1. File selected? (File name should display)
2. Name entered? (Required field)
3. JavaScript errors? (Open browser console: F12)

**Solution:**
```bash
# Clear browser cache
Ctrl + Shift + R (hard refresh)

# Check browser console for errors
F12 → Console tab
```

---

### Issue: YouTube download fails

**Check:**
1. Is `yt-dlp` installed?
```bash
pip install yt-dlp
```

2. Is URL valid?
```
Valid: https://youtube.com/watch?v=VIDEO_ID
Valid: https://youtu.be/VIDEO_ID
Invalid: https://youtube.com/playlist?list=...
```

---

### Issue: Files not processing

**Check Celery:**
```bash
# Make sure Celery worker is running
celery -A sentinel worker --loglevel=info

# Check for errors in Celery logs
```

**Check Database:**
```bash
python manage.py shell
>>> from core.models import MediaFile
>>> MediaFile.objects.all()
>>> # Check status of uploaded files
```

---

## 📊 Backend Endpoints Reference

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|---------|
| `/` | GET | Render unified upload page | Browser navigation |
| `/` | POST | Quick image analysis | Quick Image tab |
| `/upload-media-to-db/` | POST | Upload audio or video | Local Files tab |
| `/download-youtube/` | POST | Download from YouTube | YouTube tab |
| `/view-db/` | GET | View all processed media | Auto-redirect target |

---

## 💡 Pro Tips

### Tip 1: Default Tab
The **Local Files** tab is active by default since it's most commonly used.

### Tip 2: File Naming
Use descriptive names! They'll help you search later:
- ✅ "Q3_2024_Marketing_Meeting"
- ❌ "video1"

### Tip 3: File Size
For faster processing:
- Videos: Compress to 720p or 1080p max
- Audio: 16kHz sample rate is ideal

### Tip 4: Batch Processing
Upload multiple files one after another - they'll queue automatically!

### Tip 5: Mobile Upload
Works on mobile! Take a photo and upload directly from your phone.

---

## 🔐 Security Notes

### File Validation
- ✅ File types validated on client (HTML5)
- ✅ File types validated on server (Python)
- ✅ CSRF tokens on all forms
- ✅ Files saved to controlled directories

### What's Safe
- Uploading from trusted sources ✅
- Using public YouTube videos ✅
- Processing your own media ✅

### What to Avoid
- Don't upload copyrighted content without permission ❌
- Don't download private YouTube videos ❌
- Don't upload extremely large files (>2GB) ❌

---

## 📱 Browser Compatibility

### Fully Supported ✅
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Partially Supported ⚠️
- IE 11 (no drag & drop)
- Older mobile browsers

### Features by Browser
| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Tabs | ✅ | ✅ | ✅ | ✅ |
| Drag & Drop | ✅ | ✅ | ✅ | ✅ |
| File Validation | ✅ | ✅ | ✅ | ✅ |
| Auto-redirect | ✅ | ✅ | ✅ | ✅ |

---

## 🎓 Next Steps

### For Users
1. Try uploading different file types
2. Explore the database view after processing
3. Check out the transcript feature for videos
4. Try the person search functionality

### For Developers
1. Review `IMPLEMENTATION_SUMMARY.md` for technical details
2. Check `ARCHITECTURE_DIAGRAM.md` for system overview
3. Read `UNIFIED_UPLOAD_GUIDE.md` for customization options
4. View `UI_MOCKUP.txt` for interface design reference

---

## 📞 Need Help?

### Quick Checks
1. ✅ Is Django server running? (`python manage.py runserver`)
2. ✅ Is Celery worker running? (`celery -A sentinel worker`)
3. ✅ Is Redis running? (Required for Celery)
4. ✅ Browser console clear? (F12 → No red errors)

### Common Commands
```bash
# Start Django
python manage.py runserver

# Start Celery
celery -A sentinel worker --loglevel=info

# Check migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser
```

---

## ✅ Success Indicators

You'll know it's working when:
- ✅ Upload page shows 3 tabs
- ✅ Files can be dragged and dropped
- ✅ Upload shows loading indicator
- ✅ Success message appears after upload
- ✅ Auto-redirects to database view
- ✅ Files appear in database with "processing" status
- ✅ Eventually status changes to "processed" or "saved"

---

## 🎉 Congratulations!

You now have a modern, unified upload interface that:
- ✅ Combines all upload methods in one place
- ✅ Provides intuitive tab navigation
- ✅ Supports drag & drop
- ✅ Shows real-time feedback
- ✅ Auto-redirects to results
- ✅ Works on desktop and mobile

**Happy uploading! 🚀**
