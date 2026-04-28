import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROMPTS_DIR = ROOT / "src" / "prompts"

# Gemini API (Google AI Studio) — voice ONLY
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# OpenRouter — text agent, eval judge, embeddings
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
USE_ELEVENLABS_FALLBACK = os.environ.get("USE_ELEVENLABS_FALLBACK", "false").lower() == "true"

# Voice (via google-genai Live)
LIVE_MODEL = "gemini-3.1-flash-live-preview"

# Text agent + judge (via OpenRouter, OpenAI-compatible API)
# Picked from currently-available free tool-calling models on OpenRouter.
# Cross-family pairing avoids same-model self-grading.
AGENT_MODEL = "openai/gpt-oss-20b:free"    # text mode + eval entry point — same family as 120b but ~5x faster
JUDGE_MODEL = "z-ai/glm-4.5-air:free"      # eval judge (different family; multilingual incl. Arabic)
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"

LANCE_DB_PATH = str(DATA_DIR / "lance_kb")
KB_TABLE = "knowledge_base"
PRODUCTS_TABLE = "products"

KB_MIN_CONFIDENCE = 0.3       # tuned after observing Nemotron AR embeddings cluster ~0.33 for valid matches
PRODUCT_MIN_CONFIDENCE = 0.45 # tighter: 15-item catalog needs a real signal-vs-noise gap, not just any-match

KB_PATH = DATA_DIR / "knowledge_base.json"
PRODUCTS_PATH = DATA_DIR / "products.json"
TEST_CASES_PATH = DATA_DIR / "test_cases.json"
