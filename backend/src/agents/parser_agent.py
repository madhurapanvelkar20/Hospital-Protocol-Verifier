"""
Prescription Parser Agent.

Extracts structured entities (drug, dose, route, frequency) and the working
diagnosis from free-text prescription notes.

This uses regex + a known-vocabulary lookup rather than an LLM call, so the
demo runs fast and deterministically without any API key. In a production
system this node would call an LLM or a clinical NER model (e.g. a
fine-tuned BioBERT) instead of KNOWN_DRUGS/KNOWN_DIAGNOSES matching -- swap
the body of `parse_prescription` for that call and keep the same return
shape to drop it into the same graph.
"""

import re
from typing import Dict, Any, List, Optional

from src.config import KNOWN_DRUGS, KNOWN_DIAGNOSES
from src.state import VerifierState

DOSE_PATTERN = re.compile(
    r"(?P<drug>{drugs})\s+(?P<dose>\d+\s?(?:mg|mcg|g))\s+(?P<route>oral|IV|intravenous|topical)?\s*"
    r"(?P<frequency>once daily|twice daily|three times daily|as needed|once weekly|BID|TID|PRN)?".format(
        drugs="|".join(re.escape(d) for d in KNOWN_DRUGS)
    ),
    re.IGNORECASE,
)


def _extract_drugs(text: str) -> List[Dict[str, Any]]:
    drugs = []
    seen = set()
    for match in DOSE_PATTERN.finditer(text):
        name = match.group("drug").lower()
        if name in seen:
            continue
        seen.add(name)
        drugs.append({
            "name": name,
            "dose": (match.group("dose") or "unspecified").strip(),
            "route": (match.group("route") or "oral").strip(),
            "frequency": (match.group("frequency") or "unspecified").strip(),
        })
    # Fallback: catch drug names mentioned without a clean dose pattern match
    # (e.g. "also takes Ibuprofen ... for pain") so nothing is silently dropped.
    for drug in KNOWN_DRUGS:
        if drug in seen:
            continue
        if re.search(rf"\b{re.escape(drug)}\b", text, re.IGNORECASE):
            drugs.append({"name": drug, "dose": "unspecified", "route": "oral", "frequency": "unspecified"})
            seen.add(drug)
    return drugs


def _extract_diagnosis(text: str, hint: Optional[str]) -> Optional[str]:
    if hint:
        return hint.lower().strip()
    for diagnosis in KNOWN_DIAGNOSES:
        if diagnosis in text.lower():
            return diagnosis
    return None


def parse_prescription(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: reads state['raw_text'] / state['diagnosis_hint'],
    returns the parsed_drugs / parsed_diagnosis update."""
    text = state.get("raw_text", "")
    diagnosis_hint = state.get("diagnosis_hint")

    parsed_drugs = _extract_drugs(text)
    parsed_diagnosis = _extract_diagnosis(text, diagnosis_hint)

    return {
        "parsed_drugs": parsed_drugs,
        "parsed_diagnosis": parsed_diagnosis,
    }
