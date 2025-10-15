# analysis_pipeline/preprocess.py
import cv2
import numpy as np
from skimage import transform as trans

ARCFACE_DST = np.array([
    [38.2946, 51.6963], [73.5318, 51.5014],
    [56.0252, 71.7366], [41.5493, 92.3655],
    [70.7299, 92.2041]], dtype=np.float32)

def canonical_align_and_blob(image_bgr, landmarks=None, target_size=(112,112)):
    """
    Returns (blob, aligned_rgb_uint8)
    - blob: np.float32 shaped (1,3,H,W) with pixel range 0..255 (float32), contiguous
    - aligned_rgb_uint8: HWC uint8 RGB image
    landmarks: dict with keys left_eye,right_eye,nose,mouth_left,mouth_right (absolute coords)
    """
    H, W = target_size
    if landmarks:
        src = np.array([
            landmarks['left_eye'],
            landmarks['right_eye'],
            landmarks['nose'],
            landmarks['mouth_left'],
            landmarks['mouth_right']], dtype=np.float32)
        try:
            tform = trans.SimilarityTransform()
            tform.estimate(src, ARCFACE_DST)
            M = tform.params[0:2, :]
            aligned = cv2.warpAffine(image_bgr, M, (W, H), borderValue=0)
        except Exception:
            aligned = cv2.resize(image_bgr, (W, H), interpolation=cv2.INTER_LINEAR)
    else:
        aligned = cv2.resize(image_bgr, (W, H), interpolation=cv2.INTER_LINEAR)

    # BGR -> RGB uint8
    try:
        aligned_rgb = cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB)
    except Exception:
        aligned_rgb = aligned

    # Build blob (1,3,H,W) float32 but keep 0..255 range
    blob = aligned_rgb.astype(np.float32)
    blob = np.transpose(blob, (2, 0, 1))[None, ...]  # (1,3,H,W)
    blob = np.ascontiguousarray(blob, dtype=np.float32)
    return blob, aligned_rgb
