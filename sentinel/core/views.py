import os, uuid, json, cv2, subprocess
from celery.result import AsyncResult
from django.conf import settings
from django.shortcuts import render, redirect
import logging
import numpy as np
from django.http import JsonResponse
from analysis_pipeline.detector import detect_faces
from analysis_pipeline.embedder import ArcFaceEmbedder
from analysis_pipeline.vector_db import ChromaDBManager
from analysis_pipeline.processor import expand_box, is_blurry, prepare_face_for_arcface
from .models import Video, AudioFile
from .tasks import process_video_task

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize DB & embedder once
embedder = ArcFaceEmbedder()
db = ChromaDBManager()

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
        task = process_video_task.delay(file_path)
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

    emb = embedder.get_embedding(aligned_rgb)
    if emb is None:
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "embedding_error": True,
        })

    match_id, distance, metadata = db.search_person(emb, k=5, threshold=0.30)
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

        # --- DEBUG: save aligned face to inspect ---
        import pathlib
        dbg_dir = pathlib.Path("/tmp/face_debug")
        dbg_dir.mkdir(parents=True, exist_ok=True)
        dbg_path = dbg_dir / f"{person_id}.jpg"

        try:
            img_to_write = cv2.cvtColor(aligned_rgb, cv2.COLOR_RGB2BGR)
            success = cv2.imwrite(str(dbg_path), img_to_write)
            if success:
                logger.info(f"[DEBUG_FILE] Saved aligned face for {person_id} at {dbg_path}")
            else:
                logger.error(f"[DEBUG_FILE] Failed to save aligned face for {person_id}")
        except Exception as e:
            logger.exception(f"[DEBUG_FILE] Exception while saving face debug for {person_id}: {e}")
        # --- end debug ---

        # Generate embedding directly from aligned RGB face
        emb = embedder.get_embedding(aligned_rgb)
        if emb is None:
            return render(request, "enroll.html", {"error": "Failed to generate embedding."})

        # Log embedding first 10 values + norm for verification
        logger.info(f"[ENROLL_DEBUG] person={person_id} emb_norm={np.linalg.norm(emb):.6f} first10={emb[:10]}")
        if emb is None:
            return render(request, "enroll.html", {"error": "Failed to generate embedding."})

        metadata = {"job": job, "age": age, "height": height, "weight": weight}
        db.add_person(person_id=person_id, embedding=emb, metadata=metadata)

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
        url = request.POST.get("youtube_url")
        name = request.POST.get("video_name")
        
        if not url or not name:
            return JsonResponse({"error": "URL and name are required"}, status=400)
        
        try:
            save_dir = os.path.join(MEDIA_ROOT, "media_files", "videos")
            os.makedirs(save_dir, exist_ok=True)
            
            output_path = os.path.join(save_dir, f"{name}.mp4")
            
            cmd = ["yt-dlp", "-f", "best", "-o", output_path, url]
            subprocess.run(cmd, check=True, capture_output=True)
            
            video = Video.objects.create(name=name, file_path=output_path)
            return JsonResponse({"success": True, "message": f"Video '{name}' downloaded successfully"})
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
