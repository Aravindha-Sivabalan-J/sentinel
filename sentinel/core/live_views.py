import cv2
import os
import time
import threading
import logging
import requests
import numpy as np
from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
from analysis_pipeline.detector import detect_faces
from analysis_pipeline.dual_embedder import DualEmbedder
from analysis_pipeline.dual_vector_db import DualChromaDBManager

logger = logging.getLogger(__name__)

# Initialize (lazy loading)
embedder = DualEmbedder()
db = DualChromaDBManager()

# Globals - IP Webcam configuration
CAMERA_URL = 'http://192.168.1.40:8080'
VIDEO_STREAM_URL = f'{CAMERA_URL}/shot.jpg'
camera = None
detected_faces_info = []
frame_lock = threading.Lock()
camera_lock = threading.Lock()
stream_active = {}


def live_detection_view(request):
    """Render live detection page"""
    return render(request, "live_detection.html")


def get_camera():
    """Get or create camera connection"""
    global camera
    
    with camera_lock:
        if camera is None or not camera.isOpened():
            # Create new connection - IP Webcam uses /video endpoint
            cam = cv2.VideoCapture(VIDEO_STREAM_URL)
            cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not cam.isOpened():
                logger.error(f"Cannot connect to IP Webcam at {CAMERA_URL}")
                return None
            
            camera = cam
            logger.info(f"Connected to IP Webcam")
        
        return camera


def generate_frames():
    """Generate frames with face detection using snapshot method"""
    global detected_faces_info
    
    stream_id = id(threading.current_thread())
    stream_active[stream_id] = True
    
    try:
        while stream_active.get(stream_id, False):
            try:
                # Fetch frame from IP Webcam
                response = requests.get(VIDEO_STREAM_URL, timeout=10)
                if response.status_code != 200:
                    logger.error(f"Failed to get frame: {response.status_code}")
                    time.sleep(0.1)
                    continue
                
                # Decode frame
                img_array = np.frombuffer(response.content, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                
                if frame is None:
                    logger.error("Failed to decode frame")
                    time.sleep(0.1)
                    continue
                
                # Resize for faster processing
                frame = cv2.resize(frame, (960, 540))
                
                # Run face detection
                try:
                    faces = detect_faces(frame)
                    detected_faces_info = []
                    
                    for face in faces:
                        if 'box' not in face or 'aligned_face' not in face:
                            continue
                        
                        x1, y1, x2, y2 = map(int, face['box'])
                        aligned_rgb = face['aligned_face']
                        
                        if aligned_rgb is not None and aligned_rgb.size > 0:
                            arc_emb, fn_emb = embedder.get_dual_embeddings(aligned_rgb)
                            
                            if arc_emb is not None and fn_emb is not None:
                                match_id, distance, metadata = db.search_person(arc_emb, fn_emb, k=5, arc_threshold=0.30, fn_threshold=0.30)
                                
                                if match_id != "NO MATCH FOUND":
                                    label = match_id
                                    confidence = 1.0 - distance if distance else 0.0
                                    color = (0, 255, 0)
                                else:
                                    label = "Unknown"
                                    confidence = 0.0
                                    color = (0, 0, 255)
                                
                                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                                cv2.putText(frame, f"{label} ({confidence:.2f})", (x1, y1 - 10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                                
                                detected_faces_info.append({'name': label, 'confidence': confidence})
                except Exception as e:
                    logger.debug(f"Face detection error: {e}")
                
                # Encode frame
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                
                time.sleep(0.033)  # ~30 FPS
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Frame error: {e}")
                time.sleep(0.1)
    finally:
        stream_active.pop(stream_id, None)


def live_feed(request):
    """Stream live video feed"""
    response = StreamingHttpResponse(generate_frames(),
                                    content_type='multipart/x-mixed-replace; boundary=frame')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def live_faces(request):
    """Return detected faces info as JSON"""
    global detected_faces_info
    return JsonResponse({'faces': detected_faces_info})
