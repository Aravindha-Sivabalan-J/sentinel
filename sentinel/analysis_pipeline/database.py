# sentinel/analysis_pipeline/database.py

import faiss
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

class FaissManager:
    def __init__(self, index_path='analysis_pipeline/models/face_index.bin', mapping_path='analysis_pipeline/models/index_to_id.json'):
        """
        Initializes the FAISS manager.

        Args:
            index_path (str): Path to save/load the FAISS index file.
            mapping_path (str): Path to save/load the mapping from index ID to a person's identity.
        """
        self.index_path = index_path
        self.mapping_path = mapping_path
        self.dimension = 512
        self.index = None
        
        # A simple list to map the FAISS index position to a unique person ID (e.g., a name or database key)
        self.index_to_id = []

        self.load_index()

    def load_index(self):
        """Loads the FAISS index and the ID mapping from disk if they exist."""
        try:
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                logger.info(f"FAISS index loaded from {self.index_path}. Contains {self.index.ntotal} vectors.")
                
                import json
                with open(self.mapping_path, 'r') as f:
                    self.index_to_id = json.load(f)
                logger.info(f"ID mapping loaded. Contains {len(self.index_to_id)} entries.")
            else:
                self.index = faiss.IndexFlatL2(self.dimension)
                logger.info("No existing FAISS index found. A new one has been created.")
        except Exception as e:
            logger.error(f"Error loading index: {e}. Creating a new index.")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index_to_id = []

    def save_index(self):
        """Saves the FAISS index and the ID mapping to disk."""
        try:
            faiss.write_index(self.index, self.index_path)
            logger.info(f"FAISS index saved to {self.index_path}")
            
            import json
            with open(self.mapping_path, 'w') as f:
                json.dump(self.index_to_id, f)
            logger.info(f"ID mapping saved to {self.mapping_path}")
        except Exception as e:
            logger.error(f"Error saving index: {e}")

    def add_embedding(self, embedding, person_id):
        """
        Adds a new face embedding to the index.

        Args:
            embedding (numpy.ndarray): The 512-d feature vector.
            person_id (str): The unique identifier for the person (e.g., "John_Doe").
        """
        if embedding is None or not isinstance(embedding, np.ndarray):
            logger.warning("Attempted to add an invalid embedding.")
            return

        embedding = embedding.reshape(1, -1).astype('float32')
        
        self.index.add(embedding)
        
        self.index_to_id.append(person_id)
        logger.info(f"Added embedding for '{person_id}'. Index now contains {self.index.ntotal} vectors.")

    def search(self, query_embedding, k=1, threshold=1.2):
        """
        Searches the index for the closest match to a query embedding.

        Args:
            query_embedding (numpy.ndarray): The 512-d vector of the face to search for.
            k (int): The number of nearest neighbors to return.
            threshold (float): The maximum L2 distance to be considered a match.

        Returns:
            tuple: A tuple containing (person_id, distance) if a match is found,
                   otherwise (None, None).
        """
        if self.index.ntotal == 0:
            return None, None

        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        
        # Perform the search
        distances, indices = self.index.search(query_embedding, k)
        
        # Check if the closest match is within our threshold
        if distances[0][0] < threshold:
            person_index = indices[0][0]
            person_id = self.index_to_id[person_index]
            distance = distances[0][0]
            logger.info(f"Match found: '{person_id}' with distance {distance:.4f}")
            return person_id, distance
        else:
            logger.info(f"No match found within threshold. Closest distance: {distances[0][0]:.4f}")
            return None, None


# if __name__ == '__main__':
#     embedding1 = np.random.rand(512).astype('float32')
#     embedding1 /= np.linalg.norm(embedding1)

#     embedding2 = np.random.rand(512).astype('float32')
#     embedding2 /= np.linalg.norm(embedding2)

#     db_manager = FaissManager()
#     db_manager.add_embedding(embedding1, "Person_A")
#     db_manager.add_embedding(embedding2, "Person_B")

#     db_manager.save_index()

#     print("\n--- Searching for a known person (a slightly modified version of Person_A's embedding) ---")
#     query_vector_known = embedding1 + 0.1 * np.random.rand(512)
#     query_vector_known /= np.linalg.norm(query_vector_known)
#     person_id, distance = db_manager.search(query_vector_known)
#     print(f"Search Result: ID = {person_id}, Distance = {distance}")

#     print("\n--- Searching for an unknown person ---")
#     query_vector_unknown = np.random.rand(512).astype('float32')
#     query_vector_unknown /= np.linalg.norm(query_vector_unknown)
#     person_id, distance = db_manager.search(query_vector_unknown)
#     print(f"Search Result: ID = {person_id}, Distance = {distance}")