import logging
import json
import numpy as np
import chromadb
from chromadb.config import Settings
import joblib
import os

logger = logging.getLogger(__name__)

class DualChromaDBManager:
    """Manages two separate ChromaDB collections for ArcFace and FaceNet-512 embeddings"""
    
    def __init__(self, persist_directory="analysis_pipeline/production_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Load classifier
        classifier_path = os.path.join(os.path.dirname(__file__), 'models', 'face_match_classifier.pkl')
        if os.path.exists(classifier_path):
            classifier_data = joblib.load(classifier_path)
            self.classifier = classifier_data['model']
            self.scaler = classifier_data['scaler']
            self.classifier_threshold = classifier_data['threshold']
            self.classifier_approach = classifier_data.get('approach', 'Standard')
            logger.info(f"✅ Loaded classifier ({self.classifier_approach}) with threshold={self.classifier_threshold:.4f}")
        else:
            self.classifier = None
            self.scaler = None
            self.classifier_threshold = None
            self.classifier_approach = None
            logger.warning("⚠️ Classifier not found - using only dual model matching")
        
        # Delete old collections if they exist
        existing = [c.name for c in self.client.list_collections()]
        if "face_embeddings" in existing:
            self.client.delete_collection("face_embeddings")
            logger.info("Deleted old 'face_embeddings' collection")
        
        # Create/get ArcFace collection
        if "arcface_faces" in existing:
            self.arcface_collection = self.client.get_collection("arcface_faces")
            logger.info("Loaded existing 'arcface_faces' collection")
        else:
            self.arcface_collection = self.client.create_collection(
                name="arcface_faces",
                metadata={"description": "ArcFace embeddings"},
                embedding_function=None
            )
            logger.info("Created new 'arcface_faces' collection")
        
        # Create/get FaceNet collection
        if "facenet_faces" in existing:
            self.facenet_collection = self.client.get_collection("facenet_faces")
            logger.info("Loaded existing 'facenet_faces' collection")
        else:
            self.facenet_collection = self.client.create_collection(
                name="facenet_faces",
                metadata={"description": "FaceNet-512 embeddings"},
                embedding_function=None
            )
            logger.info("Created new 'facenet_faces' collection")
    
    def add_person(self, person_id: str, arcface_emb: np.ndarray, facenet_emb: np.ndarray, metadata: dict):
        """Add person to both collections with same ID and metadata"""
        try:
            arc_emb = np.asarray(arcface_emb, dtype=np.float32)
            fn_emb = np.asarray(facenet_emb, dtype=np.float32)
            
            # Delete existing entries if present
            try:
                self.arcface_collection.delete(ids=[person_id])
                self.facenet_collection.delete(ids=[person_id])
            except:
                pass
            
            # Add to ArcFace collection
            self.arcface_collection.add(
                ids=[person_id],
                embeddings=[arc_emb.tolist()],
                metadatas=[metadata],
                documents=[json.dumps(metadata)]
            )
            
            # Add to FaceNet collection
            self.facenet_collection.add(
                ids=[person_id],
                embeddings=[fn_emb.tolist()],
                metadatas=[metadata],
                documents=[json.dumps(metadata)]
            )
            
            logger.info(f"✅ Added {person_id} to both collections")
            
        except Exception as e:
            logger.exception(f"Failed to add {person_id}: {e}")
            raise
    
    def search_person(self, arcface_emb: np.ndarray, facenet_emb: np.ndarray, k=5, 
                     arc_threshold=0.30, fn_threshold=0.30):
        """
        Search using both embeddings and combine results.
        Simple ensemble: both models must agree on same person and both scores must pass thresholds.
        """
        try:
            arc_q = np.asarray(arcface_emb, dtype=np.float32)
            fn_q = np.asarray(facenet_emb, dtype=np.float32)
            
            # Query ArcFace collection
            arc_results = self.arcface_collection.query(
                query_embeddings=[arc_q.tolist()],
                n_results=k,
                include=["embeddings", "metadatas", "distances"]
            )
            
            # Query FaceNet collection
            fn_results = self.facenet_collection.query(
                query_embeddings=[fn_q.tolist()],
                n_results=k,
                include=["embeddings", "metadatas", "distances"]
            )
            
            # Check if both collections have results
            if not arc_results or not arc_results.get("ids") or not arc_results["ids"][0]:
                logger.warning("No results from ArcFace collection")
                return "NO MATCH FOUND", None, None
            
            if not fn_results or not fn_results.get("ids") or not fn_results["ids"][0]:
                logger.warning("No results from FaceNet collection")
                return "NO MATCH FOUND", None, None
            
            # Get top matches from each model
            arc_top_id = arc_results["ids"][0][0]
            arc_top_meta = arc_results["metadatas"][0][0]
            arc_emb_stored = np.array(arc_results["embeddings"][0][0], dtype=np.float32)
            arc_sim = float(np.dot(arc_q, arc_emb_stored))
            
            fn_top_id = fn_results["ids"][0][0]
            fn_top_meta = fn_results["metadatas"][0][0]
            fn_emb_stored = np.array(fn_results["embeddings"][0][0], dtype=np.float32)
            fn_sim = float(np.dot(fn_q, fn_emb_stored))
            
            logger.info(f"[SEARCH] ArcFace: {arc_top_id} (sim={arc_sim:.4f})")
            logger.info(f"[SEARCH] FaceNet: {fn_top_id} (sim={fn_sim:.4f})")
            
            # Simple ensemble: both models must agree on same person AND pass thresholds
            if arc_top_id == fn_top_id:
                # Both models agree - check thresholds
                if arc_sim >= arc_threshold and fn_sim >= fn_threshold:
                    # Calculate features for classifier
                    avg_score = (arc_sim + fn_sim) / 2.0
                    min_score = min(arc_sim, fn_sim)
                    max_score = max(arc_sim, fn_sim)
                    score_diff = abs(arc_sim - fn_sim)
                    
                    # Classifier disabled - using only dual model agreement
                    avg_score = (arc_sim + fn_sim) / 2.0
                    logger.info(f"✅ MATCH: {arc_top_id} (arc={arc_sim:.4f}, fn={fn_sim:.4f}, avg={avg_score:.4f})")
                    return arc_top_id, 1.0 - avg_score, arc_top_meta
                else:
                    logger.info(f"❌ Same person but low confidence (arc={arc_sim:.4f}, fn={fn_sim:.4f})")
                    return "NO MATCH FOUND", None, None
            else:
                logger.info(f"❌ Models disagree: ArcFace={arc_top_id}, FaceNet={fn_top_id}")
                return "NO MATCH FOUND", None, None
            
        except Exception as e:
            logger.exception("Search failed:")
            return "NO MATCH FOUND", None, None
