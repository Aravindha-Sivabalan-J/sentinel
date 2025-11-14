# Enrollment Face Cropping Fix

## Problem
When enrolling faces, the saved debug images at `/tmp/face_debug/` showed:
- Incomplete faces (missing parts)
- Black regions
- Poor quality crops
- Wrong matches during search

## Root Cause
The enrollment flow had **coordinate mismatch issues**:

1. **Detector** returned landmarks in **original image coordinates**
2. **views.py** was calling `expand_box()` to crop the face
3. Then trying to use `embedder.align_face()` with the **original landmarks** on the **cropped image**
4. This caused misalignment because landmarks were outside the crop boundaries

## Solution

### 1. Fixed `detector.py`
- Now performs **proper ArcFace alignment** using the standard 5-point template
- Uses landmarks in **original image coordinates** (correct)
- Outputs **112×112 RGB aligned faces** ready for embedding
- No need for additional alignment steps

### 2. Fixed `views.py` (enroll_view)
**Before:**
```python
box, landmarks = face["box"], face["landmarks"]
x1, y1, x2, y2 = expand_box(box, image.shape, margin=0.18)
crop = image[y1:y2, x1:x2]
aligned_rgb = embedder.align_face(crop, landmarks)  # ❌ Wrong coordinates!
```

**After:**
```python
aligned_rgb = face["aligned_face"]  # ✅ Already aligned by detector
```

### 3. Fixed `views.py` (home_view)
Same fix applied to image search flow for consistency.

## Technical Details

### ArcFace Alignment Process
1. YOLO detects face + 5 landmarks (eyes, nose, mouth corners)
2. Landmarks are in **original image coordinates**
3. Use `SimilarityTransform` to map landmarks to standard template:
   ```
   [38.29, 51.70]  # left eye
   [73.53, 51.50]  # right eye
   [56.03, 71.74]  # nose
   [41.55, 92.37]  # left mouth
   [70.73, 92.20]  # right mouth
   ```
4. Apply transformation to get **112×112 aligned face**
5. Convert BGR → RGB for ArcFace model

### Why This Matters
- **Consistent alignment** = better embeddings
- **Proper face crops** = accurate recognition
- **No coordinate mismatches** = reliable matching

## Testing

### 1. Test Detection
```bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python test_enrollment_fix.py
```

### 2. Enroll Someone
1. Go to `/enroll` page
2. Upload a clear face image
3. Fill in metadata
4. Check `/tmp/face_debug/{person_id}.jpg`
5. Should see **full, properly aligned 112×112 face**

### 3. Verify Search
1. Upload same person's photo to home page
2. Should match correctly with low distance (<0.4)

## Files Modified
- `sentinel/core/views.py` - Fixed enrollment and search flows
- `sentinel/analysis_pipeline/detector.py` - Added proper ArcFace alignment
- `sentinel/test_enrollment_fix.py` - New test script

## Expected Results
✅ Full faces in debug images  
✅ No black regions  
✅ Consistent 112×112 size  
✅ Accurate matching (distance < 0.4 for same person)  
✅ No false positives  
