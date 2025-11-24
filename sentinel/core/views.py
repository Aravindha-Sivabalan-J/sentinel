import os, uuid, json, cv2, subprocess
from celery.result import AsyncResult
from django.conf import settings
from django.shortcuts import render, redirect
import logging
import numpy as np
from django.http import JsonResponse, StreamingHttpResponse
from analysis_pipeline.detector import detect_faces
from analysis_pipeline.dual_embedder import DualEmbedder
from analysis_pipeline.dual_vector_db import DualChromaDBManager
from analysis_pipeline.processor import expand_box, is_blurry, prepare_face_for_arcface
from .models import Video, AudioFile
from .tasks import process_video_task
import cv2
import threading

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize DB & embedder once
embedder = DualEmbedder()
db = DualChromaDBManager()

MEDIA_ROOT = getattr(settings, "MEDIA_ROOT", os.path.join(settings.BASE_DIR, "media"))
RESULTS_DIR = os.path.join(MEDIA_ROOT, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def home_view(request):
    if request.method == "GET":
        return render(request, "home.html")

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return render(request, "home.html", {"error": "No file uploaded."})

    # Save upload
    save_dir = os.path.join(MEDIA_ROOT, "incoming")
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    # ---- VIDEO ----
    if ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
        from core.models import MediaFile
        
        # Create MediaFile record
        media_file = MediaFile.objects.create(
            filename=uploaded_file.name,
            video_path=file_path,
            status='pending'
        )
        
        # Start processing task
        task = process_video_task.delay(file_path, media_file.id)
        
        # Update with task_id
        media_file.task_id = task.id
        media_file.status = 'processing'
        media_file.save()
        
        return redirect("core:results_page", task_id=task.id)

    # ---- IMAGE ----
    faces = detect_faces(file_path)
    if not faces:
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "no_face": True,
        })

    face = faces[0]
    aligned_rgb = face["aligned_face"]
    
    if aligned_rgb is None or aligned_rgb.size == 0:
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "read_error": True,
        })

    if is_blurry(aligned_rgb, thresh=50):
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "blurry": True,
        })

    arc_emb, fn_emb = embedder.get_dual_embeddings(aligned_rgb)
    if arc_emb is None or fn_emb is None:
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "embedding_error": True,
        })

    match_id, distance, metadata = db.search_person(arc_emb, fn_emb, k=5, arc_threshold=0.30, fn_threshold=0.30)
    match = None if match_id == "NO MATCH FOUND" else {
        "id": match_id, "distance": distance, "metadata": metadata
    }

    return render(request, "image_result.html", {
        "media_url": os.path.relpath(file_path, MEDIA_ROOT),
        "match": match,
    })


def results_page(request, task_id):
    results_file = os.path.join(RESULTS_DIR, f"{task_id}.json")
    results = {"video_path": None, "persons": {}, "transcript": ""}

    if os.path.exists(results_file):
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            pass

    if results.get("video_path"):
        results["video_path"] = results["video_path"].replace("\\", "/")

    if "persons" in results:
        for pid, pdata in results["persons"].items():
            if isinstance(pdata, dict) and "faces" in pdata:
                pdata["faces"] = [f.replace("\\", "/") for f in pdata["faces"]]

    return render(request, "results.html", {
        "task_id": str(task_id),
        "results": results,
        "MEDIA_URL": settings.MEDIA_URL,
    })


