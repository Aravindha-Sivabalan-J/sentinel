# import numpy as np
# import json
# from pymilvus import connections, Collection

# def main():
#     # 1. Connect to Milvus (same settings as your app)
#     connections.connect("default", host="127.0.0.1", port="19530")

#     # 2. Load the face embeddings collection
#     col = Collection("face_embeddings")
#     col.load()
#     print(f"Collection {col.name} loaded.")

#     # 3. Fetch up to 1000 rows (person_id + embedding + metadata)
#     rows = col.query(
#         expr="person_id != ''",
#         output_fields=["person_id", "embedding", "metadata"],
#         limit=1000
#     )
#     print(f"Fetched {len(rows)} rows")

#     # 4. Prepare data
#     ids, metas, embs = [], [], []
#     for r in rows:
#         ids.append(r["person_id"])
#         try:
#             metas.append(json.loads(r.get("metadata", "{}")))
#         except Exception:
#             metas.append({})
#         embs.append(np.array(r["embedding"], dtype=np.float32))

#     embs = np.vstack(embs)
#     embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-10)

#     # 5. Compare embeddings (cosine similarity & euclidean distance)
#     sims = np.dot(embs, embs.T)  # cosine similarity (since normalized)
#     dists_l2 = np.sum((embs[:, None, :] - embs[None, :, :])**2, axis=-1)

#     # 6. Show the top matches for the first embedding
#     order = np.argsort(-sims[0])  # descending similarity
#     print("\nTop matches for first person in DB:")
#     for i in order[:10]:
#         print(f" - id={ids[i]:20s} cos_sim={sims[0, i]:.6f} "
#               f"cos_dist={1.0 - sims[0, i]:.6f} euclid={dists_l2[0, i]:.6f} "
#               f"meta={metas[i]}")

#     # 7. Check explicitly for Kevin Hart and Dwayne Johnson
#     print("\nExplicit check for Kevin Hart & Dwayne Johnson:")
#     for name in ("Kevin_hart", "Dwayne_johnson"):
#         found = [(i, sims[0, i], dists_l2[0, i]) for i in range(len(ids)) if ids[i] == name]
#         if found:
#             for f in found:
#                 print(f"{name}: index={f[0]} cos_sim={f[1]:.6f} euclid={f[2]:.6f}")
#         else:
#             print(f"{name}: not found in fetched rows.")

# if __name__ == "__main__":
#     main()
