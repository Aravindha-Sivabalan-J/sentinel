# sentinel/analysis_pipeline/tracker.py

import cv2, torch, os
import logging
import numpy as np
from .detector import yolo_model # Import the loaded YOLO model directly

# --- Initialization ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def track_faces_in_video(video_path):
    """
    Tracks faces in a video file using the built-in tracker of YOLOv8.

    This is a generator function that yields results frame by frame.

    Args:
        video_path (str): The full path to the video file.

    Yields:
        tuple: A tuple containing (frame_number, list_of_tracks), where list_of_tracks
               contains dictionaries for each tracked face in that frame.
    """
    if yolo_model is None:
        logger.error("YOLOv8 model is not loaded. Cannot track faces.")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Error opening video file: {video_path}")
        return

    frame_number = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_number += 1

        # Use the model's track() method. It handles detection and tracking in one step.
        # 'persist=True' tells the tracker to remember tracks between frames.
        # 'verbose=False' suppresses excessive logging.

        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Use absolute path for tracker config
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        tracker_config = os.path.join(SCRIPT_DIR, 'models', 'bytetrack.yaml')
        results = yolo_model.track(frame, persist=True, verbose=False, device=device, tracker=tracker_config)

        current_tracks = []
        # The results object contains the tracking information.
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy()

            for box, track_id in zip(boxes, track_ids):
                current_tracks.append({
                    'track_id': str(int(track_id)), # Convert to string for consistency
                    'box': box.tolist()
                })
        
        yield frame_number, current_tracks

    cap.release()
    logger.info("Video tracking complete.")


def visualize_tracking(video_path):
    """
    Opens a video, runs the YOLOv8 face tracker, and displays the results in a real-time window.
    """
    track_colors = {}
    
    for frame_num, tracks in track_faces_in_video(video_path):
        # We need to read the frame again for visualization.
        # This is inefficient but simple for a demo.
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num - 1)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            continue

        if tracks:
            for track in tracks:
                track_id = track['track_id']
                box = track['box']
                x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])

                if track_id not in track_colors:
                    track_colors[track_id] = (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))

                color = track_colors[track_id]
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.imshow('YOLOv8 Face Tracker', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()
    print("Visualization complete.")


if __name__ == '__main__':
    import os
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    test_video = os.path.join(SCRIPT_DIR, '..', 'test_images', 'test_video3.mp4')
    
    visualize_tracking(test_video)