def enroll_view(request):
    if request.method == "GET":
        return render(request, "enroll.html")

    if request.method == "POST":
        person_id = request.POST.get("person_id")
        job = request.POST.get("job")
        age = request.POST.get("age")
        height = request.POST.get("height")
        weight = request.POST.get("weight")
        uploaded_file = request.FILES.get("face_image")

        if not all([person_id, job, age, height, weight, uploaded_file]):
            return render(request, "enroll.html", {"error": "All fields are required."})

        save_dir = os.path.join(MEDIA_ROOT, "enrollments")
        os.makedirs(save_dir, exist_ok=True)
        image_path = os.path.join(save_dir, uploaded_file.name)
        with open(image_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        faces = detect_faces(image_path)
        if not faces or len(faces) != 1:
            return render(request, "enroll.html", {"error": "Upload an image with exactly one face."})

        face = faces[0]
        aligned_rgb = face["aligned_face"]  # Already aligned by detector
        
        if aligned_rgb is None or aligned_rgb.size == 0:
            return render(request, "enroll.html", {"error": "Face alignment failed."})

        # Save face crop to media/face_crops folder
        face_crops_dir = os.path.join(MEDIA_ROOT, "face_crops")
        os.makedirs(face_crops_dir, exist_ok=True)
        face_crop_path = os.path.join(face_crops_dir, f"{person_id}.jpg")

        try:
            img_to_write = cv2.cvtColor(aligned_rgb, cv2.COLOR_RGB2BGR)
            success = cv2.imwrite(face_crop_path, img_to_write)
            if success:
                logger.info(f"[FACE_CROP] Saved aligned face for {person_id} at {face_crop_path}")
            else:
                logger.error(f"[FACE_CROP] Failed to save aligned face for {person_id}")
        except Exception as e:
            logger.exception(f"[FACE_CROP] Exception while saving face crop for {person_id}: {e}")

        # Generate dual embeddings directly from aligned RGB face
        arc_emb, fn_emb = embedder.get_dual_embeddings(aligned_rgb)
        if arc_emb is None or fn_emb is None:
            return render(request, "enroll.html", {"error": "Failed to generate dual embeddings."})

        # Log embedding norms for verification
        logger.info(f"[ENROLL_DEBUG] person={person_id} arc_norm={np.linalg.norm(arc_emb):.6f} fn_norm={np.linalg.norm(fn_emb):.6f}")

        metadata = {"job": job, "age": age, "height": height, "weight": weight}
        db.add_person(person_id=person_id, arcface_emb=arc_emb, facenet_emb=fn_emb, metadata=metadata)

        return render(request, "enroll.html", {"success": f"Enrolled {person_id} successfully!"})


def task_status(request, task_id):
    results_file = os.path.join(RESULTS_DIR, f"{task_id}.json")
    
    if os.path.exists(results_file):
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "error":
            return JsonResponse({"state": "ERROR", "message": data.get("error")})
        return JsonResponse({"state": "SUCCESS", "results": data})
    
    result = AsyncResult(task_id)
    if not result.ready():
        return JsonResponse({"state": result.state})
    
    return JsonResponse({"state": "ERROR", "message": "No results file found"})


def download_youtube_video(request):
    if request.method == "POST":
        from core.models import MediaFile
        
        url = request.POST.get("youtube_url")
        name = request.POST.get("video_name")
        
        if not url or not name:
            return JsonResponse({"error": "URL and name are required"}, status=400)
        
        try:
            save_dir = os.path.join(MEDIA_ROOT, "media_files", "videos")
            os.makedirs(save_dir, exist_ok=True)
            
            output_path = os.path.join(save_dir, f"{name}.mp4")
            
            # Download video
            cmd = ["yt-dlp", "-f", "best", "-o", output_path, url]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Create MediaFile record and process
            media_file = MediaFile.objects.create(
                filename=name,
                video_path=output_path,
                status='pending'
            )
            
            # Start processing
            task = process_video_task.delay(output_path, media_file.id)
            media_file.task_id = task.id
            media_file.status = 'processing'
            media_file.save()
            
            return JsonResponse({
                "success": True, 
                "message": f"Video '{name}' downloaded and processing started",
                "media_file_id": media_file.id
            })
        except Exception as e:
            logger.error(f"YouTube download error: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request"}, status=400)


def upload_audio_to_db(request):
    if request.method == "POST":
        audio_file = request.FILES.get("audio_file")
        name = request.POST.get("audio_name")
        
        if not audio_file or not name:
            return JsonResponse({"error": "Audio file and name are required"}, status=400)
        
        try:
            save_dir = os.path.join(MEDIA_ROOT, "media_files", "audio")
            os.makedirs(save_dir, exist_ok=True)
            
            temp_path = os.path.join(save_dir, f"temp_{audio_file.name}")
            with open(temp_path, "wb") as f:
                for chunk in audio_file.chunks():
                    f.write(chunk)
            
            output_path = os.path.join(save_dir, f"{name}.wav")
            cmd = ["ffmpeg", "-i", temp_path, "-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le", "-y", output_path]
            subprocess.run(cmd, check=True, capture_output=True)
            
            os.remove(temp_path)
            
            audio = AudioFile.objects.create(name=name, file_path=output_path)
            return JsonResponse({"success": True, "message": f"Audio '{name}' uploaded successfully"})
        except Exception as e:
            logger.error(f"Audio upload error: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request"}, status=400)


