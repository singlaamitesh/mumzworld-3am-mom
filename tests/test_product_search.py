import pytest
from pathlib import Path
from src.config import LANCE_DB_PATH
from src.schemas import ProductSearchInput
from src.tools.product_search import search_products


pytestmark = pytest.mark.skipif(
    not Path(LANCE_DB_PATH).exists(),
    reason="LanceDB not indexed yet.",
)


def test_thermometer_query_returns_thermometer():
    out = search_products(ProductSearchInput(query="forehead thermometer for fever", max_results=3))
    assert len(out.recommendations) >= 1
    top = out.recommendations[0].product
    assert "thermometer" in (top.name_en + " " + " ".join(top.tags)).lower()


def test_age_filter_excludes_out_of_range():
    out = search_products(ProductSearchInput(
        query="sleep sack", age_range_months=(0, 2), max_results=3,
    ))
    for rec in out.recommendations:
        lo, hi = rec.product.age_range_months
        assert not (hi < 0 or lo > 2)
