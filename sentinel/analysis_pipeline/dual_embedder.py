import onnxruntime
import numpy as np
import cv2
import os
import logging

logger = logging.getLogger(__name__)

class DualEmbedder:
    """Generates embeddings using both ArcFace and FaceNet-512 models with lazy loading"""
    
    def __init__(self):
        self.arcface_session = None
        self.facenet_session = None
        self.arcface_path = os.path.abspath('analysis_pipeline/models/arcface.onnx')
        self.facenet_path = os.path.abspath('analysis_pipeline/models/facenet512.onnx')
    
    def load_models(self):
        """Load both models on-demand"""
        if self.arcface_session is None or self.facenet_session is None:
            try:
                # Load ArcFace model (112x112 input)
                self.arcface_session = onnxruntime.InferenceSession(
                    self.arcface_path,
                    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
                )
                logger.info(f"✅ ArcFace model loaded from {self.arcface_path}")
                
                # Load FaceNet-512 model (160x160 input)
                self.facenet_session = onnxruntime.InferenceSession(
                    self.facenet_path,
                    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
                )
                logger.info(f"✅ FaceNet-512 model loaded from {self.facenet_path}")
                
            except Exception as e:
                logger.error(f"❌ Failed to load models: {e}")
                self.arcface_session = None
                self.facenet_session = None
    
    def unload_models(self):
        """Clear models from GPU memory"""
        try:
            if self.arcface_session is not None:
                del self.arcface_session
                self.arcface_session = None
            if self.facenet_session is not None:
                del self.facenet_session
                self.facenet_session = None
            
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Face embedding models unloaded from GPU")
        except Exception as e:
            logger.warning(f"Error unloading embedding models: {e}")
    
    def preprocess_arcface(self, face_img):
        """Preprocess for ArcFace: 112x112, normalized to [-1, +1]"""
        if face_img is None or face_img.size == 0:
            return None
        
        # Resize to 112x112
        if face_img.shape[:2] != (112, 112):
            resized = cv2.resize(face_img, (112, 112), interpolation=cv2.INTER_LINEAR)
        else:
            resized = face_img
        
        # Normalize to [-1, +1]
        normalized = (resized.astype(np.float32) - 127.5) / 128.0
        
        # Convert to NCHW format
        chw = np.transpose(normalized, (2, 0, 1))
        blob = np.expand_dims(chw, axis=0)
        return blob
    
    def preprocess_facenet(self, face_img):
        """Preprocess for FaceNet-512: 160x160, normalized, NHWC format"""
        if face_img is None or face_img.size == 0:
            return None
        
        # Resize to 160x160
        if face_img.shape[:2] != (160, 160):
            resized = cv2.resize(face_img, (160, 160), interpolation=cv2.INTER_LINEAR)
        else:
            resized = face_img
        
        # Normalize to [-1, +1]
        normalized = (resized.astype(np.float32) - 127.5) / 128.0
        
        # FaceNet expects NHWC format (batch, height, width, channels)
        blob = np.expand_dims(normalized, axis=0)
        return blob
    
    def get_dual_embeddings(self, face_img_rgb):
        """
        Generate both ArcFace and FaceNet-512 embeddings from aligned RGB face.
        Returns: (arcface_embedding, facenet_embedding) or None if failed
        """
        self.load_models()
        if self.arcface_session is None or self.facenet_session is None:
            logger.error("❌ Models not initialized")
            return None
        
        try:
            # Generate ArcFace embedding (112x112)
            arc_blob = self.preprocess_arcface(face_img_rgb)
            if arc_blob is None:
                return None
            
            arc_input = self.arcface_session.get_inputs()[0].name
            arc_output = self.arcface_session.get_outputs()[0].name
            arc_raw = self.arcface_session.run([arc_output], {arc_input: arc_blob})[0]
            arc_emb = np.asarray(arc_raw).flatten().astype(np.float32)
            
            # L2 normalize
            arc_norm = np.linalg.norm(arc_emb)
            if arc_norm > 0:
                arc_emb = arc_emb / arc_norm
            
            # Generate FaceNet-512 embedding (160x160)
            fn_blob = self.preprocess_facenet(face_img_rgb)
            if fn_blob is None:
                return None
            
            fn_output = self.facenet_session.get_outputs()[0].name
            fn_raw = self.facenet_session.run([fn_output], {
                'input:0': fn_blob,
                'phase_train:0': np.array(False)
            })[0]
            fn_emb = np.asarray(fn_raw).flatten().astype(np.float32)
            
            # L2 normalize
            fn_norm = np.linalg.norm(fn_emb)
            if fn_norm > 0:
                fn_emb = fn_emb / fn_norm
            
            logger.info(f"[DUAL_EMB] ArcFace: shape={arc_emb.shape}, norm={np.linalg.norm(arc_emb):.4f}, first10={arc_emb[:10]}")
            logger.info(f"[DUAL_EMB] FaceNet: shape={fn_emb.shape}, norm={np.linalg.norm(fn_emb):.4f}, first10={fn_emb[:10]}")
            
            return (arc_emb, fn_emb)
            
        except Exception as e:
            logger.error(f"❌ Failed to generate dual embeddings: {e}")
            return None