import pytest
from pathlib import Path
from src.config import LANCE_DB_PATH
from src.schemas import KnowledgeSearchInput
from src.tools.knowledge_search import search_knowledge


pytestmark = pytest.mark.skipif(
    not Path(LANCE_DB_PATH).exists(),
    reason="LanceDB not indexed yet; run `python -m src.index_kb` first.",
)


def test_search_returns_chunks_for_feeding_query():
    out = search_knowledge(KnowledgeSearchInput(query="how often to breastfeed newborn", top_k=3))
    assert len(out.chunks) >= 1
    assert out.confidence > 0.5


def test_search_arabic_query():
    out = search_knowledge(KnowledgeSearchInput(query="كم مرة أرضع طفلي", top_k=3))
    assert len(out.chunks) >= 1
