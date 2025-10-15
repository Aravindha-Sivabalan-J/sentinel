# import onnxruntime
# from skimage import transform as trans
# import numpy as np
# import cv2, os, logging

# logger = logging.getLogger(__name__)

# class ArcFaceEmbedder:
#     def __init__(self, model_path='analysis_pipeline/models/arcface.onnx'):
#         """Initializes the ArcFace embedder, loading the ONNX model."""
#         try:
#             absolute_model_path = os.path.abspath(model_path)
#             self.session = onnxruntime.InferenceSession(absolute_model_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
#             logger.info(f"ArcFace model loaded successfully from {model_path}")
#         except Exception as e:
#             logger.error(f"Failed to load ArcFace model: {e}")
#             import traceback
#             traceback.print_exc()
#             self.session = None
#         self.arcface_dst = np.array([
#             [38.2946, 51.6963], [73.5318, 51.5014],
#             [56.0252, 71.7366], [41.5493, 92.3655],
#             [70.7299, 92.2041]], dtype=np.float32)
        
#     def align_face(self, image, landmarks):
#         le = landmarks['left_eye']
#         re = landmarks['right_eye']
#         n = landmarks['nose']
#         ml = landmarks['mouth_left']
#         mr = landmarks['mouth_right']

#         # Estimate the transformation matrix to align the face
#         src = np.array([le, re, n, ml, mr], dtype=np.float32)
#         tform = trans.SimilarityTransform()
#         tform.estimate(src, self.arcface_dst)
#         M = tform.params[0:2, :]

#         # Apply the transformation to the image to get the aligned face
#         aligned_face = cv2.warpAffine(image, M, (112, 112), borderValue=0.0)
#         return aligned_face
    
#     _EMBED_ERROR_COUNT = 0
#     _EMBED_ERROR_LIMIT = 8

#     def get_embedding(self, face_or_blob):
#         """
#         Robust get_embedding that accepts either:
#         - a raw BGR crop (H,W,3)  OR
#         - a preprocessed blob (batch) like (1,3,H,W) or (1,H,W,3)

#         It inspects the ONNX model input metadata to determine expected layout
#         (NCHW vs NHWC) and target HxW, and then either uses the provided blob
#         or performs preprocessing on the raw crop. Returns a 1-D float32 embedding
#         normalized to unit length, or None on error.
#         """
#         import numpy as np
#         import cv2
#         import logging

#         logger = logging.getLogger(__name__)

#         if self.session is None:
#             logger.error("ONNX session not loaded")
#             return None

#         try:
#             # --- inspect model input: name + shape ---
#             input_meta = self.session.get_inputs()[0]
#             input_name = input_meta.name
#             model_shape = list(input_meta.shape)  # may contain symbolic dims
#             # Normalize dims to ints where possible
#             dims = []
#             for d in model_shape:
#                 try:
#                     dims.append(int(d))
#                 except Exception:
#                     dims.append(None)

#             # Infer expected layout and H/W
#             layout = "NCHW"
#             target_h = 112
#             target_w = 112
#             if len(dims) == 4:
#                 # If dims[1]==3 -> NCHW (N,C,H,W)
#                 if dims[1] == 3:
#                     layout = "NCHW"
#                     if dims[2] is not None: target_h = dims[2]
#                     if dims[3] is not None: target_w = dims[3]
#                 # Else if dims[-1] == 3 -> NHWC (N,H,W,C)
#                 elif dims[-1] == 3:
#                     layout = "NHWC"
#                     if dims[1] is not None: target_h = dims[1]
#                     if dims[2] is not None: target_w = dims[2]
#                 else:
#                     # best-effort detection
#                     if 3 in dims:
#                         idx = dims.index(3)
#                         if idx == 1:
#                             layout = "NCHW"
#                             if dims[2] is not None: target_h = dims[2]
#                             if dims[3] is not None: target_w = dims[3]
#                         elif idx == 3:
#                             layout = "NHWC"
#                             if dims[1] is not None: target_h = dims[1]
#                             if dims[2] is not None: target_w = dims[2]

