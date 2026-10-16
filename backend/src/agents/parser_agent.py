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

DOSE_VALUE = r"\d+(?:\.\d+)?\s?(?:mg|mcg|g|units?|iu|ml)"
FREQUENCY_VALUE = (
    r"(?:once daily|twice daily|three times daily|once weekly|as needed|"
    r"at night|nightly|daily|BID|TID|PRN)"
)
DOSE_PATTERN = re.compile(
    rf"(?P<drug>{{drugs}})\s+(?P<dose>{DOSE_VALUE})\s+(?P<route>oral|IV|intravenous|topical)?\s*"
    rf"(?P<frequency>{FREQUENCY_VALUE})?".format(
        drugs="|".join(re.escape(d) for d in KNOWN_DRUGS)
    ),
    re.IGNORECASE,
)

UNKNOWN_NAME_WORD = (
    r"(?!and\b|or\b|for\b|with\b|the\b|a\b|an\b|is\b|was\b|has\b|whose\b|"
    r"medication\b|medicine\b|drug\b|treatment\b|prescription\b)"
    r"[A-Za-z][A-Za-z0-9'/-]*"
)
UNKNOWN_DRUG_PATTERN = re.compile(
    rf"\b(?:prescrib(?:e|ed|ing)|start(?:ed)?|begin|began|take|takes|taking|"
    rf"on|continue(?:d)?|add(?:ed)?|administer(?:ed)?|and)\s+"
    rf"(?P<drug>{UNKNOWN_NAME_WORD}(?:\s+{UNKNOWN_NAME_WORD}){{0,2}})"
    rf"(?:\s+(?P<dose>{DOSE_VALUE}))?"
    rf"(?=\s+(?:for\b|with\b|and\b|or\b|orally\b|oral\b|iv\b|topical\b|"
    rf"once\b|twice\b|three\b|as\b|daily\b|weekly\b)|[.,;]|$)",
    re.IGNORECASE,
)

LISTED_DRUG_PATTERN = re.compile(
    rf"^\s*(?:[-•*]|\d+[.)])\s*"
    r"(?:(?:prescribe|prescribed|prescribing|start|started|begin|began|"
    r"take|takes|taking|continue|continued|add|added|administer|administered)"
    r"\s+)?"
    rf"(?P<drug>{UNKNOWN_NAME_WORD}(?:\s+{UNKNOWN_NAME_WORD}){{0,2}})"
    rf"\s+(?P<dose>{DOSE_VALUE})(?P<details>.*)$",
    re.IGNORECASE,
)

UNRESOLVED_MEDICATION_PATTERN = re.compile(
    r"\b(?:unknown|unrecognized|unidentified|new|additional|another|other|"
    r"unreadable|illegible|unclear|unspecified)\s+"
    r"(?:medication|medicine|drug|agent)\b|"
    r"\b(?:medication|medicine|drug|agent)(?:\s+name)?\s+"
    r"(?:is\s+)?(?:unknown|unreadable|illegible|unclear|unspecified)\b",
    re.IGNORECASE,
)


