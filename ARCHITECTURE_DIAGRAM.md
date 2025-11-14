# Dual-Model Ensemble Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER UPLOADS                              │
│                    (Image or Video File)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FACE DETECTION                                │
│                  (YOLOv8n-face Model)                           │
│  • Detects bounding boxes                                       │
│  • Extracts 5 facial landmarks                                  │
│  • Returns aligned 112x112 RGB face                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DUAL PREPROCESSING                              │
│                                                                  │
│  ┌──────────────────────┐      ┌──────────────────────┐       │
│  │   ArcFace Path       │      │   FaceNet Path       │       │
│  │                      │      │                      │       │
│  │  Resize: 112x112     │      │  Resize: 160x160     │       │
│  │  Normalize: [-1,+1]  │      │  Normalize: [-1,+1]  │       │
│  │  Format: NCHW        │      │  Format: NCHW        │       │
│  └──────────┬───────────┘      └──────────┬───────────┘       │
└─────────────┼──────────────────────────────┼───────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│   ArcFace ONNX Model    │    │  FaceNet-512 ONNX Model │
│   (arcface.onnx)        │    │  (facenet512.onnx)      │
│                         │    │                         │
│   Input: 112x112x3      │    │   Input: 160x160x3      │
│   Output: 512-D vector  │    │   Output: 512-D vector  │
└─────────────┬───────────┘    └─────────────┬───────────┘
              │                              │
              │ L2 Normalize                 │ L2 Normalize
              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│  ArcFace Embedding      │    │  FaceNet Embedding      │
│  (512-D, normalized)    │    │  (512-D, normalized)    │
└─────────────┬───────────┘    └─────────────┬───────────┘
              │                              │
              └──────────────┬───────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ENROLLMENT OR SEARCH                         │
└─────────────────────────────────────────────────────────────────┘
              │                              │
    ┌─────────┴─────────┐        ┌─────────┴─────────┐
    │   ENROLLMENT      │        │      SEARCH       │
    └─────────┬─────────┘        └─────────┬─────────┘
              │                              │
              ▼                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    CHROMADB STORAGE                            │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Collection: arcface_faces                               │  │
│  │  ┌────────────┬──────────────┬──────────────────────┐   │  │
│  │  │ Person ID  │  Embedding   │     Metadata         │   │  │
│  │  ├────────────┼──────────────┼──────────────────────┤   │  │
│  │  │ alice_001  │ [512-D vec]  │ {name: "Alice", ...} │   │  │
│  │  │ bob_002    │ [512-D vec]  │ {name: "Bob", ...}   │   │  │
│  │  └────────────┴──────────────┴──────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Collection: facenet_faces                               │  │
│  │  ┌────────────┬──────────────┬──────────────────────┐   │  │
│  │  │ Person ID  │  Embedding   │     Metadata         │   │  │
│  │  ├────────────┼──────────────┼──────────────────────┤   │  │
│  │  │ alice_001  │ [512-D vec]  │ {name: "Alice", ...} │   │  │
│  │  │ bob_002    │ [512-D vec]  │ {name: "Bob", ...}   │   │  │
│  │  └────────────┴──────────────┴──────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ENSEMBLE MATCHING                             │
│                                                                  │
│  1. Query arcface_faces with ArcFace embedding                  │
│     → Returns: best_match_id_arc, similarity_arc                │
│                                                                  │
│  2. Query facenet_faces with FaceNet embedding                  │
│     → Returns: best_match_id_fn, similarity_fn                  │
│                                                                  │
│  3. Ensemble Decision:                                          │
│     IF best_match_id_arc == best_match_id_fn:                   │
│        IF similarity_arc >= 0.30 AND similarity_fn >= 0.30:     │
│           RETURN: MATCH (person_id, avg_similarity)             │
│        ELSE:                                                     │
│           RETURN: NO MATCH (low confidence)                     │
│     ELSE:                                                        │
│        RETURN: NO MATCH (models disagree)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         RESULT                                   │
│                                                                  │
│  • Matched Person ID (or "Unknown")                             │
│  • Confidence Score (average similarity)                        │
│  • Metadata (name, job, age, etc.)                              │
│  • Timestamps (for video)                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Component Interaction

```
┌──────────────────┐
│   Django Views   │  ← User requests (upload, enroll)
│   (views.py)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Celery Tasks    │  ← Async video processing
│   (tasks.py)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Processor      │  ← Orchestrates pipeline
│  (processor.py)  │
└────────┬─────────┘
         │
         ├─────────────────────────────────────┐
         │                                     │
         ▼                                     ▼
┌──────────────────┐                 ┌──────────────────┐
│    Detector      │                 │   Transcriber    │
│  (detector.py)   │                 │ (transcriber.py) │
│                  │                 │                  │
│  YOLOv8 Face     │                 │  Whisper.cpp     │
│  Detection       │                 │  Audio→Text      │
└────────┬─────────┘                 └──────────────────┘
         │
         ▼
┌──────────────────┐
│  Dual Embedder   │  ← NEW: Generates dual embeddings
│(dual_embedder.py)│
│                  │
│  • ArcFace       │
│  • FaceNet-512   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Dual Vector DB   │  ← NEW: Manages dual collections
│(dual_vector_db.py)│
│                  │
│  • arcface_faces │
│  • facenet_faces │
│  • Ensemble logic│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    ChromaDB      │  ← Vector database
│  (chroma_data/)  │
└──────────────────┘
```

