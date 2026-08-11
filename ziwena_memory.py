"""
Ziwena — Memory module (RAG-based long-term memory)
Uses ChromaDB (local, free, no server needed) + a free local embedding model.

This file handles:
  - storing new memories (facts, journal-style notes) permanently on disk
  - retrieving the most relevant memories for a given question
"""

from datetime import datetime, timedelta

# ---------- Persistent local storage ----------
client = None
embedding_fn = None
collection = None
journal_collection = None
_next_id = 0
_next_journal_id = 0
_memory_ready = None


def _init_memory():
    global client, embedding_fn, collection, journal_collection, _next_id, _next_journal_id

    if client is not None:
        return

    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path="ziwena_memory_db")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    collection = client.get_or_create_collection(
        name="ziwena_memories",
        embedding_function=embedding_fn,
    )

    journal_collection = client.get_or_create_collection(
        name="ziwena_journal",
        embedding_function=embedding_fn,
    )

    _next_id = collection.count()
    _next_journal_id = journal_collection.count()


def _ensure_memory() -> bool:
    global _memory_ready
    if _memory_ready is not None:
        return _memory_ready
    try:
        _init_memory()
        _memory_ready = True
    except Exception as e:
        print(f"[Memory: failed to initialize — {e}]")
        _memory_ready = False
    return _memory_ready


def add_memory(text: str):
    """Save a new fact/memory permanently."""
    if not _ensure_memory():
        return
    global _next_id
    if not text or not text.strip():
        return
    collection.add(
        documents=[text.strip()],
        ids=[f"mem_{_next_id}"],
    )
    _next_id += 1


def retrieve_relevant(query: str, top_k: int = 4):
    """Return the most relevant stored memories for the current message."""
    if not _ensure_memory() or collection.count() == 0:
        return []
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )
    return results["documents"][0] if results["documents"] else []


def memory_count():
    if not _ensure_memory():
        return 0
    return collection.count()


# ---------- Compaction (periodic summarization of old raw memories) ----------

COMPACTION_KEEP_RECENT = 40
COMPACTION_BATCH_SIZE = 60
COMPACTION_TRIGGER_AT = 120


def _get_all_with_meta():
    data = collection.get(include=["documents", "metadatas"])
    ids = data["ids"]
    docs = data["documents"]
    metas = data["metadatas"] or [{}] * len(ids)
    metas = [m if m is not None else {} for m in metas]
    return ids, docs, metas


def needs_compaction() -> bool:
    if not _ensure_memory():
        return False
    ids, docs, metas = _get_all_with_meta()
    raw = [i for i, m in zip(ids, metas) if not m.get("is_summary")]
    return len(raw) >= COMPACTION_TRIGGER_AT


def compact_old_memories(genai_client, model_name: str):
    if not _ensure_memory():
        return None

    ids, docs, metas = _get_all_with_meta()
    raw = [(i, d) for i, d, m in zip(ids, docs, metas) if not m.get("is_summary")]

    if len(raw) <= COMPACTION_KEEP_RECENT:
        return None

    def _idx(mem_id):
        try:
            return int(mem_id.split("_")[-1])
        except ValueError:
            return 0

    raw.sort(key=lambda pair: _idx(pair[0]))

    to_compact = raw[: max(0, len(raw) - COMPACTION_KEEP_RECENT)]
    to_compact = to_compact[:COMPACTION_BATCH_SIZE]
    if not to_compact:
        return None

    compact_ids = [i for i, _ in to_compact]
    compact_text = "\n".join(f"- {d}" for _, d in to_compact)

    prompt = (
        "Below are raw memory entries (chat exchanges and saved facts) about "
        "Mahdi, in chronological order. Condense them into a compact set of "
        "durable facts and preferences worth remembering long-term. Drop "
        "small talk, greetings, and anything time-bound or no longer "
        "relevant. Write 5-15 short bullet points, each a standalone fact "
        "(so it makes sense without the original context). No preamble, "
        "just the bullets.\n\n"
        f"{compact_text}"
    )

    try:
        response = genai_client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        summary_text = response.text.strip()
    except Exception as e:
        return f"[Compaction skipped — model call failed: {e}]"

    if not summary_text:
        return None

    global _next_id
    now = datetime.now().isoformat()
    collection.add(
        documents=[summary_text],
        ids=[f"mem_{_next_id}"],
        metadatas=[{"is_summary": True, "compacted_at": now, "source_count": len(compact_ids)}],
    )
    _next_id += 1

    collection.delete(ids=compact_ids)

    return f"[Compacted {len(compact_ids)} old memories into 1 summary]"


# ---------- Journal (structured, timestamped, reflective entries) ----------

def add_journal_entry(text: str):
    """Save a reflective journal entry with a timestamp."""
    if not _ensure_memory():
        return
    global _next_journal_id
    if not text or not text.strip():
        return
    now = datetime.now()
    journal_collection.add(
        documents=[text.strip()],
        ids=[f"journal_{_next_journal_id}"],
        metadatas=[{
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
        }],
    )
    _next_journal_id += 1


def get_journal_entries_since(days: int = 30):
    """Return journal entries from the last N days, oldest first."""
    if not _ensure_memory() or journal_collection.count() == 0:
        return []

    cutoff = datetime.now() - timedelta(days=days)
    all_entries = journal_collection.get(include=["documents", "metadatas"])

    entries = []
    for doc, meta in zip(all_entries["documents"], all_entries["metadatas"]):
        ts = meta.get("timestamp")
        if ts and datetime.fromisoformat(ts) >= cutoff:
            entries.append((ts, doc))

    entries.sort(key=lambda x: x[0])
    return entries


def journal_count():
    if not _ensure_memory():
        return 0
    return journal_collection.count()