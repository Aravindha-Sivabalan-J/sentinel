# sentinel/analysis_pipeline/detector.py

from ultralytics import YOLO
import logging
import os
import cv2

# --- Initialization ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# This will hold our loaded model
yolo_model = None

try:
    # Build robust path to the model file relative to project root
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(SCRIPT_DIR, 'models', 'yolov8n-face.pt')  # <-- FIXED

    if not os.path.exists(model_path):
        logger.error(f"FATAL: YOLOv8 model file not found at {model_path}")
        logger.error("Please download 'yolov8n-face.pt' and place it in the 'analysis_pipeline/models/' directory.")
        yolo_model = None
    else:
        from ultralytics import YOLO
        yolo_model = YOLO(model_path)  # don’t force `.to('cuda')`, Ultralytics auto-selects
        logger.info(f"YOLOv8 face detection model loaded successfully from {model_path}")

except Exception as e:
    yolo_model = None
    logger.error(f"Failed to load YOLOv8 model: {e}", exc_info=True)



def detect_faces(image_input):
    """
    Detects faces in an image using a YOLOv8 model.
    Accepts either a file path or a pre-loaded image in NumPy array format.

    Args:
        image_input (str or numpy.ndarray): The file path or image array.

    Returns:
        list: A list of dictionaries, where each dictionary contains the 'box'
              and 'landmarks' for a detected face.
    """
    if yolo_model is None:
        logger.error("YOLOv8 model is not loaded. Cannot detect faces.")
        return []

    try:
        # Perform inference with the model.
        # The 'conf=0.5' means we only consider detections with > 50% confidence.
        results = yolo_model(image_input, conf=0.5, verbose=False)

        detected_faces = []
        # The result object contains all the information. We need to parse it.
        for result in results:
            # Get bounding boxes in [x1, y1, x2, y2] format
            boxes = result.boxes.xyxy.cpu().numpy()
            
            # Get landmarks (if available)
            if result.keypoints is not None:
                landmarks_data = result.keypoints.xy.cpu().numpy()
            else:
                # Create a placeholder if no landmarks are detected
                landmarks_data = [None] * len(boxes)

            for box, landmarks in zip(boxes, landmarks_data):
                face_data = {
                    'box': box.tolist(),
                    'landmarks': {}
                }
                
                if landmarks is not None:
                    # YOLO face model has 5 landmarks in this order:
                    # left-eye, right-eye, nose, left-mouth-corner, right-mouth-corner
                    face_data['landmarks'] = {
                        'left_eye': landmarks[0].tolist(),
                        'right_eye': landmarks[1].tolist(),
                        'nose': landmarks[2].tolist(),
                        'mouth_left': landmarks[3].tolist(),
                        'mouth_right': landmarks[4].tolist()
                    }
                
                detected_faces.append(face_data)
        
        input_type = "image path" if isinstance(image_input, str) else "image frame"
        # Suppress verbose logging for video frames
        if isinstance(image_input, str):
            logger.info(f"Found {len(detected_faces)} face(s) in {input_type} using YOLOv8.")
        
        return detected_faces

    except Exception as e:
        logger.error(f"Could not detect faces with YOLOv8. Error: {e}")
        import traceback
        traceback.print_exc()
        return []

# # --- Example Usage (for testing the new detector directly) ---
# if __name__ == '__main__':
#     SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
#     test_image_path = os.path.join(SCRIPT_DIR, '..', 'test_images', 'test_face.jpg')
    
#     image = cv2.imread(test_image_path)
#     if image is not None:
#         faces_found = detect_faces(image)
        
#         for face in faces_found:
#             box = face['box']
#             x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
#             cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

#             # Draw landmarks if they exist
#             if face['landmarks']:
#                 for landmark_name, point in face['landmarks'].items():
#                     lx, ly = int(point[0]), int(point[1])
#                     cv2.circle(image, (lx, ly), 3, (0, 0, 255), -1)

#         output_path = os.path.join(SCRIPT_DIR, '..', 'test_images', 'test_face_detected_yolo.jpg')
#         cv2.imwrite(output_path, image)
#         print(f"Detection complete. Result saved to: {output_path}")
#     else:
#         print(f"Could not read the test image at: {test_image_path}")