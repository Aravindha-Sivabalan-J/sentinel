# SENTINEL - System Architecture Diagram

## Overview
SENTINEL is a comprehensive video surveillance and analysis system with real-time face detection, recognition, and audio transcription capabilities built on Django with Celery for asynchronous processing.

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                SENTINEL SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Web Interface (Django Templates)                                              │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │    Home     │   Enroll    │   View DB   │   Search    │   Live Detection│   │
│  │   Upload    │   Person    │   Results   │   Media     │      Feed       │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Django Backend (Views & APIs)                                                 │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │Upload Views │Enroll Views │Search Views │Status APIs  │  Live Views     │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Celery Task Queue (Asynchronous Processing)                                   │
│  ┌─────────────────────────────┬─────────────────────────────────────────────┐ │
│  │    process_video_task       │         process_audio_task                 │ │
│  │  (Video + Face Recognition) │       (Audio Transcription)                │ │
│  └─────────────────────────────┴─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Analysis Pipeline (ML Models)                                                 │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │  Detector   │Dual Embedder│Vector DB    │Transcriber  │Video Processor  │   │
│  │ (YOLOv8)    │(ArcFace+FN) │(ChromaDB)   │(Whisper+)   │   (Enhanced)    │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Data Storage                                                                   │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │   SQLite    │  ChromaDB   │Media Files  │   Results   │    Models       │   │
│  │ (Metadata)  │(Embeddings) │(Videos/Aud) │(Annotated)  │  (ONNX/PT)      │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Complete System Interconnection Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SENTINEL - COMPLETE FEATURE INTERCONNECTION                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   ENROLL    │───▶│  CHROMADB   │◄───│   UPLOAD    │───▶│   SEARCH    │      │
│  │   PERSON    │    │  (VECTORS)  │    │  & PROCESS  │    │   ACROSS    │      │
│  └─────────────┘    └─────────────┘    └─────────────┘    │   MEDIA     │      │
│         │                   ▲                   │         └─────────────┘      │
│         │                   │                   │                │             │
│         ▼                   │                   ▼                ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │FACE CROPS & │    │    LIVE     │    │   SQLITE    │    │   VIEW DB   │      │
│  │ EMBEDDINGS  │    │ DETECTION   │    │ (METADATA)  │    │ & RESULTS   │      │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘      │
│         │                   ▲                   │                │             │
│         │                   │                   │                │             │
│         └───────────────────┼───────────────────┼────────────────┘             │
│                             │                   │                              │
│                    ┌─────────────┐    ┌─────────────┐                         │
│                    │   MODELS    │    │   MEDIA     │                         │
│                    │(YOLO+ARC+FN)│    │   FILES     │                         │
│                    └─────────────┘    └─────────────┘                         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### **Cross-Module Dependencies:**
1. **Enrollment** → Creates embeddings → **ChromaDB** → Used by **Live Detection** & **Processing**
2. **Upload & Process** → Uses **ChromaDB** for recognition → Stores in **SQLite** → Searchable via **Search**
3. **Search** → Queries **SQLite** (filenames/transcripts) + **ChromaDB** (faces) → Results in **View DB**
4. **Live Detection** → Uses **ChromaDB** for real-time recognition → Same models as **Processing**
5. **View DB** → Displays **SQLite** metadata + **Media Files** → Links to **Search** results

---

## 🔄 Module Interaction Flow

### 1. **Person Enrollment Module**
```
User Upload Image → Face Detection → Alignment → Dual Embeddings → ChromaDB Storage
     ↓                    ↓              ↓            ↓                ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│Upload Image │→ │YOLOv8 Detect│→ │ArcFace Align│→ │ArcFace+FNet │→ │Store in DB  │
│(enroll.html)│  │+ Landmarks  │  │to 112x112   │  │Embeddings   │  │(Dual Vector)│
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
                                                                           ↓
                                                                   ┌─────────────┐
                                                                   │Save Face    │
                                                                   │Crop to      │
                                                                   │media/crops/ │
                                                                   └─────────────┘
```

