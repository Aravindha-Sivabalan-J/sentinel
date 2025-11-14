# Dual-Model Ensemble Deployment Checklist

## Pre-Deployment Verification

### 1. Model Files ✓
- [x] `analysis_pipeline/models/arcface.onnx` exists (249MB)
- [x] `analysis_pipeline/models/facenet512.onnx` exists (91MB)
- [x] Both models are ONNX format
- [x] File permissions are correct

### 2. Code Files ✓
- [x] `analysis_pipeline/dual_embedder.py` created
- [x] `analysis_pipeline/dual_vector_db.py` created
- [x] `analysis_pipeline/processor.py` modified
- [x] `core/views.py` modified
- [x] `migrate_to_dual_db.py` created
- [x] `test_dual_embedder.py` created

### 3. Dependencies ✓
```bash
# Check if installed:
pip list | grep onnxruntime
pip list | grep chromadb
pip list | grep numpy
pip list | grep opencv
```

Expected:
- onnxruntime or onnxruntime-gpu
- chromadb
- numpy
- opencv-python

## Deployment Steps

### Step 1: Backup Current System
```bash
# Backup current ChromaDB
cd /home/cannyminds/Desktop/SENTINEL/sentinel
cp -r chroma_data chroma_data.backup_$(date +%Y%m%d)

# Backup current code (optional)
git commit -am "Backup before dual-model deployment" || echo "No git repo"
```

- [ ] ChromaDB backed up
- [ ] Code committed (if using git)

### Step 2: Test Dual Embedder
```bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python test_dual_embedder.py
```

Expected output:
```
✅ Models loaded successfully
✅ ArcFace embedding: shape=(512,), norm=1.0000
✅ FaceNet embedding: shape=(512,), norm=1.0000
✅ Dual embedder test PASSED!
```

- [ ] Test passed
- [ ] No errors in output
- [ ] Both embeddings generated

### Step 3: Run Database Migration
```bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python migrate_to_dual_db.py
```

Expected output:
```
Existing collections: ['face_embeddings']
✅ Deleted old 'face_embeddings' collection
✅ Created 'arcface_faces' collection
✅ Created 'facenet_faces' collection
✅ Migration complete! Dual collections are ready.
```

- [ ] Migration completed
- [ ] Old collection deleted
- [ ] New collections created
- [ ] No errors

### Step 4: Verify Collections
```bash
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python -c "
import chromadb
client = chromadb.PersistentClient(path='./chroma_data')
collections = [c.name for c in client.list_collections()]
print('Collections:', collections)
assert 'arcface_faces' in collections
assert 'facenet_faces' in collections
print('✅ Collections verified!')
"
```

- [ ] Both collections exist
- [ ] No errors

### Step 5: Start Services
```bash
# Terminal 1: RabbitMQ
sudo systemctl status rabbitmq-server
# If not running:
sudo systemctl start rabbitmq-server
```

- [ ] RabbitMQ running

```bash
# Terminal 2: Celery Worker
cd /home/cannyminds/Desktop/SENTINEL/sentinel
celery -A sentinel worker --loglevel=info
```

- [ ] Celery worker started
- [ ] No import errors
- [ ] Worker ready

```bash
# Terminal 3: Django Server
cd /home/cannyminds/Desktop/SENTINEL/sentinel
python manage.py runserver
```

- [ ] Django server started
- [ ] No import errors
- [ ] Server accessible at http://localhost:8000

### Step 6: Test Enrollment
1. Open browser: http://localhost:8000/enroll/
2. Fill form:
   - Person ID: `test_person_001`
   - Job: `Engineer`
   - Age: `30`
   - Height: `175`
   - Weight: `70`
3. Upload clear face image
4. Click "Enroll"

Check logs for:
```
[DUAL_EMB] ArcFace: shape=(512,), norm=1.0000
[DUAL_EMB] FaceNet: shape=(512,), norm=1.0000
✅ Added test_person_001 to both collections
```

- [ ] Enrollment successful
- [ ] Dual embeddings generated
- [ ] Added to both collections
- [ ] Success message displayed

### Step 7: Test Image Recognition
1. Go to: http://localhost:8000/
2. Upload image with enrolled person's face
3. Wait for result

Check logs for:
```
[SEARCH] ArcFace: test_person_001 (sim=0.XXXX)
[SEARCH] FaceNet: test_person_001 (sim=0.XXXX)
✅ MATCH: test_person_001 (avg_sim=0.XXXX)
```

- [ ] Image processed
- [ ] Face detected
- [ ] Dual embeddings generated
- [ ] Ensemble search performed
- [ ] Correct match returned

