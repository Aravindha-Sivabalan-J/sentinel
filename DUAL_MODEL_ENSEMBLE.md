# Dual-Model Ensemble Face Recognition System

## Overview
The SENTINEL system has been enhanced with a dual-model ensemble approach that uses both **ArcFace** and **FaceNet-512** models for improved face recognition accuracy.

## Key Changes

### 1. New Components Added

#### `analysis_pipeline/dual_embedder.py`
- Handles both ArcFace (112x112) and FaceNet-512 (160x160) models
- Generates dual embeddings simultaneously for each face
- Both embeddings are L2-normalized for consistency

#### `analysis_pipeline/dual_vector_db.py`
- Manages two separate ChromaDB collections:
  - `arcface_faces` - stores ArcFace embeddings
  - `facenet_faces` - stores FaceNet-512 embeddings
- Implements ensemble matching logic:
  - Both models must agree on the same person ID
  - Both similarity scores must pass their respective thresholds
  - Returns average similarity score for matched faces

#### `migrate_to_dual_db.py`
- Migration script to delete old `face_embeddings` collection
- Creates new dual collections
- Run once before using the system

### 2. Modified Components

#### `analysis_pipeline/processor.py`
- Updated to use `DualEmbedder` and `DualChromaDBManager`
- Enrollment generates both ArcFace and FaceNet-512 embeddings
- Video processing uses dual embeddings for face matching

#### `core/views.py`
- Updated enrollment view to generate dual embeddings
- Image recognition uses ensemble matching
- Maintains same user interface and functionality

### 3. Model Requirements

- **ArcFace**: `analysis_pipeline/models/arcface.onnx` (112x112 input)
- **FaceNet-512**: `analysis_pipeline/models/facenet512.onnx` (160x160 input) ✅ Already present

## How It Works

### Enrollment Process
1. User uploads image with person's face
2. Face is detected and aligned using YOLOv8
3. Aligned face (RGB) is processed by both models:
   - Resized to 112x112 → ArcFace embedding (512-D)
   - Resized to 160x160 → FaceNet-512 embedding (512-D)
4. Both embeddings stored in separate collections with same person ID

### Recognition Process
1. New face detected in image/video
2. Dual embeddings generated for the face
3. Both collections queried independently
4. Ensemble decision:
   - ✅ MATCH if: same person ID from both + both scores pass thresholds
   - ❌ NO MATCH if: different IDs or low confidence from either model

### Ensemble Logic (Simple Rule-Based)
```python
# Both models must agree
if arcface_match_id == facenet_match_id:
    # Both scores must pass thresholds
    if arcface_similarity >= 0.30 and facenet_similarity >= 0.30:
        return MATCH
return NO_MATCH
```

## Setup Instructions

### 1. Run Migration Script
```bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python migrate_to_dual_db.py
```

### 2. Re-enroll All Persons
Since the database structure changed, you need to re-enroll all persons:
- Go to `/enroll/` endpoint
- Upload each person's image again
- System will generate dual embeddings automatically

### 3. Start Using the System
All existing functionality works as before:
- Upload videos for face recognition + transcription
- Upload images for face recognition
- Enroll new persons

## Configuration

### Similarity Thresholds
Adjust in `dual_vector_db.py` → `search_person()` method:
```python
arc_threshold=0.30  # ArcFace threshold (default: 0.30)
fn_threshold=0.30   # FaceNet-512 threshold (default: 0.30)
```

### Ensemble Strategy
Current: Both models must agree (conservative approach)

Future improvements could include:
- Weighted voting based on confidence scores
- Machine learning classifier trained on dual embeddings
- Adaptive thresholds per person

## Benefits

1. **Higher Accuracy**: Two models reduce false positives
2. **Robustness**: Different model architectures complement each other
3. **Confidence**: Agreement between models increases trust
4. **Flexibility**: Easy to adjust thresholds per model

## Unchanged Components

- ✅ Celery task queue (no changes)
- ✅ RabbitMQ configuration (no changes)
- ✅ Face detection (YOLOv8)
- ✅ Face tracking (ByteTrack)
- ✅ Audio transcription (Whisper.cpp)
- ✅ Django views and templates
- ✅ User interface

## Testing

### Test Enrollment
```bash
# Access enrollment page
http://localhost:8000/enroll/

# Upload image with single face
# Check logs for dual embedding generation
```

### Test Recognition
```bash
# Upload video or image
http://localhost:8000/

# System will use dual-model matching
# Check logs for ensemble decisions
```

## Logs to Monitor

```
[DUAL_EMB] ArcFace: shape=(512,), norm=1.0000
[DUAL_EMB] FaceNet: shape=(512,), norm=1.0000
[SEARCH] ArcFace: alice_001 (sim=0.8523)
[SEARCH] FaceNet: alice_001 (sim=0.8712)
✅ MATCH: alice_001 (avg_sim=0.8618)
```

## Troubleshooting

### Issue: "Models not initialized"
- Check that `facenet512.onnx` exists in `analysis_pipeline/models/`
- Verify ONNX runtime is installed: `pip install onnxruntime-gpu` or `onnxruntime`

### Issue: "No results from collection"
- Run migration script to create collections
- Re-enroll at least one person

### Issue: "Models disagree"
- Normal behavior - means models detected different persons
- Consider adjusting thresholds if too strict
- Check face quality (blur, lighting, angle)

## Performance Notes

- Dual embedding generation takes ~2x time vs single model
- Video processing optimized: processes every 2nd frame
- GPU acceleration recommended for real-time performance
- Memory usage: ~2x for storing dual embeddings

## Future Enhancements

1. Train ML classifier on dual embeddings (SVM, Random Forest)
2. Add confidence scores to UI
3. Per-person threshold tuning
4. Model performance analytics dashboard
5. Support for additional models (3+ ensemble)