### 2. **Video/Audio Upload & Processing Module**
```
Upload Media → MediaFile Creation → Celery Task → Processing Pipeline → Results Storage
     ↓               ↓                   ↓              ↓                    ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
│Upload File  │→│Create Record│→│Queue Task   │→│Process      │→│Store Results    │
│(home.html)  │ │in SQLite    │ │(Celery)     │ │(Pipeline)   │ │(DB + Files)     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────┘
                      ↓                                                    ↑
                ┌─────────────┐                                   ┌─────────────────┐
                │Status:      │                                   │Annotated Video  │
                │pending →    │                                   │+ Transcript     │
                │processing → │                                   │+ Person Data    │
                │processed    │                                   │+ Timestamps     │
                └─────────────┘                                   └─────────────────┘
```

### 3. **Video Processing Pipeline (Detailed)**
```
Video Input → Frame Extraction → Face Detection → Recognition → Annotation → Audio Merge
     ↓              ↓                  ↓              ↓             ↓            ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│Video File   │→│Extract      │→│YOLOv8       │→│Search       │→│Draw Boxes   │→│Merge with   │
│(.mp4/.avi)  │ │Frames       │ │Detect Faces │ │ChromaDB     │ │+ Labels     │ │Original     │
└─────────────┘ │(OpenCV)     │ │+ Landmarks  │ │(Dual Match) │ │on Frames    │ │Audio Track  │
                └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
                                       ↓              ↓
                                ┌─────────────┐ ┌─────────────┐
                                │Align Face   │ │Generate     │
                                │to 112x112   │ │ArcFace+FNet │
                                │(ArcFace)    │ │Embeddings   │
                                └─────────────┘ └─────────────┘
```

### 4. **Audio Processing Pipeline**
```
Audio Input → Audio Extraction → Language Detection → Transcription → Storage
     ↓              ↓                    ↓               ↓            ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│Audio File   │→│Convert to   │→│Whisper      │→│Multi-Model  │→│Save to DB   │
│(.mp3/.wav)  │ │16kHz WAV    │ │Language     │ │Transcription│ │+ Audio File │
└─────────────┘ │(FFmpeg)     │ │Detection    │ │(GPU Accel.) │ └─────────────┘
                └─────────────┘ └─────────────┘ └─────────────┘
                                       ↓              ↓
                                ┌─────────────┐ ┌─────────────┐
                                │Tamil:       │ │English:     │
                                │IndicWhisper │ │Whisper Small│
                                │Other: M4T   │ │             │
                                └─────────────┘ └─────────────┘
```

### 5. **Search Across Media Module**
```
Search Query → Database Search → Results Aggregation → Display Results
     ↓               ↓                  ↓                   ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────────┐ ┌─────────────┐
│User Input   │→│Search in:   │→│Combine &        │→│Show Matching│
│(search bar) │ │• Filenames  │ │Remove           │ │Media Files  │
└─────────────┘ │• Person IDs │ │Duplicates       │ └─────────────┘
                │• Transcripts│ └─────────────────┘
                └─────────────┘
                       ↓
                ┌─────────────┐
                │Django ORM   │
                │icontains    │
                │Queries      │
                └─────────────┘
```

### 6. **Live Detection Module**
```
IP Webcam → Frame Capture → Face Detection → Recognition → Real-time Display
     ↓            ↓              ↓              ↓              ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│Mobile IP    │→│HTTP Request │→│YOLOv8       │→│ChromaDB     │→│Stream with  │
│Webcam App   │ │/shot.jpg    │ │Detection    │ │Search       │ │Bounding     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │Boxes        │
                                                                └─────────────┘
```

---

