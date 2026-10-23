"""Tests for the optional LLM parser and its regex fallback."""

import importlib
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _mock_anthropic(monkeypatch, response_text):
    fake_anthropic = types.ModuleType("anthropic")

    class FakeMessages:
        def create(self, **_kwargs):
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text=response_text)]
            )

    class FakeAnthropic:
        def __init__(self):
            self.messages = FakeMessages()

    fake_anthropic.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)


def test_no_api_key_uses_regex_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import src.agents.llm_parser_agent as llm_parser_module

    importlib.reload(llm_parser_module)
    result = llm_parser_module.parse_prescription_llm({
        "raw_text": "Prescribe Metformin 500mg oral twice daily for type 2 diabetes.",
        "diagnosis_hint": None,
    })
    assert result["parsed_drugs"][0]["name"] == "metformin"


def test_successful_llm_response_preserves_drug_and_multiple_diagnoses(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _mock_anthropic(monkeypatch, json.dumps({
        "drugs": [
            {"name": "atorvastatin", "dose": "10mg", "route": "oral", "frequency": "once daily"}
        ],
        "diagnoses": ["hyperlipidemia", "hypertension"],
    }))
    import src.agents.llm_parser_agent as llm_parser_module

    importlib.reload(llm_parser_module)
    result = llm_parser_module.parse_prescription_llm({
        "raw_text": "Atorvastatin 10mg once daily",
        "diagnosis_hint": None,
    })
    assert result["parsed_drugs"][0]["name"] == "atorvastatin"
    assert result["parsed_drugs"][0]["recognized"] is True
    assert result["parsed_diagnoses"] == ["hyperlipidemia", "hypertension"]


def test_malformed_llm_response_falls_back_without_leaking_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _mock_anthropic(monkeypatch, "this is not valid json {{{")
    import src.agents.llm_parser_agent as llm_parser_module

    importlib.reload(llm_parser_module)
    result = llm_parser_module.parse_prescription_llm({
        "raw_text": "Prescribe Warfarin 5mg oral once daily.",
        "diagnosis_hint": None,
    })
    assert result["parsed_drugs"][0]["name"] == "warfarin"
