# import whisper, torch
# import os
# import logging
# from moviepy.editor import VideoFileClip
# import subprocess

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# try:
#     model = whisper.load_model("small", device=DEVICE)
#     logger.info(f"MODEL: {model} loaded")
# except Exception as e:
#     logger.error(f" Unable to load model, ERROR: {e}")
#     model=None

# def eat_video(video_path):
#     """
#     first extract the audio from the video and
#     save it in a temporary path and then transcribe the audio and 
#     then finally remove the temporarily stored audio file
#     """

#     temp_audio_path = "temp_audio.mp3"

#     if model is None:
#         logger.error("model is not loaded, cannot transcribe")
#         return ""
#     try:

#         command = [
#         "ffmpeg",
#         "-i", video_path,
#         "-vn",
#         "-c:a", "libmp3lame",
#         "-ar", "16000",
#         "-ac", "1",
#         "-y",
#         temp_audio_path
#         ]

#         logger.info(f"Executing FFmpeg command: {''.join(command)}")

#         subprocess.run(command, check=True, capture_output=True, text=True)

#         transcription_result = model.transcribe(
#             temp_audio_path,
#             word_timestamps=True,
#             verbose=True,
#             fp16=False
#         )

#         transcribed_text = transcription_result.get('text', '').strip()
#         logger.info("Transcription complete.")

#         return transcribed_text

#     except FileNotFoundError:
#         logger.error("FATAL: ffmpeg not found. Please ensure ffmpeg is installed and in your system's PATH.")
#         return ""
#     except subprocess.CalledProcessError as e:
#         logger.error("FATAL: FFmpeg command failed.")
#         logger.error(f"FFmpeg stderr: {e.stderr}")
#         return ""
#     except Exception as e:
#         logger.error(f"An unexpected error occurred during transcription: {e}")
#         return ""
    
#     finally:
#         if os.path.exists(temp_audio_path):
#             os.remove(temp_audio_path)
#             logger.info(f"Temporary audio file {temp_audio_path} deleted.")


# transcriber.py

import os
import logging
import subprocess
import torch
import numpy as np
from scipy.io import wavfile
import whisper

# Bypass torch.load security check
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '0'

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "multitask_unity_medium.pt")
TAMIL_MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "tamil_models", "whisper-medium-ta_alldata_multigpu")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Lazy loading variables
whisper_small = None
tamil_model = None
tamil_processor = None
seamless_model = None
seamless_processor = None

def load_whisper_small():
    """Load Whisper small model on-demand"""
    global whisper_small
    if whisper_small is None:
        try:
            whisper_small = whisper.load_model("small", device=DEVICE)
            logger.info("✅ Loaded Whisper small for language detection")
        except Exception as e:
            logger.exception(f"❌ Failed to load Whisper small: {e}")
    return whisper_small

