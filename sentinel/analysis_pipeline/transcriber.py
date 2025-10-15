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
    model = whisper.load_model("small", device=DEVICE)
    logger.info(f"MODEL: {model} loaded")
except Exception as e:
    logger.error(f" Unable to load model, ERROR: {e}")
    model=None

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