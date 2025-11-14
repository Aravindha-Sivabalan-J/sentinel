import cv2
import numpy as np

def expand_box(x1, y1, x2, y2, img_w, img_h, factor=0.2):
    """Expand bounding box by factor while keeping within image bounds"""
    w = x2 - x1
    h = y2 - y1
    dx = int(w * factor / 2)
    dy = int(h * factor / 2)
    
    x1 = max(0, x1 - dx)
    y1 = max(0, y1 - dy)
    x2 = min(img_w, x2 + dx)
    y2 = min(img_h, y2 + dy)
    
    return x1, y1, x2, y2

def is_blurry(image, thresh=100):
    """Check if image is blurry using Laplacian variance"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image
    
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var < thresh

def prepare_face_for_arcface(face_image, target_size=(112, 112)):
    """Prepare face image for ArcFace model input"""
    if face_image.shape[:2] != target_size:
        face_image = cv2.resize(face_image, target_size)
    
    # Convert to float32 and normalize
    face_blob = face_image.astype(np.float32)
    face_blob = np.transpose(face_blob, (2, 0, 1))
    face_blob = np.expand_dims(face_blob, axis=0)
    
    return np.ascontiguousarray(face_blob, dtype=np.float32)