## 🗄️ Data Models & Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATABASE SCHEMA                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    1:1     ┌─────────────────┐                            │
│  │   MediaFile     │◄──────────►│   Transcript    │                            │
│  │                 │            │                 │                            │
│  │• id             │            │• media_file_id  │                            │
│  │• filename       │            │• full_text      │                            │
│  │• status         │            │• created_at     │                            │
│  │• progress       │            └─────────────────┘                            │
│  │• task_id        │                                                           │
│  │• video_path     │                                                           │
│  │• annotated_video│                                                           │
│  │• uploaded_at    │                                                           │
│  └─────────────────┘                                                           │
│           │                                                                    │
│           │ 1:N                                                                │
│           ▼                                                                    │
│  ┌─────────────────┐    1:N     ┌─────────────────┐                            │
│  │ DetectedPerson  │◄──────────►│  TimestampLog   │                            │
│  │                 │            │                 │                            │
│  │• id             │            │• detected_person│                            │
│  │• media_file_id  │            │• start_time     │                            │
│  │• identity       │            │• end_time       │                            │
│  │• confidence     │            └─────────────────┘                            │
│  │• face_thumbnail │                                                           │
│  │• arcface_embed  │                                                           │
│  │• facenet_embed  │                                                           │
│  └─────────────────┘                                                           │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                            VECTOR DATABASE                                     │
│                                                                                 │
│  ┌─────────────────┐              ┌─────────────────┐                          │
│  │ ArcFace         │              │ FaceNet         │                          │
│  │ Collection      │              │ Collection      │                          │
│  │                 │              │                 │                          │
│  │• person_id      │              │• person_id      │                          │
│  │• embedding[512] │              │• embedding[512] │                          │
│  │• metadata       │              │• metadata       │                          │
│  └─────────────────┘              └─────────────────┘                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 File System Organization

```
sentinel/
├── media/
│   ├── enrollments/           # Original enrollment images
│   ├── face_crops/           # Aligned face crops (112x112)
│   ├── incoming/             # Temporary upload storage
│   ├── media_files/          # Processed audio/video files
│   │   ├── audio/           # Converted audio files (.wav)
│   │   └── videos/          # Video files
│   ├── results/             # Processing results
│   │   ├── annotated/       # Annotated videos with bounding boxes
│   │   └── *.json          # Task result files
│   ├── temp_search/         # Temporary search uploads
│   └── thumbnails/          # Face thumbnails
│
├── analysis_pipeline/
│   ├── models/              # ML model files
│   │   ├── yolov8n-face.pt # Face detection model
│   │   ├── arcface.onnx    # ArcFace embedding model
│   │   ├── facenet512.onnx # FaceNet embedding model
│   │   └── tamil_models/   # Tamil transcription models
│   ├── production_db/       # ChromaDB vector storage
│   └── *.py                # Processing modules
│
└── core/                   # Django application
    ├── models.py           # Database models
    ├── views.py            # Web views and APIs
    ├── tasks.py            # Celery tasks
    └── templates/          # HTML templates
```

---

## 🔄 Processing Status Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          TASK STATUS LIFECYCLE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Upload File → Create MediaFile → Queue Celery Task → Process → Store Results  │
│       ↓              ↓                   ↓              ↓           ↓          │
│  ┌─────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐   │
│  │ User    │→ │   PENDING   │→ │ PROCESSING  │→ │ PROCESSED   │→ │ SAVED   │   │
│  │ Action  │  │             │  │             │  │             │  │         │   │
│  └─────────┘  │• progress:0 │  │• progress:  │  │• progress:  │  │• Final  │   │
│               │• task_id:   │  │  1-99%      │  │  100%       │  │  State  │   │
│               │  null       │  │• task_id:   │  │• task_id:   │  │         │   │
│               └─────────────┘  │  active     │  │  complete   │  └─────────┘   │
│                               └─────────────┘  └─────────────┘                 │
│                                      ↓              ↓                          │
│                               ┌─────────────┐  ┌─────────────┐                 │
│                               │   FAILED    │  │  STOPPED    │                 │
│                               │             │  │             │                 │
│                               │• Error      │  │• User       │                 │
│                               │  occurred   │  │  cancelled  │                 │
│                               └─────────────┘  └─────────────┘                 │
│                                      ↓              ↓                          │
│                               ┌─────────────────────────────┐                  │
│                               │      RESTART OPTION         │                  │
│                               │   (Back to PROCESSING)      │                  │
│                               └─────────────────────────────┘                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Complete Data Flow Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        END-TO-END DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ USER ACTIONS:                                                                   │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│ │1. Enroll    │  │2. Upload    │  │3. Search    │  │4. Live      │             │
│ │   Person    │  │   Media     │  │   Media     │  │   Detection │             │
│ └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘             │
│        │                │                │                │                    │
│        ▼                ▼                ▼                ▼                    │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │                    SHARED PROCESSING LAYER                                 │ │
│ │                                                                             │ │
│ │  Face Detection (YOLOv8) → Alignment → Dual Embeddings (ArcFace+FaceNet)  │ │
│ │                              ↓                                             │ │
│ │                    Audio Transcription (Multi-language)                   │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
│                                ↓                                               │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │                      SHARED STORAGE LAYER                                  │ │
│ │                                                                             │ │
│ │ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│ │ │  ChromaDB   │  │   SQLite    │  │Media Files  │  │   Results   │        │ │
│ │ │ (Vectors)   │  │(Metadata)   │  │(Original)   │  │(Processed)  │        │ │
│ │ └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
│                                ↓                                               │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │                       UNIFIED ACCESS LAYER                                 │ │
│ │                                                                             │ │
│ │  Search API → View DB → Results Display → Status Tracking → Live Stream   │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### **Feature Interconnection Matrix:**