def upload_media_to_db(request):
    """Upload audio or video to database and process automatically"""
    from core.models import MediaFile
    
    if request.method == "POST":
        media_file = request.FILES.get("media_file")
        name = request.POST.get("media_name")
        
        if not media_file or not name:
            return JsonResponse({"error": "File and name are required"}, status=400)
        
        try:
            ext = os.path.splitext(media_file.name)[1].lower()
            
            # Video file - save and process
            if ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
                save_dir = os.path.join(MEDIA_ROOT, "media_files", "videos")
                os.makedirs(save_dir, exist_ok=True)
                
                output_path = os.path.join(save_dir, f"{name}{ext}")
                with open(output_path, "wb") as f:
                    for chunk in media_file.chunks():
                        f.write(chunk)
                
                # Create MediaFile record
                media_file_obj = MediaFile.objects.create(
                    filename=name,
                    video_path=output_path,
                    status='pending'
                )
                
                # Start processing
                task = process_video_task.delay(output_path, media_file_obj.id)
                media_file_obj.task_id = task.id
                media_file_obj.status = 'processing'
                media_file_obj.save()
                
                return JsonResponse({
                    "success": True, 
                    "message": f"Video '{name}' uploaded and processing started",
                    "media_file_id": media_file_obj.id
                })
            
            # Audio file
            elif ext in [".mp3", ".wav", ".flac", ".m4a"]:
                save_dir = os.path.join(MEDIA_ROOT, "media_files", "audio")
                os.makedirs(save_dir, exist_ok=True)
                
                temp_path = os.path.join(save_dir, f"temp_{media_file.name}")
                with open(temp_path, "wb") as f:
                    for chunk in media_file.chunks():
                        f.write(chunk)
                
                output_path = os.path.join(save_dir, f"{name}.wav")
                cmd = ["ffmpeg", "-i", temp_path, "-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le", "-y", output_path]
                subprocess.run(cmd, check=True, capture_output=True)
                
                os.remove(temp_path)
                
                # Create MediaFile record and process through pipeline
                from core.tasks import process_audio_task
                media_file_obj = MediaFile.objects.create(
                    filename=name,
                    video_path=output_path,
                    status='pending'
                )
                
                # Start processing
                task = process_audio_task.delay(output_path, media_file_obj.id)
                media_file_obj.task_id = task.id
                media_file_obj.status = 'processing'
                media_file_obj.save()
                
                return JsonResponse({
                    "success": True, 
                    "message": f"Audio '{name}' uploaded and processing started",
                    "media_file_id": media_file_obj.id
                })
            
            else:
                return JsonResponse({"error": "Unsupported file format"}, status=400)
        
        except Exception as e:
            logger.error(f"Media upload error: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request"}, status=400)


def get_db_media(request):
    videos = Video.objects.all().values("id", "name", "download_date")
    audios = AudioFile.objects.all().values("id", "name", "upload_date")
    
    media_list = []
    for v in videos:
        media_list.append({
            "id": v["id"],
            "name": v["name"],
            "type": "video",
            "date": v["download_date"].strftime("%Y-%m-%d %H:%M:%S")
        })
    for a in audios:
        media_list.append({
            "id": a["id"],
            "name": a["name"],
            "type": "audio",
            "date": a["upload_date"].strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return JsonResponse({"media": media_list})


def view_db(request):
    """View all media in database"""
    return render(request, "view_db.html")


def get_all_media(request):
    """API endpoint to get all media files with status"""
    from core.models import MediaFile
    
    media_files = MediaFile.objects.all().order_by('-uploaded_at')
    
    media_list = []
    for mf in media_files:
        media_list.append({
            'id': mf.id,
            'filename': mf.filename,
            'status': mf.status,
            'progress': mf.progress,
            'uploaded_at': mf.uploaded_at.isoformat(),
            'task_id': mf.task_id
        })
    
    return JsonResponse({'media': media_list})


def search_media_files(request):
    """API endpoint to search media files by filename, person_id, or transcript content"""
    from core.models import MediaFile, DetectedPerson, Transcript
    from django.db.models import Q
    
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'media': []})
    
    # Search by filename
    filename_matches = MediaFile.objects.filter(
        filename__icontains=query
    ).distinct()
    
    # Search by person_id
    person_matches = MediaFile.objects.filter(
        detected_persons__identity__icontains=query
    ).distinct()
    
    # Search by transcript content
    transcript_matches = MediaFile.objects.filter(
        transcript__full_text__icontains=query
    ).distinct()
    
    # Combine all matches
    all_matches = (filename_matches | person_matches | transcript_matches).distinct().order_by('-uploaded_at')
    
    media_list = []
    for mf in all_matches:
        media_list.append({
            'id': mf.id,
            'filename': mf.filename,
            'status': mf.status,
            'progress': mf.progress,
            'uploaded_at': mf.uploaded_at.isoformat(),
            'task_id': mf.task_id
        })
    
    return JsonResponse({'media': media_list})


