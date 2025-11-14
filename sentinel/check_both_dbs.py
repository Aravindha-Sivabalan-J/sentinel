#!/usr/bin/env python3
import chromadb

print("=" * 60)
print("CHECKING: analysis_pipeline/production_db")
print("=" * 60)
try:
    client1 = chromadb.PersistentClient(path="analysis_pipeline/production_db")
    collections1 = client1.list_collections()
    print(f"Found {len(collections1)} collections:")
    for col in collections1:
        print(f"  - {col.name}: {col.count()} items")
        if col.count() > 0:
            data = col.get(limit=10)
            print(f"    IDs: {data['ids']}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("CHECKING: chroma_data")
print("=" * 60)
try:
    client2 = chromadb.PersistentClient(path="chroma_data")
    collections2 = client2.list_collections()
    print(f"Found {len(collections2)} collections:")
    for col in collections2:
        print(f"  - {col.name}: {col.count()} items")
        if col.count() > 0:
            data = col.get(limit=10)
            print(f"    IDs: {data['ids']}")
except Exception as e:
    print(f"Error: {e}")
