# analysis_pipeline/vector_db.py
import logging
import json
import numpy as np
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ChromaDBManager:
    def __init__(self, persist_directory="./chroma_data", collection_name="face_embeddings"):
        """
        Initialize ChromaDB client and collection.
        DeepFace-style embeddings are stored directly (already normalized).
        """
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=persist_directory)

        existing_collections = [c.name for c in self.client.list_collections()]
        if collection_name not in existing_collections:
            logger.info(f"Creating new collection: {collection_name}")
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Face embeddings collection"},
                embedding_function=None  # embeddings are precomputed manually
            )
        else:
            logger.info(f"Loading existing collection: {collection_name}")
            self.collection = self.client.get_collection(name=collection_name)

    def add_person(self, person_id: str, embedding: np.ndarray, metadata: dict):
        """
        Add or update a person's embedding in the ChromaDB collection.
        The embedding should already be L2-normalized (like DeepFace).
        """
        try:
            # Ensure numpy array and float32
            emb = np.asarray(embedding, dtype=np.float32)

            # Check if the ID already exists — delete old record if so
            existing = self.collection.get(ids=[person_id])
            if existing and len(existing.get("ids", [])) > 0:
                self.collection.delete(ids=[person_id])
                logger.info(f"Deleted existing entry for {person_id} before re-inserting.")

            logger.info(f"[ADD_PERSON] id={person_id} shape={emb.shape} first10={emb[:10]}")

            # Insert embedding directly (no normalization or flattening)
            self.collection.add(
                ids=[person_id],
                embeddings=[emb.tolist()],
                metadatas=[metadata],
                documents=[json.dumps(metadata)]
            )

            logger.info(f"Added {person_id} to ChromaDB.")

        except Exception as e:
            logger.exception(f"Failed to add {person_id}: {e}")
            raise

    def search_person(self, query_embedding: np.ndarray, k=5, threshold=0.30):
        """
        Search the closest person using cosine similarity.
        Assumes both stored and query embeddings are L2-normalized,
        consistent with DeepFace and ArcFace behavior.
        """
        try:
            q = np.asarray(query_embedding, dtype=np.float32)

            results = self.collection.query(
                query_embeddings=[q.tolist()],
                n_results=k,
                include=["embeddings", "metadatas", "documents", "distances"]
            )

            if not results or not results.get("ids") or not results["ids"][0]:
                logger.warning("No vectors found in ChromaDB.")
                return "NO MATCH FOUND", None, None

            candidates = []
            embeddings_list = results.get("embeddings", [[None]])[0]

            for i, pid in enumerate(results["ids"][0]):
                emb_stored = np.array(embeddings_list[i], dtype=np.float32)
                sim = float(np.dot(q, emb_stored))  # cosine similarity (since normalized)
                meta = results["metadatas"][0][i]
                candidates.append((pid, sim, meta))

            if not candidates:
                return "NO MATCH FOUND", None, None

            # Sort by similarity
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_id, best_sim, best_meta = candidates[0]

            if best_sim >= threshold:
                logger.info(f"✅ Verified match: {best_id} (sim={best_sim:.4f})")
                return best_id, 1.0 - best_sim, best_meta
            else:
                logger.info(f"❌ No verified match (best={best_id}, sim={best_sim:.4f})")
                return "NO MATCH FOUND", None, None

        except Exception as e:
            logger.exception("Search failed:")
            return "NO MATCH FOUND", None, None