| Feature | Uses Data From | Provides Data To | Shared Components |
|---------|---------------|------------------|-------------------|
| **Enrollment** | User Images | ChromaDB, Face Crops | YOLOv8, ArcFace, FaceNet |
| **Video Processing** | ChromaDB, Media Files | SQLite, Results, Transcripts | All ML Models, Celery |
| **Audio Processing** | Media Files | SQLite, Transcripts | Whisper Models, Celery |
| **Search** | SQLite, ChromaDB | View Results | Django ORM, Search APIs |
| **Live Detection** | ChromaDB, IP Webcam | Real-time Stream | YOLOv8, Embedders |
| **View DB** | SQLite, Results | User Interface | Django Templates, APIs |

---

## 🚀 Real-time Features

### Live Detection Flow (Connected to Enrollment Data)
```
Mobile Phone (IP Webcam) → Django Server → Face Recognition → Browser Display
        ↓                        ↓                ↓                 ↓
┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐    ┌─────────────┐
│IP Webcam App    │ →  │HTTP GET         │ →  │YOLOv8 +     │ →  │Streaming    │
│/shot.jpg        │    │Frame Capture    │    │ChromaDB     │    │Response     │
│(192.168.1.40)   │    │(live_views.py)  │    │(Same DB as  │    │with Names   │
└─────────────────┘    └─────────────────┘    │ Enrollment) │    │from Enroll  │
                                              └─────────────┘    └─────────────┘
                                                     ↑
                                              ┌─────────────┐
                                              │Uses Same    │
                                              │Embeddings   │
                                              │from Person  │
                                              │Enrollment   │
                                              └─────────────┘
```

### Search Functionality (Cross-Module Integration)
```
Search Input → Debounced Query → Multi-table Search → Aggregated Results
     ↓               ↓                  ↓                    ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────────┐ ┌─────────────────┐
│User Types   │→│300ms Delay  │→│• MediaFile      │→│Combined Results │
│"John Doe"   │ │(JavaScript) │ │• DetectedPerson │ │Shows all videos │
│or "meeting" │ └─────────────┘ │• Transcript     │ │with John or     │
│or "video1"  │                 │                 │ │word "meeting"   │
└─────────────┘                 └─────────────────┘ └─────────────────┘
                                         ↑                    ↓
                                ┌─────────────────┐ ┌─────────────────┐
                                │Links to:        │ │Click → View     │
                                │• Enrollment DB  │ │• Annotated Video│
                                │• Processing     │ │• Transcript     │
                                │  Results        │ │• Person Times   │
                                │• Transcripts    │ └─────────────────┘
                                └─────────────────┘
```

---