#             # --- convert incoming to numpy ---
#             arr = np.asarray(face_or_blob)

#             # Case A: already a 4D blob (batch present)
#             if arr.ndim == 4:
#                 # common accepted shapes: (1,3,H,W) NCHW or (1,H,W,3) NHWC
#                 prepared_blob = None

#                 # If matches NCHW shape and channel is in axis 1
#                 if arr.shape[0] == 1 and arr.shape[1] == 3 and arr.shape[2] == target_h and arr.shape[3] == target_w:
#                     prepared_blob = arr.astype(np.float32)
#                     prepared_layout = "NCHW"
#                 # If matches NHWC shape and channel is last
#                 elif arr.shape[0] == 1 and arr.shape[1] == target_h and arr.shape[2] == target_w and arr.shape[3] == 3:
#                     prepared_blob = arr.astype(np.float32)
#                     prepared_layout = "NHWC"
#                 else:
#                     # maybe it's (1, H, W, C) or (1, C, H, W) but dims differ; attempt to adapt:
#                     # if arr is (1,3,H,W) but H/W not equal target, but user already preprocessed to different size:
#                     if arr.shape[0] == 1 and arr.shape[1] == 3:
#                         # arr is NCHW but size differs => assume it's ready (don't resize), just adapt dtype
#                         prepared_blob = arr.astype(np.float32)
#                         prepared_layout = "NCHW"
#                     elif arr.shape[0] == 1 and arr.shape[-1] == 3:
#                         prepared_blob = arr.astype(np.float32)
#                         prepared_layout = "NHWC"
#                     else:
#                         # fallback: squeeze batch and treat as raw HWC
#                         try:
#                             arr2 = np.squeeze(arr, axis=0)
#                             if arr2.ndim == 3 and arr2.shape[2] in (1,3,4):
#                                 # treat arr2 as raw image and continue preprocessing below
#                                 arr = arr2
#                                 # fall through to raw-image path
#                                 prepared_blob = None
#                             else:
#                                 logger.error("Unrecognized 4D blob format: %s", arr.shape)
#                                 return None
#                         except Exception:
#                             logger.error("Unable to interpret 4D input: %s", arr.shape)
#                             return None

#                 # If we have a prepared_blob, ensure layout matches model; transpose if needed
#                 if 'prepared_blob' in locals() and prepared_blob is not None:
#                     if layout == "NCHW" and prepared_layout == "NHWC":
#                         # NHWC -> NCHW
#                         prepared_blob = np.transpose(prepared_blob, (0, 3, 1, 2))
#                     elif layout == "NHWC" and prepared_layout == "NCHW":
#                         # NCHW -> NHWC
#                         prepared_blob = np.transpose(prepared_blob, (0, 2, 3, 1))

#                     input_blob = np.ascontiguousarray(prepared_blob, dtype=np.float32)
#                     logger.debug("Using provided preprocessed blob; prepared shape: %s", input_blob.shape)

#                     # run model
#                     output_name = self.session.get_outputs()[0].name
#                     result = self.session.run([output_name], {input_name: input_blob})[0]
#                     vec = result.flatten()
#                     norm = np.linalg.norm(vec)
#                     if norm == 0:
#                         return None
#                     return (vec / norm).astype(np.float32)

#             # Case B: raw image-like (H,W, C) or squeezed 3D array
#             if arr.ndim == 3 or (arr.ndim == 2):
#                 # if 2D -> convert to 3-channel BGR
#                 img = arr
#                 if img.ndim == 2:
#                     img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
#                 if img.ndim == 3 and img.shape[2] == 4:
#                     img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

#                 # guard against empty
#                 if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
#                     logger.warning("get_embedding: empty image crop %s", getattr(img, 'shape', None))
#                     return None

#                 # Resize to model HxW (cv2 uses (w,h))
#                 tw, th = int(target_w), int(target_h)
#                 if tw <= 0 or th <= 0:
#                     logger.error("Invalid target dims from model: %s x %s", target_w, target_h)
#                     tw, th = 112, 112

