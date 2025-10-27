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

import whisper, torch
import os
import logging
from moviepy.editor import VideoFileClip
import subprocess

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
try:
    # Load fine-tuned Tamil model from project models folder
    import transformers
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    TAMIL_MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "whisper-tamil")
    
    # Load using transformers for fine-tuned model
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    processor = WhisperProcessor.from_pretrained(TAMIL_MODEL_PATH)
    model = WhisperForConditionalGeneration.from_pretrained(TAMIL_MODEL_PATH).to(DEVICE)
    logger.info(f"Tamil fine-tuned MODEL loaded from {TAMIL_MODEL_PATH}")
    USE_TRANSFORMERS = True
except Exception as e:
    logger.error(f" Unable to load Tamil model: {e}, falling back to default")
    try:
        model = whisper.load_model("small", device=DEVICE)
        logger.info("Loaded default Whisper small model")
        USE_TRANSFORMERS = False
    except:
        model = None
        USE_TRANSFORMERS = False

def eat_video(video_path):
    """
    first extract the audio from the video and
    save it in a temporary path and then transcribe the audio and 
    then finally remove the temporarily stored audio file
    """

    temp_audio_path = "temp_audio.mp3"

    if model is None:
        logger.error("model is not loaded, cannot transcribe")
        return {"text": "", "segments": []}
    try:
        command = [
            "ffmpeg",
            "-i", video_path,
            "-vn",
            "-c:a", "libmp3lame",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            temp_audio_path
        ]

        logger.info(f"Executing FFmpeg command: {''.join(command)}")

        subprocess.run(command, check=True, capture_output=True, text=True)

        if USE_TRANSFORMERS:
            # Use transformers model
            import librosa
            audio, sr = librosa.load(temp_audio_path, sr=16000)
            input_features = processor(audio, sampling_rate=16000, return_tensors="pt").input_features.to(DEVICE)
            predicted_ids = model.generate(input_features)
            transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
            return {"text": transcription, "segments": []}
        else:
            # Use original whisper model
            transcription_result = model.transcribe(
                temp_audio_path,
                word_timestamps=True,
                verbose=True
            )
            full_text = transcription_result.get('text', '').strip()
            segments = transcription_result.get('segments', [])
            return {"text": full_text, "segments": segments}

    except FileNotFoundError:
        logger.error("FATAL: ffmpeg not found. Please ensure ffmpeg is installed and in your system's PATH.")
        return {"text": "", "segments": []}
    except subprocess.CalledProcessError as e:
        logger.error("FATAL: FFmpeg command failed.")
        logger.error(f"FFmpeg stderr: {e.stderr}")
        return {"text": "", "segments": []}
    except Exception as e:
        logger.error(f"An unexpected error occurred during transcription: {e}")
        return {"text": "", "segments": []}
    
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
            logger.info(f"Temporary audio file {temp_audio_path} deleted.")




if __name__ == '__main__':
    test_video = 'test_images/test_video2.mp4'
    
    if os.path.exists(test_video):
        full_transcript = eat_video(test_video)
        
        print("\n--- TRANSCRIPTION RESULT ---")
        print(full_transcript)
    else:
        print(f"Test video not found at: {test_video}")
        print("Please add a video file to test the transcriber.")