def _drug_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def finalize_drug_parse(
    state: VerifierState,
    parsed_drugs: List[Dict[str, Any]],
    parser_warnings: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Annotates support status and prevents empty parses from looking clear."""
    raw_text = state.get("raw_text", "")
    known_drugs = {_drug_key(drug) for drug in KNOWN_DRUGS}
    unique_drugs: List[Dict[str, Any]] = []
    seen = set()

    for drug in parsed_drugs:
        name = _drug_key(str(drug.get("name", "")))
        if not name or name in seen:
            continue
        seen.add(name)
        classified = dict(drug)
        classified["name"] = name
        classified["recognition_status"] = (
            "recognized" if name in known_drugs else "unsupported"
        )
        unique_drugs.append(classified)

    warnings = list(parser_warnings or [])
    for drug in unique_drugs:
        if drug["recognition_status"] == "unsupported":
            warnings.append({
                "type": "unsupported_drug",
                "drug": drug["name"],
                "message": (
                    f"{drug['name']} was extracted from the prescription but is "
                    "not in this system's supported drug knowledge base. Its "
                    "interaction and monitoring risks were not assessed; do not "
                    "interpret the absence of findings as evidence of safety."
                ),
            })

    if UNRESOLVED_MEDICATION_PATTERN.search(raw_text):
        warnings.append({
            "type": "drug_parse_failure",
            "message": (
                "The prescription text indicates that a medication may be "
                "present but its name could not be reliably extracted. This is "
                "a parsing failure, not a finding that the medication is safe "
                "or absent. Review the prescription."
            ),
        })
    elif raw_text.strip() and not unique_drugs:
        warnings.append({
            "type": "drug_parse_failure",
            "message": (
                "No drug name could be reliably extracted from the prescription. "
                "This may be a parsing failure and does not mean that no drug "
                "was prescribed. Review the prescription text."
            ),
        })

    return {
        "parsed_drugs": unique_drugs,
        "parser_warnings": warnings,
    }


def _extract_drugs(text: str) -> List[Dict[str, Any]]:
    drugs = []
    seen = set()
    for match in DOSE_PATTERN.finditer(text):
        name = _drug_key(match.group("drug"))
        if name in seen:
            continue
        seen.add(name)
        drugs.append({
            "name": name,
            "dose": (match.group("dose") or "unspecified").strip(),
            "route": (match.group("route") or "oral").strip(),
            "frequency": (match.group("frequency") or "unspecified").strip(),
        })

    for line in text.splitlines():
        match = LISTED_DRUG_PATTERN.match(line)
        if not match:
            continue
        name = _drug_key(match.group("drug"))
        if name in seen:
            continue
        seen.add(name)
        details = match.group("details")
        route_match = re.search(r"\b(?:oral|IV|intravenous|topical)\b", details, re.IGNORECASE)
        frequency_match = re.search(FREQUENCY_VALUE, details, re.IGNORECASE)
        drugs.append({
            "name": name,
            "dose": match.group("dose").strip(),
            "route": route_match.group(0) if route_match else "oral",
            "frequency": frequency_match.group(0) if frequency_match else "unspecified",
        })

    # Fallback: catch drug names mentioned without a clean dose pattern match
    # (e.g. "also takes Ibuprofen ... for pain") so nothing is silently dropped.
    for drug in KNOWN_DRUGS:
        if drug in seen:
            continue
        if re.search(rf"\b{re.escape(drug)}\b", text, re.IGNORECASE):
            drugs.append({"name": drug, "dose": "unspecified", "route": "oral", "frequency": "unspecified"})
            seen.add(drug)

    known_keys = {_drug_key(drug) for drug in KNOWN_DRUGS}
    for match in UNKNOWN_DRUG_PATTERN.finditer(text):
        name = _drug_key(match.group("drug"))
        if name in seen or name in known_keys:
            continue
        seen.add(name)
        drugs.append({
            "name": name,
            "dose": (match.group("dose") or "unspecified").strip(),
            "route": "oral",
            "frequency": "unspecified",
        })
    return drugs


def _extract_diagnoses(text: str, hint: Optional[str]) -> List[str]:
    """Returns EVERY matching diagnosis, not just the first -- a real
    prescription commonly lists more than one (e.g. hypertension AND type
    2 diabetes on the same visit), and treating diagnosis as singular
    meant the Cross-Check Agent could only check contraindications
    against one of them, silently ignoring the rest.

    `hint` (from the diagnosis field / OCR extraction) may itself be
    comma-separated ("hypertension, type 2 diabetes") to support multiple
    diagnoses from the same input.
    """
    diagnoses = []

    if hint:
        for part in hint.split(","):
            part = part.strip().lower()
            if part:
                diagnoses.append(part)

    for diagnosis in KNOWN_DIAGNOSES:
        # Skip if this keyword is already covered by an existing entry in
        # either direction -- e.g. a hint of "type 2 diabetes mellitus"
        # already covers the keyword "type 2 diabetes"; don't list both.
        already_covered = any(diagnosis in d or d in diagnosis for d in diagnoses)
        if diagnosis in text.lower() and not already_covered:
            diagnoses.append(diagnosis)

    return diagnoses


def parse_prescription(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: reads state['raw_text'] / state['diagnosis_hint'],
    returns the parsed_drugs / parsed_diagnoses update."""
    text = state.get("raw_text", "")
    diagnosis_hint = state.get("diagnosis_hint")

    parsed_drugs = _extract_drugs(text)
    parsed_diagnoses = _extract_diagnoses(text, diagnosis_hint)

    result = finalize_drug_parse(state, parsed_drugs)
    return {
        **result,
        "parsed_diagnoses": parsed_diagnoses,
    }
