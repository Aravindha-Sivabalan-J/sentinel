# SENTINEL Face Recognition Fixes - Complete Summary

## Overview
Fixed critical issues in face enrollment and video processing that caused poor face crops, zero embeddings, and incorrect matches.

---

## Problem 1: Poor Enrollment Face Crops ✅ FIXED

### Symptoms
- `/tmp/face_debug/` images showed incomplete faces
- Black regions in saved crops
- Wrong matches during search
- Faces not properly aligned

### Root Cause
**Coordinate mismatch between detector and alignment:**
```python
# WRONG FLOW
faces = detect_faces(image_path)
box, landmarks = face["box"], face["landmarks"]  # Landmarks in ORIGINAL coords
x1, y1, x2, y2 = expand_box(box, ...)
crop = image[y1:y2, x1:x2]  # Crop from original image
aligned = embedder.align_face(crop, landmarks)  # ❌ Landmarks outside crop!
```

### Solution
Use detector's pre-aligned faces:
```python
# CORRECT FLOW
faces = detect_faces(image_path)
aligned_rgb = face["aligned_face"]  # ✅ Already aligned 112×112 RGB
emb = embedder.get_embedding(aligned_rgb)
```

### Files Changed
- `sentinel/core/views.py` - Both `enroll_view()` and `home_view()`
- `sentinel/analysis_pipeline/detector.py` - Added proper ArcFace alignment

---

## Problem 2: Zero Embeddings in Video Processing ✅ FIXED

### Symptoms
```
[EMB] norm=0.000000 first10=[0.0, 0.0, 0.0, ...]
❌ No verified match (best=Dwayne_johnson, sim=0.0000)
```

### Root Cause
**Double color conversion causing channel swap:**
```python
# WRONG FLOW
crop = frame[y1:y2, x1:x2]  # BGR from video
input_blob = prepare_face_for_arcface(crop)  # BGR→RGB conversion
emb = embedder.get_embedding(input_blob)  # ANOTHER BGR→RGB! ❌
```

The embedder's `preprocess_face()` did:
```python
face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
```
But input was **already RGB**, causing wrong color channels → zero embeddings.

### Solution
**Unified preprocessing pipeline:**
```python
# CORRECT FLOW
crop = frame[y1:y2, x1:x2]
faces = detect_faces(crop)  # Returns aligned RGB faces
aligned_rgb = faces[0]["aligned_face"]
emb = embedder.get_embedding(aligned_rgb)  # ✅ Correct preprocessing
```

### Files Changed
- `sentinel/analysis_pipeline/processor.py` - Use detector for alignment
- `sentinel/analysis_pipeline/embedder.py` - Fixed RGB handling

---

## Technical Architecture

### Unified Pipeline (Enrollment + Video)
```
┌─────────────────────────────────────────────────────────────┐
│ 1. Input: Image/Frame (BGR from OpenCV)                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. detector.detect_faces()                                   │
│    - YOLO detects face + 5 landmarks                        │
│    - Landmarks in ORIGINAL image coordinates                │
│    - Apply SimilarityTransform to ArcFace template          │
│    - Output: 112×112 RGB aligned face                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. embedder.get_embedding(aligned_rgb)                      │
│    - preprocess_face():                                     │
│      • Resize to 112×112 (if needed)                        │
│      • Normalize: (pixel - 127.5) / 128.0 → [-1, +1]       │
│      • Transpose: (H,W,C) → (C,H,W)                         │
│      • Add batch: (C,H,W) → (1,C,H,W)                       │
│    - Run ONNX model: (1,3,112,112) → (1,512)               │
│    - L2 normalize: emb / ||emb|| → unit vector             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Output: 512-D embedding (norm=1.0)                       │
└─────────────────────────────────────────────────────────────┘
```

### ArcFace 5-Point Template
```python
ARCFACE_DST = np.array([
    [38.2946, 51.6963],  # left eye
    [73.5318, 51.5014],  # right eye
    [56.0252, 71.7366],  # nose
    [41.5493, 92.3655],  # left mouth corner
    [70.7299, 92.2041]   # right mouth corner
], dtype=np.float32)
```

---

## Verification Checklist

