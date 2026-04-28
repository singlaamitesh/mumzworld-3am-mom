import pytest
from src.schemas import EscalationCheckInput, Severity
from src.tools.escalation_check import check_escalation


def _check(text: str):
    return check_escalation(EscalationCheckInput(user_text=text))


def test_no_symptom_returns_not_triggered():
    out = _check("What thermometer should I buy?")
    assert out.flag.triggered is False
    assert out.flag.severity == Severity.GREEN


def test_fever_with_high_temp_triggers():
    out = _check("My baby has a fever of 39 degrees")
    assert out.flag.triggered is True
    assert out.flag.severity == Severity.RED
    assert "fever_high_temp" in out.flag.triggers


def test_breathing_distress_triggers():
    out = _check("My baby has trouble breathing and blue lips")
    assert out.flag.triggered is True
    assert "breathing_distress" in out.flag.triggers


def test_seizure_triggers():
    out = _check("My baby just had a seizure")
    assert out.flag.triggered is True
    assert "seizure" in out.flag.triggers


def test_arabic_seizure_triggers():
    out = _check("ابني صار عنده تشنج")
    assert out.flag.triggered is True
    assert "seizure" in out.flag.triggers


def test_arabic_advice_returned_for_arabic_input():
    out = _check("ابني يلهث وما يقدر يتنفس")
    assert out.flag.triggered is True
    assert any(c in out.flag.advice for c in "أبجدهوزحطيكلمنسعفصقرشتثخذضظغ")


def test_english_advice_returned_for_english_input():
    out = _check("emergency, my baby is unconscious")
    assert out.flag.triggered is True
    assert "pediatrician" in out.flag.advice.lower() or "emergency" in out.flag.advice.lower()


def test_blood_in_stool_triggers():
    out = _check("There's blood in my baby's stool")
    assert out.flag.triggered is True
    assert "blood_in_output" in out.flag.triggers


def test_dehydration_triggers():
    out = _check("She has not had a wet diaper in 10 hours")
    assert out.flag.triggered is True
    assert "hydration_red" in out.flag.triggers


def test_explicit_emergency_word_triggers():
    out = _check("Should I take her to the ER?")
    assert out.flag.triggered is True
    assert "explicit_emergency" in out.flag.triggers