### Step 8: Test Video Recognition
1. Go to: http://localhost:8000/
2. Upload short video (10-30 seconds) with enrolled person
3. Wait for Celery task to complete
4. View results page

Check Celery logs for:
```
Starting video analysis...
[DUAL_EMB] ArcFace: shape=(512,), norm=1.0000
[DUAL_EMB] FaceNet: shape=(512,), norm=1.0000
[SEARCH] ArcFace: test_person_001 (sim=0.XXXX)
[SEARCH] FaceNet: test_person_001 (sim=0.XXXX)
✅ MATCH: test_person_001 (avg_sim=0.XXXX)
Video processing done.
```

- [ ] Video uploaded
- [ ] Celery task started
- [ ] Face tracking working
- [ ] Dual embeddings generated
- [ ] Ensemble matching working
- [ ] Annotated video created
- [ ] Results displayed

### Step 9: Re-enroll All Persons
For each person previously enrolled:
1. Go to: http://localhost:8000/enroll/
2. Use same Person ID
3. Upload their image
4. Verify enrollment success

- [ ] All persons re-enrolled
- [ ] Same IDs used
- [ ] All enrollments successful

### Step 10: Production Testing
Test with real-world scenarios:
- [ ] Multiple faces in single image
- [ ] Multiple people in video
- [ ] Unknown faces (not enrolled)
- [ ] Poor lighting conditions
- [ ] Different angles
- [ ] Partial occlusions

## Post-Deployment Monitoring

### Logs to Watch
```bash
# Django logs
tail -f /path/to/django.log

# Celery logs
# (visible in celery worker terminal)

# Check for:
- [DUAL_EMB] messages
- [SEARCH] messages
- ✅ MATCH or ❌ NO MATCH messages
- Any errors or exceptions
```

### Key Metrics
- [ ] Enrollment success rate: ____%
- [ ] Recognition accuracy: ____%
- [ ] False positive rate: ____%
- [ ] False negative rate: ____%
- [ ] Average processing time: ___ms
- [ ] Models agreement rate: ____%

### Performance Checks
```bash
# Check GPU usage (if using GPU)
nvidia-smi

# Check memory usage
free -h

# Check disk space
df -h
```

- [ ] GPU utilization acceptable
- [ ] Memory usage acceptable
- [ ] Disk space sufficient

## Rollback Plan (If Needed)

### If Issues Occur:
```bash
# Stop services
# Terminal 2: Ctrl+C (Celery)
# Terminal 3: Ctrl+C (Django)

# Restore backup
cd /home/cannyminds/Desktop/SENTINEL/sentinel
rm -rf chroma_data
mv chroma_data.backup_YYYYMMDD chroma_data

# Revert code changes
git revert HEAD  # if using git
# OR manually restore old files

# Restart services
```

- [ ] Rollback procedure tested
- [ ] Backup restoration verified

## Troubleshooting

### Issue: Models not loading
**Solution:**
```bash
pip install onnxruntime-gpu  # For GPU
# OR
pip install onnxruntime  # For CPU
```

### Issue: Collections not found
**Solution:**
```bash
python migrate_to_dual_db.py
```

### Issue: No matches found
**Possible causes:**
- Persons not re-enrolled after migration
- Thresholds too strict (adjust in dual_vector_db.py)
- Face quality issues

**Solution:**
1. Re-enroll persons
2. Check face image quality
3. Review threshold settings

### Issue: Models always disagree
**Possible causes:**
- Different model sensitivities
- Face quality issues
- Thresholds too strict

**Solution:**
1. Check enrollment image quality
2. Adjust thresholds independently
3. Review logs for similarity scores

## Success Criteria

### Minimum Requirements
- [x] Both models load successfully
- [x] Dual embeddings generated
- [x] Both collections created
- [x] Enrollment works
- [x] Image recognition works
- [x] Video recognition works
- [x] No critical errors

### Performance Requirements
- [ ] Enrollment time < 5 seconds
- [ ] Image recognition time < 3 seconds
- [ ] Video processing time < 2x video duration
- [ ] Recognition accuracy > 90%
- [ ] False positive rate < 5%

### Stability Requirements
- [ ] System runs for 24 hours without crashes
- [ ] Memory usage stable
- [ ] No memory leaks
- [ ] Celery tasks complete successfully

## Sign-off

- [ ] All tests passed
- [ ] Performance acceptable
- [ ] Documentation reviewed
- [ ] Team trained on new system
- [ ] Monitoring in place
- [ ] Rollback plan ready

**Deployed by:** _______________
**Date:** _______________
**Version:** Dual-Model Ensemble v1.0
**Status:** ☐ Success ☐ Issues ☐ Rolled Back

## Notes
_Add any deployment notes, issues encountered, or observations here:_

---

**Next Review Date:** _______________
