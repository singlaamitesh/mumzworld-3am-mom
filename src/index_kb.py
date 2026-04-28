"""One-shot indexer. Embeds KB and product catalog into LanceDB.

Run: python -m src.index_kb
"""
import json
import time
import requests
import lancedb
import pyarrow as pa

from src.config import (
    OPENROUTER_API_KEY, EMBED_MODEL, LANCE_DB_PATH, KB_TABLE, PRODUCTS_TABLE,
    KB_PATH, PRODUCTS_PATH,
)


def embed_text(text: str, retries: int = 3, sleep: float = 1.0) -> list[float]:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": EMBED_MODEL, "input": text}
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers=headers, json=payload, timeout=30,
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
        except Exception as e:
            last_err = e
            time.sleep(sleep * (2 ** attempt))
    raise RuntimeError(f"embed_text failed after {retries} attempts: {last_err}")


def index_knowledge_base(db) -> None:
    chunks = json.load(open(KB_PATH))
    rows = []
    for c in chunks:
        text = (c["text_en"] or "") + " " + (c["text_ar"] or "")
        vec = embed_text(text)
        row = dict(c)
        # tuples become lists when JSON-serialized; LanceDB tolerates lists
        if row.get("age_range_months") is not None:
            row["age_range_months"] = list(row["age_range_months"])
        row["vector"] = vec
        rows.append(row)
        print(f"  embedded kb chunk {c['chunk_id']}")

    if KB_TABLE in db.table_names():
        db.drop_table(KB_TABLE)
    db.create_table(KB_TABLE, data=rows)
    print(f"Indexed {len(rows)} KB chunks into '{KB_TABLE}'.")


def index_products(db) -> None:
    products = json.load(open(PRODUCTS_PATH))
    rows = []
    for p in products:
        text_parts = [p["name_en"], p["name_ar"], p["description_en"], p["description_ar"]]
        text_parts.extend(p.get("tags", []))
        text = " ".join(text_parts)
        vec = embed_text(text)
        row = dict(p)
        row["age_range_months"] = list(row["age_range_months"])
        row["vector"] = vec
        rows.append(row)
        print(f"  embedded product {p['product_id']}")

    if PRODUCTS_TABLE in db.table_names():
        db.drop_table(PRODUCTS_TABLE)
    db.create_table(PRODUCTS_TABLE, data=rows)
    print(f"Indexed {len(rows)} products into '{PRODUCTS_TABLE}'.")


def main():
    if not OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY not set in .env")
    db = lancedb.connect(LANCE_DB_PATH)
    index_knowledge_base(db)
    index_products(db)
    print("Done.")


if __name__ == "__main__":
    main()
