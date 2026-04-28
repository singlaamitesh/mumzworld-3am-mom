from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Language(str, Enum):
    EN = "en"
    AR_KHALEEJI = "ar-khaleeji"
    AR_MSA = "ar-msa"
    UNKNOWN = "unknown"


class KnowledgeChunk(BaseModel):
    chunk_id: str
    topic: str
    text_en: str
    text_ar: str
    source: str
    source_url: Optional[str] = None
    severity_tag: Severity
    age_range_months: Optional[tuple[int, int]] = None


class Product(BaseModel):
    product_id: str
    name_en: str
    name_ar: str
    category: str
    age_range_months: tuple[int, int]
    price_aed: float
    description_en: str
    description_ar: str
    tags: list[str]


class ProductRecommendation(BaseModel):
    product: Product
    relevance_score: float = Field(ge=0.0, le=1.0)
    reasoning_en: str


class EscalationFlag(BaseModel):
    triggered: bool
    severity: Severity
    triggers: list[str]
    advice: str


class AgentResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_input_text: str
    user_input_language: Language
    response_language: Language
    response_text: str
    knowledge_chunks_used: list[KnowledgeChunk] = Field(default_factory=list)
    products_recommended: list[ProductRecommendation] = Field(default_factory=list)
    escalation: Optional[EscalationFlag] = None
    confidence: float = Field(ge=0.0, le=1.0)
    in_scope: bool


class KnowledgeSearchInput(BaseModel):
    query: str
    top_k: int = 3


class KnowledgeSearchOutput(BaseModel):
    chunks: list[KnowledgeChunk]
    confidence: float


class ProductSearchInput(BaseModel):
    query: str
    age_range_months: Optional[tuple[int, int]] = None
    max_results: int = 3


class ProductSearchOutput(BaseModel):
    recommendations: list[ProductRecommendation]


class EscalationCheckInput(BaseModel):
    user_text: str


class EscalationCheckOutput(BaseModel):
    flag: EscalationFlag
