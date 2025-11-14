# Quick Start: Dual-Model Ensemble System

## Step-by-Step Setup

### 1. Verify Models
```bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
ls -lh analysis_pipeline/models/*.onnx
```
Expected output:
- `arcface.onnx` (249M) ✅
- `facenet512.onnx` (91M) ✅

### 2. Test Dual Embedder
```bash
python test_dual_embedder.py
```
Expected output:
```
✅ Models loaded successfully
✅ ArcFace embedding: shape=(512,), norm=1.0000
✅ FaceNet embedding: shape=(512,), norm=1.0000
✅ Dual embedder test PASSED!
```

### 3. Migrate Database
```bash
python migrate_to_dual_db.py
```
Expected output:
```
✅ Deleted old 'face_embeddings' collection
✅ Created 'arcface_faces' collection
✅ Created 'facenet_faces' collection
✅ Migration complete!
```

### 4. Start Services
```bash
# Terminal 1: Start RabbitMQ (if not running)
sudo systemctl start rabbitmq-server

# Terminal 2: Start Celery worker
celery -A sentinel worker --loglevel=info

# Terminal 3: Start Django server
python manage.py runserver
```

### 5. Re-enroll Persons
1. Open browser: `http://localhost:8000/enroll/`
2. For each person:
   - Enter Person ID (e.g., "alice_001")
   - Fill in metadata (job, age, height, weight)
   - Upload clear face image
   - Click "Enroll"
3. Check logs for:
   ```
   [DUAL_EMB] ArcFace: shape=(512,), norm=1.0000
   [DUAL_EMB] FaceNet: shape=(512,), norm=1.0000
   ✅ Added alice_001 to both collections
   ```

### 6. Test Recognition

#### Test with Image:
1. Go to: `http://localhost:8000/`
2. Upload image with enrolled person's face
3. Check result page for match

#### Test with Video:
1. Go to: `http://localhost:8000/`
2. Upload video (10-30 seconds recommended)
3. Wait for processing (check Celery logs)
4. View results with annotated video

### 7. Monitor Logs

Watch for ensemble decisions:
```
[SEARCH] ArcFace: alice_001 (sim=0.8523)
[SEARCH] FaceNet: alice_001 (sim=0.8712)
✅ MATCH: alice_001 (avg_sim=0.8618)
```

Or disagreements:
```
[SEARCH] ArcFace: alice_001 (sim=0.8523)
[SEARCH] FaceNet: bob_002 (sim=0.7234)
❌ Models disagree: ArcFace=alice_001, FaceNet=bob_002
```

## Key Files Modified

| File | Change |
|------|--------|
| `analysis_pipeline/dual_embedder.py` | NEW - Dual model handler |
| `analysis_pipeline/dual_vector_db.py` | NEW - Dual collection manager |
| `analysis_pipeline/processor.py` | MODIFIED - Uses dual embeddings |
| `core/views.py` | MODIFIED - Uses dual embeddings |
| `migrate_to_dual_db.py` | NEW - Database migration |

## Troubleshooting

### Models not loading?
```bash
# Check ONNX runtime
pip install onnxruntime-gpu  # For GPU
# OR
pip install onnxruntime  # For CPU
```

### No matches found?
- Re-enroll persons after migration
- Check similarity thresholds (default: 0.30 for both)
- Verify face quality (lighting, angle, resolution)

### Models always disagree?
- Normal for unknown faces
- May need threshold adjustment
- Check enrollment image quality

## Performance Tips

1. **GPU Acceleration**: Install `onnxruntime-gpu` for faster inference
2. **Video Processing**: System processes every 2nd frame by default
3. **Batch Enrollment**: Enroll multiple persons at once
4. **Image Quality**: Use high-resolution, well-lit, frontal face images

## What's Different?

### Before (Single Model):
- 1 embedding per face (ArcFace only)
- 1 ChromaDB collection
- Simple threshold matching

### After (Dual Model):
- 2 embeddings per face (ArcFace + FaceNet-512)
- 2 ChromaDB collections
- Ensemble matching (both must agree)

## Expected Behavior

### Enrollment:
- Takes ~2x time (generates 2 embeddings)
- Stores in both collections with same ID

### Recognition:
- Queries both collections
- Returns match only if both agree
- More accurate, fewer false positives

## Next Steps

1. ✅ Complete setup steps above
2. ✅ Re-enroll all persons
3. ✅ Test with sample images/videos
4. 📊 Monitor accuracy improvements
5. 🔧 Adjust thresholds if needed

## Support

Check logs in:
- Django console
- Celery worker console
- `/tmp/face_debug/` for aligned face images

For issues, review:
- `DUAL_MODEL_ENSEMBLE.md` - Full documentation
- Test scripts output
- Django/Celery logs