## 🔗 Feature Dependency Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FEATURE DEPENDENCY MATRIX                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│    ENROLLMENT ──┐                                                               │
│         │       │                                                               │
│         ▼       ▼                                                               │
│    ChromaDB ←── LIVE DETECTION                                                  │
│         │                                                                       │
│         ▼                                                                       │
│    VIDEO PROCESSING ──┐                                                         │
│         │             │                                                         │
│         ▼             ▼                                                         │
│    SQLite Database ←── AUDIO PROCESSING                                         │
│         │                                                                       │
│         ▼                                                                       │
│    SEARCH FUNCTIONALITY                                                         │
│         │                                                                       │
│         ▼                                                                       │
│    VIEW DATABASE & RESULTS                                                      │
│                                                                                 │
│  Dependencies:                                                                  │
│  • ENROLLMENT must happen before recognition works                              │
│  • PROCESSING creates data that SEARCH queries                                 │
│  • LIVE DETECTION uses ENROLLMENT data in real-time                            │
│  • VIEW DB displays results from all other modules                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Technology Stack Summary

| Layer | Technology | Purpose |
| **Frontend** | HTML/CSS/JavaScript | User interface and real-time updates |
| **Backend** | Django 5.2 | Web framework and API endpoints |
| **Database** | SQLite | Metadata and relationships |
| **Vector DB** | ChromaDB | Face embedding storage and search |
| **Task Queue** | Celery + Redis/RabbitMQ | Asynchronous processing |
| **ML Models** | YOLOv8, ArcFace, FaceNet-512 | Face detection and recognition |
| **Transcription** | Whisper, IndicWhisper, M4T | Multi-language audio processing |
| **Media Processing** | OpenCV, FFmpeg | Video/audio manipulation |
| **Deployment** | ONNX Runtime, PyTorch | Model inference optimization |

### **Shared Components Across Features:**
- **YOLOv8 Model**: Used in Enrollment, Processing, and Live Detection
- **ArcFace/FaceNet Models**: Shared across all face recognition features  
- **ChromaDB**: Central vector database for all face matching operations
- **Celery Workers**: Handle async processing for uploads and heavy tasks
- **Django ORM**: Unified data access layer for all database operations
- **Media Storage**: Centralized file management across all features

---

## 🎯 Key Features Integration

1. **Persistent Processing**: All tasks survive server restarts via database status tracking
2. **Dual Model Ensemble**: ArcFace + FaceNet-512 for robust face recognition
3. **Multi-language Support**: Automatic language detection and appropriate model selection
4. **Real-time Monitoring**: Live progress updates and status polling
5. **Comprehensive Search**: Cross-modal search across filenames, faces, and transcripts
6. **GPU Acceleration**: CUDA support for faster Tamil transcription
7. **Browser Compatibility**: H.264/AAC encoding for universal video playback

## 🔄 Complete Feature Integration Cycle

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE SYSTEM INTEGRATION CYCLE                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  START: User enrolls person                                                     │
│     ↓                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ ENROLLMENT → Face Detection → Embeddings → ChromaDB Storage            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│     ↓                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ UPLOAD VIDEO → Celery Task → Frame Processing → Face Recognition       │   │
│  │              → Uses ChromaDB → Matches Enrolled Person                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│     ↓                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ PROCESSING → Annotated Video → Transcript → SQLite Storage             │   │
│  │            → Person Timestamps → Face Thumbnails                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│     ↓                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ SEARCH → Query SQLite (filename/transcript) + ChromaDB (faces)          │   │
│  │        → Find all videos with enrolled person                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│     ↓                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ VIEW RESULTS → Play annotated video → See timestamps                   │   │
│  │             → View transcript → Download files                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│     ↓                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ LIVE DETECTION → Real-time recognition → Uses same ChromaDB            │   │
│  │               → Recognizes enrolled person instantly                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  RESULT: Complete surveillance ecosystem with persistent data               │   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### **Critical Interconnection Points:**

1. **ChromaDB as Central Hub**: All face recognition features depend on this shared vector database
2. **Shared ML Pipeline**: Same models (YOLOv8, ArcFace, FaceNet) used across enrollment, processing, and live detection
3. **SQLite as Metadata Store**: Links all processed content with searchable metadata
4. **Celery Task System**: Enables persistent processing that survives system restarts
5. **Media File Management**: Centralized storage with organized directory structure
6. **Status Tracking**: Real-time progress updates across all async operations

This architecture ensures scalability, reliability, and comprehensive functionality for video surveillance and analysis applications with complete feature integration.