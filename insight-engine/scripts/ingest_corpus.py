"""
A script to ingest the entire project corpus into a Qdrant collection.
"""

import os
import glob
from insight_engine.tools.vector_store import embed_and_upload

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FILE_PATTERNS = [
    "**/*.md",
    "**/*.py",
    "**/*.toml",
    "**/*.json",
]
CHUNK_SIZE = 2000


def chunk_text(text, size=CHUNK_SIZE):
    """Splits text into chunks of a specified size."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def ingest_corpus():
    """
    Scans the project, chunks the files, and ingests them into Qdrant.
    """
    print("Starting project corpus ingestion...")

    # 1. Find all relevant files
    all_files = []
    for pattern in FILE_PATTERNS:
        for file_path in glob.glob(os.path.join(PROJECT_ROOT, pattern), recursive=True):
            if "venv" in file_path or "node_modules" in file_path:
                continue
            all_files.append(file_path)

    print(f"Found {len(all_files)} files to ingest.")

    # 2. Read, chunk, and ingest each file
    total_chunks = 0
    for file_path in all_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                chunks = chunk_text(text)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{os.path.relpath(file_path, PROJECT_ROOT)}#{i}"
                    metadata = {"source": os.path.relpath(file_path, PROJECT_ROOT)}
                    embed_and_upload(id=doc_id, text=chunk, metadata=metadata)
                total_chunks += len(chunks)
                print(f"Ingested {len(chunks)} chunks from {file_path}")
        except Exception as e:
            print(f"Could not read or ingest file {file_path}: {e}")

    print(f"✅ Ingestion complete. Total chunks ingested: {total_chunks}")


if __name__ == "__main__":
    ingest_corpus()
