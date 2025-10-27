import onnxruntime
import numpy as np
import cv2
import os
import logging
from skimage import transform as trans

logger = logging.getLogger(__name__)

class ArcFaceEmbedder:
    """
    ArcFaceEmbedder:
    ----------------
    Handles loading the ArcFace ONNX model, aligning faces using 5 facial landmarks,
    generating embeddings, and performing L2 normalization to ensure consistency
    across embeddings (as DeepFace does).
    """

    def __init__(self, model_path='analysis_pipeline/models/arcface.onnx'):
        """Initialize the ArcFace ONNX model and prepare preprocessing setup."""
        try:
            absolute_model_path = os.path.abspath(model_path)
            self.session = onnxruntime.InferenceSession(
                absolute_model_path,
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            logger.info(f"✅ ArcFace model loaded successfully from {model_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load ArcFace model: {e}")
            self.session = None

        # Template 5-point facial landmark positions (ArcFace standard)
        self.arcface_template = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)

    def align_face(self, image, landmarks):
        """
        Aligns a detected face using 5 key facial landmarks (eyes, nose, mouth corners).
        Ensures consistent orientation and size before embedding extraction.
        """
        try:
            src = np.array([
                landmarks['left_eye'],
                landmarks['right_eye'],
                landmarks['nose'],
                landmarks['mouth_left'],
                landmarks['mouth_right']
            ], dtype=np.float32)

            tform = trans.SimilarityTransform()
            tform.estimate(src, self.arcface_template)
            M = tform.params[0:2, :]
            aligned_face = cv2.warpAffine(image, M, (112, 112), borderValue=0.0)
            return aligned_face
        except Exception as e:
            logger.error(f"❌ Face alignment failed: {e}")
            return None

    def preprocess_face(self, face_img):
        """
        Converts aligned face into ArcFace-compatible input (NCHW, RGB, normalized to [-1, +1]).
        Assumes input is already RGB (from detector).
        """
        if face_img is None:
            return None

        # Handle grayscale
        if face_img.ndim == 2:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_GRAY2RGB)
        # Handle RGBA
        elif face_img.ndim == 3 and face_img.shape[2] == 4:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_RGBA2RGB)

        # Input is already RGB from detector, just resize if needed
        if face_img.shape[:2] != (112, 112):
            resized = cv2.resize(face_img, (112, 112), interpolation=cv2.INTER_LINEAR)
        else:
            resized = face_img

        # ✅ Correct normalization: from [0,255] → [-1,+1]
        normalized = (resized.astype(np.float32) - 127.5) / 128.0

        # Convert to NCHW format (1,3,112,112)
        chw = np.transpose(normalized, (2, 0, 1))
        blob = np.expand_dims(chw, axis=0)
        return blob


    def get_embedding(self, face_img):
        """
        Generates an L2-normalized 512-D embedding for the input face.
        """
        if self.session is None:
            logger.error("❌ ArcFace ONNX session not initialized.")
            return None

        blob = self.preprocess_face(face_img)
        if blob is None:
            return None

        try:
            input_name = self.session.get_inputs()[0].name
            output_name = self.session.get_outputs()[0].name
            raw_output = self.session.run([output_name], {input_name: blob})[0]

            embedding = np.asarray(raw_output).flatten().astype(np.float32)
            norm = np.linalg.norm(embedding)

            # 🔍 Debug: print embedding stats
            logger.info(f"[EMB] shape={embedding.shape}, dtype={embedding.dtype}, norm={norm:.4f}, first10={embedding[:10]}")

            if norm > 0:
                embedding = embedding / norm

            return embedding
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            return None


    @staticmethod
    def cosine_similarity(vec1, vec2):
        """
        Computes cosine similarity between two embeddings.
        Value range: -1 to 1 (closer to 1 means more similar).
        """
        if vec1 is None or vec2 is None:
            return -1
        vec1, vec2 = np.asarray(vec1), np.asarray(vec2)
        denom = np.linalg.norm(vec1) * np.linalg.norm(vec2)
        if denom == 0:
            return -1
        return np.dot(vec1, vec2) / denom
