import pytest
from pydantic import ValidationError
from src.schemas import (
    Severity, Language, KnowledgeChunk, Product, ProductRecommendation,
    EscalationFlag, AgentResponse, KnowledgeSearchInput, KnowledgeSearchOutput,
    ProductSearchInput, ProductSearchOutput, EscalationCheckInput, EscalationCheckOutput,
)

def test_severity_uses_nice_colors():
    assert Severity.GREEN.value == "green"
    assert Severity.AMBER.value == "amber"
    assert Severity.RED.value == "red"

def test_knowledge_chunk_minimal_valid():
    chunk = KnowledgeChunk(
        chunk_id="kb_001", topic="feeding",
        text_en="Breastfed newborns feed every 2-3 hours.",
        text_ar="المواليد الرضع يرضعون كل ساعتين إلى ثلاث ساعات.",
        source="WHO", source_url="https://www.who.int/",
        severity_tag=Severity.GREEN, age_range_months=(0, 6),
    )
    assert chunk.chunk_id == "kb_001"

def test_product_requires_age_range():
    with pytest.raises(ValidationError):
        Product(
            product_id="p1", name_en="x", name_ar="x", category="feeding",
            price_aed=10.0, description_en="x", description_ar="x", tags=[],
        )

def test_product_recommendation_score_bounds():
    p = Product(
        product_id="p1", name_en="x", name_ar="x", category="feeding",
        age_range_months=(0, 6), price_aed=10.0,
        description_en="x", description_ar="x", tags=[],
    )
    with pytest.raises(ValidationError):
        ProductRecommendation(product=p, relevance_score=1.5, reasoning_en="x")

def test_agent_response_serializes_enum_values():
    resp = AgentResponse(
        user_input_text="hi", user_input_language=Language.EN,
        response_language=Language.EN, response_text="hello",
        confidence=0.9, in_scope=True,
    )
    dumped = resp.model_dump()
    assert dumped["user_input_language"] == "en"