def load_tamil_model():
    """Load Tamil model on-demand"""
    global tamil_model, tamil_processor
    if tamil_model is None or tamil_processor is None:
        try:
            logger.info(f"Loading Tamil model from {TAMIL_MODEL_PATH}...")
            from transformers import WhisperForConditionalGeneration, WhisperProcessor, AutoConfig
            from transformers.modeling_utils import load_state_dict as original_load_state_dict
            import warnings
            warnings.filterwarnings('ignore')
            
            # Patch the load_state_dict function to bypass security check
            def patched_load_state_dict(checkpoint_file, *args, **kwargs):
                return torch.load(checkpoint_file, map_location='cpu', weights_only=False)
            
            import transformers.modeling_utils
            transformers.modeling_utils.load_state_dict = patched_load_state_dict
            
            logger.info("Loading Tamil model config...")
            config = AutoConfig.from_pretrained(TAMIL_MODEL_PATH, local_files_only=True)
            logger.info("Loading Tamil model weights...")
            tamil_model = WhisperForConditionalGeneration.from_pretrained(
                TAMIL_MODEL_PATH,
                config=config,
                local_files_only=True
            ).to(DEVICE)
            logger.info("Loading Tamil processor...")
            tamil_processor = WhisperProcessor.from_pretrained(TAMIL_MODEL_PATH, local_files_only=True)
            tamil_model.eval()
            
            # Restore original function
            transformers.modeling_utils.load_state_dict = original_load_state_dict
            
            logger.info("✅ Loaded Tamil IndicWhisper model successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load Tamil model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            tamil_model = None
            tamil_processor = None
    return tamil_model, tamil_processor

def load_seamless_model():
    """Load Seamless M4T model on-demand"""
    global seamless_model, seamless_processor
    if seamless_model is None or seamless_processor is None:
        try:
            logger.info("Loading Seamless M4T model...")
            from transformers import SeamlessM4Tv2ForSpeechToText, AutoProcessor
            logger.info("Loading base model architecture...")
            seamless_model = SeamlessM4Tv2ForSpeechToText.from_pretrained(
                "facebook/seamless-m4t-v2-large"
            )
            logger.info(f"Loading checkpoint from {MODEL_PATH}...")
            checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
            if isinstance(checkpoint, dict):
                if 'model' in checkpoint:
                    seamless_model.load_state_dict(checkpoint['model'], strict=False)
                else:
                    seamless_model.load_state_dict(checkpoint, strict=False)
            seamless_model = seamless_model.to(DEVICE)
            seamless_model.eval()
            logger.info("Loading processor...")
            seamless_processor = AutoProcessor.from_pretrained("facebook/seamless-m4t-v2-large", use_fast=False)
            logger.info("✅ Loaded Seamless-M4T model")
        except Exception as e:
            logger.error(f"❌ Failed to load Seamless-M4T: {e}")
            seamless_model = None
            seamless_processor = None
    return seamless_model, seamless_processor

def unload_audio_models():
    """Clear all audio models from GPU memory"""
    global whisper_small, tamil_model, tamil_processor, seamless_model, seamless_processor
    try:
        if whisper_small is not None:
            del whisper_small
            whisper_small = None
        if tamil_model is not None:
            del tamil_model
            tamil_model = None
        if tamil_processor is not None:
            del tamil_processor
            tamil_processor = None
        if seamless_model is not None:
            del seamless_model
            seamless_model = None
        if seamless_processor is not None:
            del seamless_processor
            seamless_processor = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Audio models unloaded from GPU")
    except Exception as e:
        logger.warning(f"Error unloading audio models: {e}")

def eat_video(video_path):
    temp_audio_path = os.path.abspath("temp_audio.wav")
    try:
        ffmpeg_cmd = [
            "ffmpeg", "-i", video_path, "-vn",
            "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le",
            "-af", "apad=pad_dur=1",
            "-y", temp_audio_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        logger.info(f"Audio extracted to {temp_audio_path}")
        
        # Detect language using Whisper small
        detected_lang = "en"
        whisper_model = load_whisper_small()
        if whisper_model:
            logger.info("Detecting language...")
            audio = whisper.load_audio(temp_audio_path)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(DEVICE)
            _, probs = whisper_model.detect_language(mel)
            detected_lang = max(probs, key=probs.get)
            logger.info(f"Detected language: {detected_lang}")
        
        # Transcribe based on detected language
        segments = []
        if detected_lang == "ta":
            tamil_m, tamil_p = load_tamil_model()
            if tamil_m and tamil_p:
                logger.info("Using Tamil IndicWhisper model")
                sample_rate, audio_data = wavfile.read(temp_audio_path)
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
                
                # Process audio in chunks for long files
                chunk_length = 30 * 16000  # 30 seconds chunks
                transcriptions = []
                
                for i in range(0, len(audio_data), chunk_length):
                    chunk = audio_data[i:i + chunk_length]
                    with torch.no_grad():
                        inputs = tamil_p(chunk, sampling_rate=16000, return_tensors="pt").to(DEVICE)
                        generated_ids = tamil_m.generate(
                            inputs.input_features,
                            max_length=448,
                            num_beams=5
                        )
                        chunk_text = tamil_p.batch_decode(generated_ids, skip_special_tokens=True)[0]
                        transcriptions.append(chunk_text)
                        start_time = i / 16000
                        end_time = min((i + chunk_length) / 16000, len(audio_data) / 16000)
                        segments.append({"text": chunk_text, "start": start_time, "end": end_time})
                        logger.info(f"Processed chunk {i//chunk_length + 1}")
                
                transcription = " ".join(transcriptions)
                logger.info("✅ Tamil transcription complete")
            else:
                # Fallback to Whisper
                whisper_model = load_whisper_small()
                result = whisper_model.transcribe(temp_audio_path, language="en", task="transcribe", fp16=False, word_timestamps=True)
                transcription = result["text"]
                segments = [{"text": seg["text"], "start": seg["start"], "end": seg["end"]} for seg in result.get("segments", [])]
        
        elif detected_lang != "en":
            seamless_m, seamless_p = load_seamless_model()
            if seamless_m and seamless_p:
                logger.info(f"✅ Using Seamless M4T for language: {detected_lang}")
                sample_rate, audio_data = wavfile.read(temp_audio_path)
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
                
                lang_map = {"hi": "hin", "te": "tel", "kn": "kan", "ml": "mal", "mr": "mar", "bn": "ben", "gu": "guj", "pa": "pan", "ur": "urd"}
                tgt_lang = lang_map.get(detected_lang, "eng")
                
                with torch.no_grad():
                    inputs = seamless_p(audio=audio_data, sampling_rate=16000, return_tensors="pt").to(DEVICE)
                    output_tokens = seamless_m.generate(
                        **inputs,
                        tgt_lang=tgt_lang,
                        max_length=512,
                        num_beams=5,
                        no_repeat_ngram_size=3,
                        repetition_penalty=1.2
                    )
                    transcription = seamless_p.decode(output_tokens[0].tolist(), skip_special_tokens=True)
                    segments = [{"text": transcription, "start": 0, "end": len(audio_data) / 16000}]
            else:
                # Fallback to Whisper
                whisper_model = load_whisper_small()
                result = whisper_model.transcribe(temp_audio_path, language="en", task="transcribe", fp16=False, word_timestamps=True)
                transcription = result["text"]
                segments = [{"text": seg["text"], "start": seg["start"], "end": seg["end"]} for seg in result.get("segments", [])]
        else:
            logger.info("✅ Using Whisper small for English")
            whisper_model = load_whisper_small()
            result = whisper_model.transcribe(temp_audio_path, language="en", task="transcribe", fp16=False, word_timestamps=True)
            transcription = result["text"]
            segments = [{"text": seg["text"], "start": seg["start"], "end": seg["end"]} for seg in result.get("segments", [])]
            logger.info("✅ English transcription complete")
        
        logger.info(f"Transcription complete: {transcription[:100]}")
        
        # Unload audio models after transcription
        unload_audio_models()
        
        return {"text": transcription, "segments": segments}
    except Exception as e:
        logger.exception(f"Transcription error: {e}")
        return {"text": "", "segments": []}
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
            logger.info(f"Removed temp audio file")




if __name__ == '__main__':
    test_video = 'test_images/test_video2.mp4'
    
    if os.path.exists(test_video):
        full_transcript = eat_video(test_video)
        
        print("\n--- TRANSCRIPTION RESULT ---")
        print(full_transcript)
    else:
        print(f"Test video not found at: {test_video}")
        print("Please add a video file to test the transcriber.")