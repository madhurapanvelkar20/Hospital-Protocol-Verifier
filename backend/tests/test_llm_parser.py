import os
import sys
import types
import json
from unittest.mock import MagicMock

sys.path.insert(0, ".")

# --- Test 1: no API key set -> should silently fall back to regex parser ---
os.environ.pop("ANTHROPIC_API_KEY", None)
from src.agents.llm_parser_agent import parse_prescription_llm

state = {"raw_text": "Prescribe Metformin 500mg oral twice daily for type 2 diabetes.", "diagnosis_hint": None}
result = parse_prescription_llm(state)
assert result["parsed_drugs"], "Expected fallback regex parser to find metformin"
assert result["parsed_drugs"][0]["name"] == "metformin"
print("PASS: falls back to regex parser when no API key is set")

# --- Test 2: mock a successful Claude response and verify JSON parsing ---
os.environ["ANTHROPIC_API_KEY"] = "fake-key-for-testing"

fake_anthropic_module = types.ModuleType("anthropic")


class FakeContent:
    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeContent(text)]


class FakeMessages:
    def create(self, **kwargs):
        fake_json = json.dumps({
            "drugs": [
                {"name": "atorvastatin", "dose": "10mg", "route": "oral", "frequency": "once daily"}
            ],
            "diagnosis": "hyperlipidemia",
        })
        return FakeResponse(fake_json)


class FakeAnthropic:
    def __init__(self):
        self.messages = FakeMessages()


fake_anthropic_module.Anthropic = FakeAnthropic
sys.modules["anthropic"] = fake_anthropic_module

# reload the module so it picks up the fake anthropic module cleanly
import importlib
import src.agents.llm_parser_agent as llm_parser_module
importlib.reload(llm_parser_module)

state2 = {"raw_text": "Start atorvastatin 10mg nightly for high cholesterol.", "diagnosis_hint": None}
result2 = llm_parser_module.parse_prescription_llm(state2)
assert result2["parsed_drugs"][0]["name"] == "atorvastatin", result2
assert result2["parsed_diagnosis"] == "hyperlipidemia", result2
print("PASS: correctly parses a mocked Claude JSON response, including a drug NOT in the regex vocabulary (atorvastatin)")

# --- Test 3: malformed response -> should fall back to regex, not crash ---
class FakeMessagesBroken:
    def create(self, **kwargs):
        return FakeResponse("this is not valid json {{{")


class FakeAnthropicBroken:
    def __init__(self):
        self.messages = FakeMessagesBroken()


fake_anthropic_module.Anthropic = FakeAnthropicBroken
importlib.reload(llm_parser_module)

state3 = {"raw_text": "Prescribe Warfarin 5mg oral once daily.", "diagnosis_hint": None}
result3 = llm_parser_module.parse_prescription_llm(state3)
assert result3["parsed_drugs"][0]["name"] == "warfarin", result3
print("PASS: malformed API response falls back to regex parser without crashing")

print("\nAll LLM parser tests passed.")