### ✅ Enrollment
1. Go to `/enroll` page
2. Upload clear face photo
3. Check `/tmp/face_debug/{person_id}.jpg`:
   - Should be **full face** (not cropped)
   - **No black regions**
   - **112×112 pixels**
   - Properly aligned (eyes horizontal)
4. Check logs:
   ```
   [EMB] norm=1.0000 first10=[0.123, -0.456, ...]  ✅
   ```

### ✅ Image Search
1. Upload same person's photo to home page
2. Should match with **distance < 0.4**
3. Check logs show non-zero embeddings

### ✅ Video Processing
1. Enroll person (e.g., Kevin Hart)
2. Upload video of that person
3. Check Celery logs:
   ```
   [EMB] norm=1.0000 first10=[...]  ✅
   ✅ Verified match: Kevin_Hart (sim=0.8234)
   ```
4. NOT:
   ```
   [EMB] norm=0.0000 first10=[0.0, ...]  ❌
   ❌ No verified match (best=wrong_person, sim=0.0000)
   ```

---

## Key Insights

### Why Coordinate Mismatch Happened
- YOLO returns landmarks in **original image coordinates**
- Cropping the image creates a **new coordinate system**
- Using original landmarks on cropped image = misalignment
- Solution: Align **before** cropping, using original coordinates

### Why Color Conversion Failed
- Detector outputs RGB (standard for deep learning)
- Embedder assumed BGR input (OpenCV default)
- Double conversion: RGB → (treated as BGR) → RGB = BGR output
- ArcFace trained on RGB, got BGR → garbage embeddings
- Solution: Embedder accepts RGB directly

### Why Consistency Matters
- Enrollment and search **must use identical preprocessing**
- Different pipelines = different embeddings = no matches
- Now both use: `detector → embedder` (same flow)

---

## Performance Expectations

### Good Embeddings
- **Norm:** ~1.0 (after L2 normalization)
- **Values:** Mix of positive/negative floats
- **Range:** Typically [-0.5, +0.5] after normalization

### Same Person Match
- **Cosine similarity:** > 0.6 (typically 0.7-0.9)
- **Distance:** < 0.4 (distance = 1 - similarity)

### Different Person
- **Cosine similarity:** < 0.5
- **Distance:** > 0.5

---

## Files Modified

### Core Application
- `sentinel/core/views.py`
  - `enroll_view()` - Use detector's aligned faces
  - `home_view()` - Use detector's aligned faces

### Analysis Pipeline
- `sentinel/analysis_pipeline/detector.py`
  - Added proper ArcFace alignment with SimilarityTransform
  - Returns 112×112 RGB aligned faces
  
- `sentinel/analysis_pipeline/embedder.py`
  - Fixed `preprocess_face()` to handle RGB input
  - Removed incorrect BGR→RGB conversion
  
- `sentinel/analysis_pipeline/processor.py`
  - Use `detect_faces()` for video frame alignment
  - Removed manual `prepare_face_for_arcface()`

### Documentation
- `ENROLLMENT_FIX.md` - Enrollment coordinate fix details
- `VIDEO_PROCESSING_FIX.md` - Zero embedding fix details
- `FIXES_SUMMARY.md` - This file

### Testing
- `sentinel/test_enrollment_fix.py` - Test script for verification

---

## Troubleshooting

### Still Getting Zero Embeddings?
1. Check input is RGB: `print(face.shape, face.dtype)`
2. Check normalization: Values should be in [-1, +1]
3. Check ONNX model path is correct
4. Verify CUDA/CPU provider is working

### Still Getting Wrong Matches?
1. Clear ChromaDB: Delete `chroma_data/` folder
2. Re-enroll all persons
3. Check threshold (default 0.62, try 0.55-0.65)
4. Verify embeddings have norm=1.0

### Poor Face Alignment?
1. Check landmarks are detected (5 points)
2. Verify image quality (not blurry, good lighting)
3. Check face is frontal (not profile view)
4. Ensure face is large enough in image

---

## Credits
Fixed by analyzing the complete pipeline flow and identifying:
1. Coordinate system mismatches
2. Color space conversion errors
3. Preprocessing inconsistencies

All fixes maintain minimal code changes while ensuring correctness.