def process_db_media(request):
    if request.method == "POST":
        media_id = request.POST.get("media_id")
        media_type = request.POST.get("media_type")
        
        if not media_id or not media_type:
            return JsonResponse({"error": "Media ID and type are required"}, status=400)
        
        try:
            if media_type == "video":
                video = Video.objects.get(id=media_id)
                task = process_video_task.delay(video.file_path)
                return JsonResponse({"success": True, "task_id": task.id})
            elif media_type == "audio":
                audio = AudioFile.objects.get(id=media_id)
                from analysis_pipeline.transcriber import eat_video
                result = eat_video(audio.file_path)
                transcript = result.get("text", "") if isinstance(result, dict) else result
                
                task_id = str(uuid.uuid4())
                result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
                audio_result = {
                    "status": "ok",
                    "transcript": transcript,
                    "persons": {},
                    "video_path": None,
                    "audio_only": True
                }
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump(audio_result, f, ensure_ascii=False, indent=2)
                
                return JsonResponse({"success": True, "task_id": task_id})
        except Exception as e:
            logger.error(f"Process DB media error: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request"}, status=400)


def search_media_view(request):
    """Render search media page"""
    if request.method == "GET":
        return render(request, "search_media.html")
    
    # POST - search for person across media
    from core.models import MediaFile, DetectedPerson, TimestampLog
    
    uploaded_file = request.FILES.get("person_image")
    if not uploaded_file:
        return JsonResponse({"error": "No image uploaded"}, status=400)
    
    # Save uploaded image temporarily
    save_dir = os.path.join(MEDIA_ROOT, "temp_search")
    os.makedirs(save_dir, exist_ok=True)
    image_path = os.path.join(save_dir, uploaded_file.name)
    with open(image_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    
    try:
        # Detect face and get embeddings
        faces = detect_faces(image_path)
        if not faces:
            return JsonResponse({"error": "No face detected in uploaded image"}, status=400)
        
        face = faces[0]
        aligned_rgb = face["aligned_face"]
        
        if aligned_rgb is None or aligned_rgb.size == 0:
            return JsonResponse({"error": "Face alignment failed"}, status=400)
        
        # Get embeddings
        arc_emb, fn_emb = embedder.get_dual_embeddings(aligned_rgb)
        if arc_emb is None or fn_emb is None:
            return JsonResponse({"error": "Failed to generate embeddings"}, status=400)
        
        # Search across all stored face crops
        results = []
        
        # Get all detected persons with embeddings
        detected_persons = DetectedPerson.objects.exclude(
            arcface_embedding__isnull=True
        ).select_related('media_file')
        
        for person in detected_persons:
            # Load stored embeddings
            stored_arc = np.frombuffer(person.arcface_embedding, dtype=np.float32)
            stored_fn = np.frombuffer(person.facenet_embedding, dtype=np.float32)
            
            # Calculate similarity
            arc_sim = float(np.dot(arc_emb, stored_arc))
            fn_sim = float(np.dot(fn_emb, stored_fn))
            
            # Check if match (both models agree and pass threshold)
            if arc_sim >= 0.30 and fn_sim >= 0.30:
                # Get timestamps
                timestamps = list(person.timestamps.values('start_time', 'end_time'))
                
                results.append({
                    'media_file_id': person.media_file.id,
                    'filename': person.media_file.filename,
                    'person_identity': person.identity,
                    'confidence': (arc_sim + fn_sim) / 2.0,
                    'timestamps': timestamps
                })
        
        # Remove duplicates and sort by confidence
        unique_results = {}
        for r in results:
            key = r['media_file_id']
            if key not in unique_results or r['confidence'] > unique_results[key]['confidence']:
                unique_results[key] = r
        
        final_results = sorted(unique_results.values(), key=lambda x: x['confidence'], reverse=True)
        
        return JsonResponse({"results": final_results})
    
    except Exception as e:
        logger.exception(f"Search media error: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        # Cleanup temp file
        if os.path.exists(image_path):
            os.remove(image_path)


def view_media(request, media_file_id):
    """View processed media with annotations and transcripts"""
    from core.models import MediaFile, DetectedPerson, Transcript
    
    try:
        media_file = MediaFile.objects.get(id=media_file_id)
        
        # Get detected persons with timestamps
        persons = {}
        for person in media_file.detected_persons.all():
            timestamps = list(person.timestamps.values('start_time', 'end_time'))
            persons[person.identity] = {
                'timestamps': timestamps,
                'thumbnail': person.face_thumbnail.url if person.face_thumbnail else None
            }
        
        # Get transcript
        transcript = ""
        try:
            transcript = media_file.transcript.full_text
        except:
            pass
        
        # Get annotated video path or audio file path
        if media_file.annotated_video and media_file.annotated_video.name:
            video_path = settings.MEDIA_URL + media_file.annotated_video.name
        else:
            video_path = None
        
        # Check if this is an audio file
        is_audio = False
        if media_file.video_path:
            ext = os.path.splitext(media_file.video_path)[1].lower()
            is_audio = ext in ['.mp3', '.wav', '.flac', '.m4a']
        
        results = {
            'video_path': video_path,
            'persons': persons,
            'transcript': transcript,
            'status': media_file.status,
            'is_audio': is_audio
        }
        
        return render(request, "results.html", {
            "task_id": media_file.task_id or media_file.id,
            "results": results,
            "MEDIA_URL": settings.MEDIA_URL,
        })
    
    except MediaFile.DoesNotExist:
        return render(request, "results.html", {
            "error": "Media file not found"
        })


def stop_processing(request, media_file_id):
    """Stop processing a media file"""
    from core.models import MediaFile
    from celery.result import AsyncResult
    
    if request.method == "POST":
        try:
            media_file = MediaFile.objects.get(id=media_file_id)
            
            # Update status FIRST (so task checks and stops)
            media_file.status = 'stopped'
            media_file.save()
            
            if media_file.task_id:
                # Revoke the Celery task (terminate if running, remove if queued)
                AsyncResult(media_file.task_id).revoke(terminate=True, signal='SIGKILL')
                logger.info(f"Revoked task {media_file.task_id} for media file {media_file_id}")
            
            return JsonResponse({"success": True, "message": "Processing stopped"})
        except MediaFile.DoesNotExist:
            return JsonResponse({"error": "Media file not found"}, status=404)
        except Exception as e:
            logger.error(f"Stop processing error: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request"}, status=400)


def restart_processing(request, media_file_id):
    """Restart processing a media file"""
    from core.models import MediaFile
    
    if request.method == "POST":
        try:
            media_file = MediaFile.objects.get(id=media_file_id)
            
            # Use stored video_path
            video_path = media_file.video_path
            
            if not video_path or not os.path.exists(video_path):
                return JsonResponse({"error": "Video file not found"}, status=404)
            
            # Start new processing task
            task = process_video_task.delay(video_path, media_file.id)
            
            # Update status
            media_file.task_id = task.id
            media_file.status = 'processing'
            media_file.progress = 0
            media_file.save()
            
            return JsonResponse({"success": True, "message": "Processing restarted", "task_id": task.id})
        except MediaFile.DoesNotExist:
            return JsonResponse({"error": "Media file not found"}, status=404)
        except Exception as e:
            logger.error(f"Restart processing error: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request"}, status=400)
