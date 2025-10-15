import os, uuid, json, cv2
from celery.result import AsyncResult
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from analysis_pipeline.detector import detect_faces
from analysis_pipeline.embedder import ArcFaceEmbedder
from analysis_pipeline.vector_db import ChromaDBManager
from analysis_pipeline.processor import expand_box, is_blurry, prepare_face_for_arcface

from .tasks import process_video_task

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
    box, landmarks = face["box"], face["landmarks"]
    image = cv2.imread(file_path)
    if image is None:
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "read_error": True,
        })

    x1, y1, x2, y2 = expand_box(box, image.shape, margin=0.18)
    crop = image[y1:y2, x1:x2]
    if is_blurry(crop, thresh=50):
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "blurry": True,
        })

    aligned = embedder.align_face(crop, landmarks)
    emb = embedder.get_embedding(aligned)
    if emb is None:
        return render(request, "image_result.html", {
            "media_url": os.path.relpath(file_path, MEDIA_ROOT),
            "embedding_error": True,
        })

    match_id, distance, metadata = db.search_person(
        emb, k=5, threshold=0.4, verify_top_k=3
    )

    match_id, distance, metadata = db.search_person(
        emb, k=5, threshold=0.4, verify_top_k=3
    )
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
        box, landmarks = face["box"], face["landmarks"]
        image = cv2.imread(image_path)
        if image is None:
            return render(request, "enroll.html", {"error": "Failed to read uploaded image."})

        x1, y1, x2, y2 = expand_box(box, image.shape, margin=0.18)
        crop = image[y1:y2, x1:x2]
        aligned = embedder.align_face(crop, landmarks)
        emb = embedder.get_embedding(prepare_face_for_arcface(aligned))
        if emb is None:
            return render(request, "enroll.html", {"error": "Failed to generate embedding."})

        metadata = {"job": job, "age": age, "height": height, "weight": weight}
        db.add_person(person_id=person_id, embedding=emb, metadata=metadata)

        return render(request, "enroll.html", {"success": f"Enrolled {person_id} successfully!"})


def task_status(request, task_id):
    result = AsyncResult(task_id)
    if not result.ready():
        return JsonResponse({"state": result.state})

    results_file = os.path.join(RESULTS_DIR, f"{task_id}.json")
    if os.path.exists(results_file):
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "error":
            return JsonResponse({"state": "ERROR", "message": data.get("error")})
        return JsonResponse({"state": "SUCCESS", "results": data})
    return JsonResponse({"state": "ERROR", "message": "No results file found"})
