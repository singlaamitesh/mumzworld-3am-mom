"""Run all eval cases through the agent, score with the OpenRouter Qwen 2.5 72B judge.

Run: python -m evals.run_evals
"""
import json
import re
from pathlib import Path
from openai import OpenAI

from src.config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, JUDGE_MODEL,
    TEST_CASES_PATH, PROMPTS_DIR,
)
from src.agent import Agent


JUDGE_PROMPT = (PROMPTS_DIR / "eval_judge_prompt.md").read_text()
RESULTS_PATH = Path(__file__).parent / "results.json"


def _judge(client: OpenAI, case: dict, agent_response: dict) -> dict:
    case_blob = json.dumps(
        {k: case[k] for k in ("id", "category", "input_text", "expected_behavior", "must_call_tool", "must_not_fabricate")},
        ensure_ascii=False,
    )
    response_blob = json.dumps({
        "response_text": agent_response.get("response_text"),
        "escalation": agent_response.get("escalation"),
        "knowledge_chunks_used_ids": [c.get("chunk_id") for c in agent_response.get("knowledge_chunks_used", [])],
        "products_recommended_ids": [r["product"]["product_id"] for r in agent_response.get("products_recommended", [])],
        "response_language": agent_response.get("response_language"),
    }, ensure_ascii=False)

    user_msg = (
        f"{JUDGE_PROMPT}\n\nTEST CASE:\n{case_blob}\n\n"
        f"AGENT RESPONSE:\n{response_blob}\n\nReturn the JSON now."
    )
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": user_msg}],
        extra_headers={
            "HTTP-Referer": "https://github.com/singlaamitesh/mumzworld-3am-mom",
            "X-Title": "3am Mom evals",
        },
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"groundedness": 0, "safety": 0, "language": 0, "product": 0, "notes": f"unparseable judge output: {raw[:200]}"}


def main():
    if not OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY not set")
    cases = json.load(open(TEST_CASES_PATH))
    agent = Agent()
    judge_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

    results = []
    totals = {"groundedness": 0, "safety": 0, "language": 0, "product": 0}
    for case in cases:
        print(f"\n>>> Running {case['id']} ({case['category']})")
        try:
            agent_resp = agent.turn(case["input_text"]).model_dump()
        except Exception as e:
            agent_resp = {"response_text": f"<agent error: {e}>", "escalation": None,
                          "knowledge_chunks_used": [], "products_recommended": [], "response_language": "unknown"}
        print(f"    A: {agent_resp.get('response_text','')[:120]}")
        scores = _judge(judge_client, case, agent_resp)
        print(f"    Scores: {scores}")
        results.append({"case": case, "agent_response": agent_resp, "scores": scores})
        for k in totals:
            totals[k] += int(scores.get(k, 0))

    json.dump(results, open(RESULTS_PATH, "w"), ensure_ascii=False, indent=2)

    print("\n===== SUMMARY =====")
    n = len(cases)
    for k, v in totals.items():
        print(f"  {k:14s}: {v}/{2*n}")
    print(f"  TOTAL         : {sum(totals.values())}/{8*n}")
    print(f"\nResults: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
