#!/usr/bin/env python3
import chromadb

client = chromadb.PersistentClient(path="analysis_pipeline/production_db")
collections = client.list_collections()

print(f"Found {len(collections)} collections:")
for col in collections:
    print(f"\n  Collection: {col.name}")
    count = col.count()
    print(f"  Count: {count}")
    if count > 0:
        data = col.get(limit=5)
        print(f"  Sample IDs: {data['ids']}")
