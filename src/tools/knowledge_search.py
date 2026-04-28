"""KB retrieval. Embeds query, cosine-searches LanceDB, filters by confidence."""
import lancedb

from src.config import LANCE_DB_PATH, KB_TABLE, KB_MIN_CONFIDENCE
from src.index_kb import embed_text
from src.schemas import KnowledgeSearchInput, KnowledgeSearchOutput, KnowledgeChunk


_FIELDS = {
    "chunk_id", "topic", "text_en", "text_ar", "source", "source_url",
    "severity_tag", "age_range_months",
}


def search_knowledge(input: KnowledgeSearchInput) -> KnowledgeSearchOutput:
    db = lancedb.connect(LANCE_DB_PATH)
    table = db.open_table(KB_TABLE)
    query_vec = embed_text(input.query)
    rows = table.search(query_vec).metric("cosine").limit(input.top_k).to_list()
    if not rows:
        return KnowledgeSearchOutput(chunks=[], confidence=0.0)

    chunks: list[KnowledgeChunk] = []
    similarities: list[float] = []
    for r in rows:
        sim = 1.0 - float(r.get("_distance", 1.0))
        similarities.append(sim)
        if sim < KB_MIN_CONFIDENCE:
            continue
        payload = {k: v for k, v in r.items() if k in _FIELDS}
        if isinstance(payload.get("age_range_months"), list):
            payload["age_range_months"] = tuple(payload["age_range_months"])
        chunks.append(KnowledgeChunk(**payload))

    top_conf = max(similarities) if similarities else 0.0
    return KnowledgeSearchOutput(chunks=chunks, confidence=top_conf)