## Data Flow: Enrollment

```
User Upload Image
      │
      ▼
┌─────────────┐
│ Detect Face │ → YOLOv8 → Aligned 112x112 RGB
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ Generate Embeddings  │
│                      │
│ Input: 112x112 RGB   │
│   ├→ Resize 112x112 → ArcFace → arc_emb (512-D)
│   └→ Resize 160x160 → FaceNet → fn_emb (512-D)
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Store in ChromaDB   │
│                      │
│  arcface_faces[person_id] = arc_emb + metadata
│  facenet_faces[person_id] = fn_emb + metadata
└──────────────────────┘
```

## Data Flow: Recognition

```
New Face Detected
      │
      ▼
┌─────────────┐
│ Align Face  │ → 112x112 RGB
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ Generate Embeddings  │
│                      │
│ Input: 112x112 RGB   │
│   ├→ ArcFace → query_arc_emb
│   └→ FaceNet → query_fn_emb
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Query ChromaDB      │
│                      │
│  arcface_faces.search(query_arc_emb)
│    → alice_001 (sim=0.85)
│                      │
│  facenet_faces.search(query_fn_emb)
│    → alice_001 (sim=0.87)
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Ensemble Decision   │
│                      │
│  Same ID? ✓          │
│  Arc sim ≥ 0.30? ✓   │
│  FN sim ≥ 0.30? ✓    │
│                      │
│  → MATCH: alice_001  │
│     (avg_sim=0.86)   │
└──────────────────────┘
```

## File Structure

```
SENTINEL/
├── sentinel/
│   ├── analysis_pipeline/
│   │   ├── models/
│   │   │   ├── arcface.onnx          (249MB)
│   │   │   ├── facenet512.onnx       (91MB) ← NEW
│   │   │   ├── yolov8n-face.pt
│   │   │   └── bytetrack.yaml
│   │   ├── detector.py               (unchanged)
│   │   ├── embedder.py               (old, not used)
│   │   ├── dual_embedder.py          ← NEW
│   │   ├── vector_db.py              (old, not used)
│   │   ├── dual_vector_db.py         ← NEW
│   │   ├── processor.py              (modified)
│   │   ├── tracker.py                (unchanged)
│   │   ├── transcriber.py            (unchanged)
│   │   └── preprocess.py             (unchanged)
│   ├── core/
│   │   ├── views.py                  (modified)
│   │   ├── tasks.py                  (unchanged)
│   │   └── models.py                 (unchanged)
│   ├── chroma_data/
│   │   ├── arcface_faces/            ← NEW collection
│   │   └── facenet_faces/            ← NEW collection
│   ├── migrate_to_dual_db.py         ← NEW
│   └── test_dual_embedder.py         ← NEW
├── DUAL_MODEL_ENSEMBLE.md            ← NEW
├── QUICK_START_DUAL_MODEL.md         ← NEW
├── IMPLEMENTATION_SUMMARY.md         ← NEW
└── ARCHITECTURE_DIAGRAM.md           ← NEW (this file)
```

## Key Design Decisions

1. **Separate Collections**: Each model has its own collection for clean separation
2. **Same Person ID**: Critical for ensemble matching across collections
3. **L2 Normalization**: Both embeddings normalized for cosine similarity
4. **Conservative Ensemble**: Both models must agree (reduces false positives)
5. **Configurable Thresholds**: Independent thresholds per model
6. **Minimal Changes**: Only ~25 lines modified in existing code
7. **Backward Compatible**: Old code structure preserved

## Performance Characteristics

| Metric | Single Model | Dual Model | Change |
|--------|-------------|------------|--------|
| Embedding Time | ~50ms | ~100ms | 2x |
| Storage per Person | 512 floats | 1024 floats | 2x |
| Query Time | ~10ms | ~20ms | 2x |
| Accuracy | Baseline | Higher | ↑ |
| False Positives | Baseline | Lower | ↓ |

## Scalability Considerations

- **GPU Acceleration**: Both models run on GPU if available
- **Batch Processing**: Can process multiple faces in parallel
- **Caching**: Video frames can cache embeddings for tracks
- **Async Processing**: Celery handles long-running video tasks
- **Database**: ChromaDB scales to millions of embeddings
