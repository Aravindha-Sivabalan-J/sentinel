# analysis_pipeline/detector.py
import logging
import os
import cv2
import numpy as np
from ultralytics import YOLO
from skimage import transform as trans

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- Lazy Loading for YOLOv8 Face Model ---
yolo_model = None
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(SCRIPT_DIR, "models", "yolov8n-face.pt")

def load_yolo_model():
    """Load YOLO model on-demand"""
    global yolo_model
    if yolo_model is None:
        try:
            if not os.path.exists(model_path):
                logger.error(f"FATAL: YOLOv8 model not found at {model_path}")
                return None
            yolo_model = YOLO(model_path)
            logger.info(f"YOLOv8 face detection model loaded from {model_path}")
        except Exception as e:
            logger.exception("Failed to load YOLOv8 model:")
            return None
    return yolo_model

def unload_yolo_model():
    """Clear YOLO model from GPU memory"""
    global yolo_model
    if yolo_model is not None:
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            del yolo_model
            yolo_model = None
            logger.info("YOLOv8 model unloaded from GPU")
        except Exception as e:
            logger.warning(f"Error unloading YOLO model: {e}")

# ArcFace standard 5-point template
ARCFACE_DST = np.array([
    [38.2946, 51.6963], [73.5318, 51.5014],
    [56.0252, 71.7366], [41.5493, 92.3655],
    [70.7299, 92.2041]], dtype=np.float32)


def detect_faces(image_input):
    """
    Detect faces using YOLOv8n-face and align to ArcFace standard template.
    Returns list with aligned 112x112 RGB faces ready for embedding.
    """
    model = load_yolo_model()
    if model is None:
        logger.error("YOLOv8 model not loaded.")
        return []

    try:
        if isinstance(image_input, str):
            image = cv2.imread(image_input)
            if image is None:
                logger.error(f"Failed to read image from path: {image_input}")
                return []
        else:
            image = np.copy(image_input)

        if image.dtype != np.uint8:
            image = np.clip(image * 255.0, 0, 255).astype(np.uint8)

        results = model(image, conf=0.4, verbose=False, device='cuda' if __import__('torch').cuda.is_available() else 'cpu')
        detected_faces = []

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            landmarks = result.keypoints.xy.cpu().numpy() if result.keypoints is not None else [None] * len(boxes)

            for box, lm in zip(boxes, landmarks):
                x1, y1, x2, y2 = map(int, box)
                
                # Expand box by 15% for better face capture
                h, w = image.shape[:2]
                bw, bh = x2 - x1, y2 - y1
                margin = 0.15
                x1 = max(0, int(x1 - bw * margin))
                y1 = max(0, int(y1 - bh * margin))
                x2 = min(w, int(x2 + bw * margin))
                y2 = min(h, int(y2 + bh * margin))
                
                landmark_dict = {}
                if lm is not None:
                    landmark_dict = {
                        "left_eye": lm[0].tolist(),
                        "right_eye": lm[1].tolist(),
                        "nose": lm[2].tolist(),
                        "mouth_left": lm[3].tolist(),
                        "mouth_right": lm[4].tolist(),
                    }

                # Align face using landmarks in ORIGINAL image coordinates
                aligned_rgb = None
                if landmark_dict:
                    try:
                        src = np.array([
                            landmark_dict['left_eye'],
                            landmark_dict['right_eye'],
                            landmark_dict['nose'],
                            landmark_dict['mouth_left'],
                            landmark_dict['mouth_right']
                        ], dtype=np.float32)
                        
                        tform = trans.SimilarityTransform()
                        tform.estimate(src, ARCFACE_DST)
                        M = tform.params[0:2, :]
                        aligned_bgr = cv2.warpAffine(image, M, (112, 112), borderValue=0)
                        aligned_rgb = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB)
                    except Exception as e:
                        logger.warning(f"Alignment failed, using resized crop: {e}")
                
                # Fallback: simple crop + resize
                if aligned_rgb is None:
                    crop = image[y1:y2, x1:x2]
                    if crop.size > 0:
                        resized = cv2.resize(crop, (112, 112))
                        aligned_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    else:
                        continue

                detected_faces.append({
                    "box": [x1, y1, x2, y2],
                    "aligned_face": aligned_rgb,
                    "landmarks": landmark_dict
                })

        return detected_faces

    except Exception as e:
        logger.exception("YOLO face detection failed:")
        return []
