"""NICE NG143 traffic-light pediatric red-flag rule engine.

Hard-coded patterns (not LLM) for: deterministic safety, audit trail, low latency.
Reference: https://www.nice.org.uk/guidance/ng143
"""
import re
from src.schemas import EscalationCheckInput, EscalationCheckOutput, EscalationFlag, Severity

# NICE NG143-derived categories. Each maps to one or more regex patterns (EN + AR).
RED_FLAG_PATTERNS: dict[str, list[str]] = {
    "fever_high_temp": [
        r"\b(fever|temperature|حرارة|حراره|سخونة)\b.*?\b(3[89]|4[0-2])(\.\d)?\b",
        r"\b(38\.[5-9]|39|40|41|42)\b",
        r"\bحرارته?\s*(ثمان(ية)?\s*و?ثلاث(ين|ون)|تسع(ة)?\s*و?ثلاث(ين|ون)|أربع(ين|ون))\b",
    ],
    "fever_under_3_months": [
        r"\b(newborn|6\s*weeks?|2\s*month|3\s*month|أسبوع|شهر|شهرين)\b.*\b(fever|hot|temperature|حرارة|سخونة)\b",
    ],
    "breathing_distress": [
        r"\b(can'?t breathe|trouble breathing|wheezing|blue lips|gasping|retractions)\b",
        r"\b(ضيق(\s*في\s*)?النفس|يلهث|يزرق|ما يقدر يتنفس)\b",
    ],
    "consciousness_red": [
        r"\b(unconscious|won'?t wake|not responding|extremely lethargic|limp)\b",
        r"\b(فاقد(ة)?\s*الوعي|ما يصحى|ما يرد|مغمى عليه)\b",
    ],
    "seizure": [
        r"\b(seizure|convulsion|fitting|febrile fit)\b",
        r"\b(تشنج|اختلاج|نوبة)\b",
    ],
    "blood_in_output": [
        r"\b(blood)\b.*\b(stool|vomit|poop|diaper|spit ?up)\b",
        r"\b(دم|نزيف)\b.*\b(براز|قي|استفراغ|حفاضة)\b",
    ],
    "hydration_red": [
        r"\b(no\s+wet\s+diaper(s)?|sunken\s+(fontanelle|eyes)|dry mouth|no tears)\b",
        r"\b(ما يبول|ما بال|غارت العين|جفاف شديد|ما يطلع دموع)\b",
        r"\b(has(n'?t|\s+not)\s+(had\s+(a\s+)?)?wet\s+diaper)\b",
    ],
    "head_injury": [
        r"\b(head injury|hit (his|her|the) head|fell (off|from)|skull)\b",
        r"\b(طاح|ضرب راسه|سقط على راسه|وقع على راسه)\b",
    ],
    "poisoning_choking": [
        r"\b(swallowed|choking|poison|ingested)\b",
        r"\b(بلع|اختناق|تسمم)\b",
    ],
    "explicit_emergency": [
        r"\b(emergency|er\b|hospital|ambulance|911|997|998)\b",
        r"\b(طوارئ|مستشفى|إسعاف)\b",
    ],
}

ADVICE_EN = (
    "Please contact your pediatrician immediately or go to the nearest emergency room. "
    "This needs medical attention right now."
)
ADVICE_AR = (
    "تواصلي مع طبيب الأطفال الحين أو روحي أقرب طوارئ. "
    "هالحالة تحتاج رعاية طبية بسرعة."
)


def _has_arabic(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text))


def check_escalation(input: EscalationCheckInput) -> EscalationCheckOutput:
    text = input.user_text
    triggered: list[str] = []
    for category, patterns in RED_FLAG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.UNICODE):
                triggered.append(category)
                break

    if triggered:
        advice = ADVICE_AR if _has_arabic(text) else ADVICE_EN
        return EscalationCheckOutput(
            flag=EscalationFlag(
                triggered=True,
                severity=Severity.RED,
                triggers=triggered,
                advice=advice,
            )
        )
    return EscalationCheckOutput(
        flag=EscalationFlag(
            triggered=False,
            severity=Severity.GREEN,
            triggers=[],
            advice="",
        )
    )