#                 try:
#                     resized = cv2.resize(img, (tw, th), interpolation=cv2.INTER_LINEAR)
#                 except Exception as e:
#                     logger.exception("Error resizing image for embedding: %s; img.shape=%s target=(%s,%s)", e, img.shape, tw, th)
#                     return None

#                 # Convert BGR -> RGB
#                 try:
#                     rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
#                 except Exception:
#                     # fallback: maybe already RGB
#                     rgb = resized

#                 # build blob according to layout
#                 if layout == "NCHW":
#                     blob = np.transpose(rgb, (2, 0, 1))[None, ...].astype(np.float32)  # (1, C, H, W)
#                 else:  # NHWC
#                     blob = rgb[None, ...].astype(np.float32)  # (1, H, W, C)

#                 input_blob = np.ascontiguousarray(blob, dtype=np.float32)
#                 logger.debug("Prepared raw image blob shape: %s (layout=%s)", input_blob.shape, layout)

#                 # run model
#                 output_name = self.session.get_outputs()[0].name
#                 result = self.session.run([output_name], {input_name: input_blob})[0]
#                 vec = result.flatten()
#                 norm = np.linalg.norm(vec)
#                 if norm == 0:
#                     return None
#                 return (vec / norm).astype(np.float32)

#             # If we reach here, unknown format
#             logger.error("get_embedding: unsupported input ndim=%s shape=%s", arr.ndim, arr.shape)
#             return None

#         except Exception as exc:
#             logger.exception("Unexpected error in get_embedding: %s", exc)
#             return None



import onnxruntime
import numpy as np
import cv2
import os
import logging
from skimage import transform as trans

logger = logging.getLogger(__name__)

class ArcFaceEmbedder:
    def __init__(self, model_path='analysis_pipeline/models/arcface.onnx'):
        """Initializes the ArcFace embedder, loading the ONNX model."""
        try:
            absolute_model_path = os.path.abspath(model_path)
            self.session = onnxruntime.InferenceSession(
                absolute_model_path,
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            logger.info(f"ArcFace model loaded successfully from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load ArcFace model: {e}")
            self.session = None

        # Standard 5-point template for face alignment
        self.arcface_dst = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)

    def align_face(self, image, landmarks):
        """Aligns face to standard template using 5 landmarks."""
        le = landmarks['left_eye']
        re = landmarks['right_eye']
        n = landmarks['nose']
        ml = landmarks['mouth_left']
        mr = landmarks['mouth_right']

        src = np.array([le, re, n, ml, mr], dtype=np.float32)
        tform = trans.SimilarityTransform()
        tform.estimate(src, self.arcface_dst)
        M = tform.params[0:2, :]
        aligned_face = cv2.warpAffine(image, M, (112, 112), borderValue=0.0)
        return aligned_face

    def get_embedding(self, face_or_blob):
        """Runs ArcFace ONNX model and returns embedding as float32 array (no normalization)."""
        if self.session is None:
            logger.error("ONNX session not loaded")
            return None

        arr = np.asarray(face_or_blob, dtype=np.float32)

        # --- If already a 4D blob, assume model-ready ---
        if arr.ndim == 4:
            input_blob = np.ascontiguousarray(arr, dtype=np.float32)
        # --- If raw image crop (H,W,3) ---
        elif arr.ndim == 3 or arr.ndim == 2:
            img = arr
            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            img_resized = cv2.resize(img, (112, 112), interpolation=cv2.INTER_LINEAR)
            # Build blob in NCHW layout
            input_blob = np.transpose(img_resized, (2, 0, 1))[None, ...].astype(np.float32)
        else:
            logger.error("Unsupported input shape: %s", arr.shape)
            return None

        try:
            input_name = self.session.get_inputs()[0].name
            output_name = self.session.get_outputs()[0].name
            result = self.session.run([output_name], {input_name: input_blob})[0]
            return np.asarray(result.flatten(), dtype=np.float32)
        except Exception as e:
            logger.exception("Error running ArcFace ONNX model: %s", e)
            return None
