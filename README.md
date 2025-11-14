# SENTINEL

A comprehensive video surveillance and analysis system with real-time face detection, recognition, and audio transcription capabilities.

## Features

- **Real-time Face Detection & Recognition**: Advanced dual-model ensemble for accurate face identification
- **Video Processing**: Automated video analysis with frame extraction and processing
- **Audio Transcription**: Whisper-based speech-to-text conversion
- **Live Detection**: Real-time surveillance monitoring
- **Media Management**: Upload, search, and manage media files
- **Database Integration**: SQLite backend with Django ORM
- **Web Interface**: User-friendly web dashboard for system management

## Architecture

The system consists of several key components:

- **Analysis Pipeline**: Core ML models and processing engines
- **Django Backend**: Web framework handling API and database operations
- **Celery Workers**: Asynchronous task processing
- **Vector Database**: Dual embedding storage for face recognition
- **Media Storage**: Organized file management system

## Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg
- Redis (for Celery)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd SENTINEL
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Whisper.cpp:
```bash
cd sentinel
chmod +x setup_whisper_cpp.sh
./setup_whisper_cpp.sh
```

4. Initialize the database:
```bash
cd sentinel
python manage.py migrate
```

5. Start Redis server (required for Celery):
```bash
redis-server
```

6. Start Celery worker:
```bash
cd sentinel
celery -A sentinel worker --loglevel=info
```

7. Run the Django server:
```bash
cd sentinel
python manage.py runserver
```

## Usage

### Web Interface

Access the web interface at `http://localhost:8000` to:

- Enroll new faces in the system
- Upload and analyze videos
- View detection results
- Search through media files
- Monitor live detection feeds

### Face Enrollment

1. Navigate to the enrollment page
2. Upload clear face images
3. Provide identification labels
4. System automatically processes and stores face embeddings

### Video Analysis

1. Upload video files through the web interface
2. System automatically:
   - Extracts frames
   - Detects and recognizes faces
   - Transcribes audio content
   - Generates analysis reports

## Configuration

Key configuration files:

- `sentinel/settings.py`: Django settings
- `sentinel/celery.py`: Celery configuration
- `requirements.txt`: Python dependencies
- `environment.yml`: Conda environment setup

## Development

### Project Structure

```
sentinel/
├── analysis_pipeline/     # ML models and processing
├── core/                 # Django app
├── media/               # File storage
├── templates/           # HTML templates
├── whisper.cpp/         # Audio transcription
└── manage.py           # Django management
```

### Key Components

- **Detector**: Face detection and recognition engine
- **Dual Embedder**: Advanced embedding generation
- **Video Processor**: Frame extraction and analysis
- **Transcriber**: Audio-to-text conversion
- **Dual Vector DB**: Embedding storage and retrieval

## Troubleshooting

### Common Issues

1. **Celery Tasks Not Processing**:
   ```bash
   cd sentinel
   ./purge_celery_tasks.sh
   ```

2. **Whisper.cpp Setup Issues**:
   - Ensure FFmpeg is installed
   - Check file permissions on setup script

3. **Database Issues**:
   ```bash
   python manage.py migrate --run-syncdb
   ```

## Documentation

Additional documentation available:

- [Architecture Diagram](ARCHITECTURE_DIAGRAM.md)
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)
- [Dual Model Ensemble](DUAL_MODEL_ENSEMBLE.md)
- [Quick Start Guide](QUICK_START_DUAL_MODEL.md)
- [Feature Implementation](FEATURE_IMPLEMENTATION_SUMMARY.md)

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]