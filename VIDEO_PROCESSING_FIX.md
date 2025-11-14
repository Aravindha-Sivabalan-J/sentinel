# Video Processing Zero Embedding Fix

## Problem
When processing videos, all embeddings were **zero vectors** (norm=0.000000), causing:
- No matches found (always "NO MATCH FOUND")
- Wrong person shown as "best match" with sim=0.0000
- All faces labeled as "Unknown"

## Root Cause Analysis

### Issue 1: Double Preprocessing in processor.py
```python
# OLD CODE (WRONG)
crop = frame[y1:y2, x1:x2]  # Raw BGR crop from video frame
input_blob = prepare_face_for_arcface(crop)  # Converts BGR→RGB, resizes, creates blob
emb = embedder.get_embedding(input_blob)  # Does ANOTHER BGR→RGB conversion!
```

**Problem:** The embedder's `preprocess_face()` was doing `cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)` on an image that was **already RGB**, causing color channel swap and zero embeddings.

### Issue 2: Not Using Detector's Alignment
The video processing was:
1. Getting raw crop from tracker bounding box
2. Manually preprocessing with `prepare_face_for_arcface()`
3. Missing proper face alignment (no landmarks used)

But enrollment was:
1. Using detector's properly aligned faces
2. Getting correct embeddings

This **inconsistency** meant enrollment and search used different preprocessing pipelines!

## Solution

### 1. Fixed processor.py
**Before:**
```python
crop = frame[y1:y2, x1:x2]
input_blob = prepare_face_for_arcface(crop)
emb = embedder.get_embedding(input_blob)
```

**After:**
```python
crop = frame[y1:y2, x1:x2]
faces = detect_faces(crop)  # Detect + align face properly
if not faces:
    continue
aligned_rgb = faces[0]["aligned_face"]  # Already 112x112 RGB
emb = embedder.get_embedding(aligned_rgb)  # Correct preprocessing
```

### 2. Fixed embedder.py
**Before:**
```python
def preprocess_face(self, face_img):
    # ...
    face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)  # ❌ Assumes BGR input
```

**After:**
```python
def preprocess_face(self, face_img):
    # Input is already RGB from detector
    if face_img.shape[:2] != (112, 112):
        resized = cv2.resize(face_img, (112, 112))
    else:
        resized = face_img  # ✅ No color conversion needed
```

### 3. Unified Pipeline
Now **both enrollment and video processing** use the same flow:
```
detector.detect_faces() 
  → Returns aligned 112×112 RGB face
  → embedder.get_embedding(aligned_rgb)
    → preprocess_face() normalizes to [-1,+1]
    → ONNX model generates embedding
    → L2 normalize to unit vector
```

## Technical Details

### Why Zero Embeddings Happened
1. Detector returns RGB: `[R, G, B]` channels
2. Embedder did `cv2.cvtColor(img, cv2.COLOR_BGR2RGB)` 
3. OpenCV interprets input as BGR and swaps: `[B, G, R]` → `[R, G, B]`
4. But input was already RGB, so result is: `[B, G, R]` (wrong!)
5. ArcFace model trained on RGB gets wrong color channels
6. Outputs garbage → zero vector after normalization

### Correct Preprocessing Flow
```
Input: RGB uint8 (112, 112, 3) in range [0, 255]
  ↓
Normalize: (pixel - 127.5) / 128.0  → range [-1, +1]
  ↓
Transpose: (H, W, C) → (C, H, W)
  ↓
Add batch: (C, H, W) → (1, C, H, W)
  ↓
ONNX model: (1, 3, 112, 112) → (1, 512)
  ↓
L2 normalize: embedding / ||embedding||
  ↓
Output: float32 (512,) with norm=1.0
```

## Verification

### Check Embeddings Are Non-Zero
Look for logs like:
```
[EMB] shape=(512,) dtype=float32 norm=1.0000 first10=[0.123, -0.456, ...]
```

NOT:
```
[EMB] shape=(512,) dtype=float32 norm=0.0000 first10=[0.0, 0.0, ...]
```

### Check Matches Work
```
✅ Verified match: Kevin_Hart (sim=0.8234)
```

NOT:
```
❌ No verified match (best=Dwayne_johnson, sim=0.0000)
```

## Files Modified
1. `sentinel/analysis_pipeline/processor.py` - Use detector for video frames
2. `sentinel/analysis_pipeline/embedder.py` - Fixed RGB handling
3. `sentinel/core/views.py` - Already fixed in previous commit

## Testing
1. Enroll Kevin Hart
2. Upload video of Kevin Hart
3. Should see matches with sim > 0.6
4. Check logs show norm=1.0 (not 0.0)
