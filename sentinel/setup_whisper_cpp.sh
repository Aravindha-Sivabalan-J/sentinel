#!/bin/bash
# Setup whisper.cpp locally in the project

cd /home/cannyminds/Desktop/SENTINEL/sentinel

# Clone whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp.git

# Build with GPU support
cd whisper.cpp
make WHISPER_CUDA=1

# Download base model
bash ./models/download-ggml-model.sh base

# Create symlink in analysis_pipeline
cd ..
ln -sf whisper.cpp/main analysis_pipeline/whisper-cpp
ln -sf whisper.cpp/models/ggml-base.bin analysis_pipeline/models/ggml-base.bin

echo "✅ whisper.cpp setup complete!"
echo "Binary: analysis_pipeline/whisper-cpp"
echo "Model: analysis_pipeline/models/ggml-base.bin"
