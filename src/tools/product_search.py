"""Product retrieval with optional age-range filter and per-product reasoning."""
import lancedb

from src.config import LANCE_DB_PATH, PRODUCTS_TABLE, PRODUCT_MIN_CONFIDENCE
from src.index_kb import embed_text
from src.schemas import (
    ProductSearchInput, ProductSearchOutput, Product, ProductRecommendation,
)


_FIELDS = {
    "product_id", "name_en", "name_ar", "category", "age_range_months",
    "price_aed", "description_en", "description_ar", "tags",
}


def _age_overlaps(product_range: tuple[int, int], filter_range: tuple[int, int]) -> bool:
    p_lo, p_hi = product_range
    f_lo, f_hi = filter_range
    return not (p_hi < f_lo or p_lo > f_hi)


def search_products(input: ProductSearchInput) -> ProductSearchOutput:
    db = lancedb.connect(LANCE_DB_PATH)
    table = db.open_table(PRODUCTS_TABLE)
    query_vec = embed_text(input.query)
    rows = table.search(query_vec).metric("cosine").limit(max(input.max_results * 3, 9)).to_list()

    recs: list[ProductRecommendation] = []
    for r in rows:
        sim = 1.0 - float(r.get("_distance", 1.0))
        if sim < PRODUCT_MIN_CONFIDENCE:
            continue
        payload = {k: v for k, v in r.items() if k in _FIELDS}
        if isinstance(payload.get("age_range_months"), list):
            payload["age_range_months"] = tuple(payload["age_range_months"])
        product = Product(**payload)
        if input.age_range_months and not _age_overlaps(product.age_range_months, input.age_range_months):
            continue
        recs.append(ProductRecommendation(
            product=product,
            relevance_score=round(sim, 3),
            reasoning_en=f"Matched on '{input.query}' (similarity {sim:.2f}).",
        ))
        if len(recs) >= input.max_results:
            break

    return ProductSearchOutput(recommendations=recs)
