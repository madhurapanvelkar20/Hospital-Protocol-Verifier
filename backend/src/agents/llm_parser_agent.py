"""
LLM-based Prescription Parser Agent.

Unlike parser_agent.py (regex + a hardcoded 16-drug vocabulary), this
version sends the raw prescription text to Claude and asks for structured
JSON back, so it can handle any drug or diagnosis mentioned in free text --
not just the ones in KNOWN_DRUGS/KNOWN_DIAGNOSES.

Enable it by setting PARSER_BACKEND=llm (see src/config.py) and having
ANTHROPIC_API_KEY set in the environment. If the API call fails for any
reason (no key, network error, malformed response), this falls back to the
regex parser automatically -- the pipeline never hard-fails because of it.

NOTE: because this calls an external API, its output should be validated
before being trusted for anything beyond a demo -- see the "Limitations"
note in README.md for how to properly evaluate this against the regex
parser using the benchmark harness.
"""

import json
import os
from typing import Dict, Any

from src.state import VerifierState
from src.agents.parser_agent import (
    _drug_key,
    _extract_drugs,
    finalize_drug_parse,
    parse_prescription as regex_parse_prescription,
)

SYSTEM_PROMPT = """You extract structured data from a clinical prescription note.

Return ONLY a JSON object (no markdown fences, no commentary) with this exact shape:
{
  "drugs": [
    {"name": "<lowercase generic drug name>", "dose": "<e.g. 10mg, or 'unspecified'>",
     "route": "<e.g. oral, IV, topical, or 'oral' if not stated>",
     "frequency": "<e.g. once daily, twice daily, or 'unspecified'>"}
  ],
  "diagnoses": ["<each working diagnosis/indication mentioned, lowercase>"]
}

Rules:
- Include every drug mentioned, even ones you're not fully certain about.
- Use the drug's generic name in lowercase (e.g. "metformin", not "Metformin" or a brand name).
- If a detail isn't stated, use "unspecified" for that field.
- A prescription commonly lists more than one diagnosis (e.g. hypertension AND
  type 2 diabetes) -- include ALL of them in the "diagnoses" list, not just one.
- Do not invent a diagnosis that isn't implied by the text. Use an empty list
  if none is stated."""


def _call_claude(raw_text: str) -> Dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
    )
    text = response.content[0].text.strip()
    # Defensive: strip markdown fences if the model adds them anyway
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def parse_prescription_llm(state: VerifierState) -> Dict[str, Any]:
    """LangGraph-compatible node: same return shape as parser_agent.parse_prescription,
    so it can be swapped in without touching src/graph.py."""
    raw_text = state.get("raw_text", "")
    diagnosis_hint = state.get("diagnosis_hint")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        fallback = regex_parse_prescription(state)
        fallback["parser_warnings"].append({
            "type": "parser_fallback",
            "message": (
                "LLM parsing is configured but no API key is available; the "
                "limited local drug vocabulary parser was used instead."
            ),
        })
        return fallback

    try:
        parsed = _call_claude(raw_text)
        drugs = [
            {
                "name": d.get("name", "").lower().strip(),
                "dose": d.get("dose", "unspecified"),
                "route": d.get("route", "oral"),
                "frequency": d.get("frequency", "unspecified"),
            }
            for d in parsed.get("drugs", [])
            if d.get("name")
        ]
        existing_names = {_drug_key(drug["name"]) for drug in drugs}
        for candidate in _extract_drugs(raw_text):
            if _drug_key(candidate["name"]) not in existing_names:
                drugs.append(candidate)
                existing_names.add(_drug_key(candidate["name"]))

        diagnoses = []
        if diagnosis_hint:
            diagnoses.extend(p.strip().lower() for p in diagnosis_hint.split(",") if p.strip())
        for d in parsed.get("diagnoses") or []:
            d = (d or "").strip().lower()
            if d and d not in diagnoses:
                diagnoses.append(d)

        return {
            **finalize_drug_parse(state, drugs),
            "parsed_diagnoses": diagnoses,
        }
    except Exception:
        fallback = regex_parse_prescription(state)
        fallback["parser_warnings"].append({
            "type": "parser_fallback",
            "message": (
                "The LLM parser request or response failed; the limited local "
                "drug vocabulary parser was used instead. Review extracted "
                "drug names before relying on the result."
            ),
        })
        return fallback


def get_parser():
    """Returns the configured parser function based on src/config.PARSER_BACKEND."""
    from src.config import PARSER_BACKEND

    if PARSER_BACKEND == "llm":
        return parse_prescription_llm
    return regex_parse_prescription
