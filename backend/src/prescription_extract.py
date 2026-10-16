"""
Extracts structured diagnosis and ordered-test lists from raw prescription
text (typically OCR output), so a photo upload can auto-fill those fields
instead of leaving the user to retype what a well-formatted prescription
already states clearly.

Two extraction strategies, tried in order:
  1. Section-header based: many real prescriptions (like hospital-issued
     printouts) have an explicit "DIAGNOSIS" and "TESTS ORDERED" section --
     if found, every line under that header (until the next header) is
     taken as one entry. This is the more reliable path when available,
     since it reads what the prescription actually states rather than
     guessing from a fixed vocabulary.
  2. Keyword fallback (diagnoses only): if no explicit section is found,
     falls back to matching against KNOWN_DIAGNOSES -- the same approach
     parser_agent.py uses for typed input. There is no equivalent
     fallback for tests, since there's no fixed vocabulary of lab test
     names to match against; if there's no "tests ordered" section, the
     user is expected to enter those manually.

This never fabricates a diagnosis or test that isn't in the text --
matching the same discipline as src/live_data.py: skip and let the user
fill it in by hand rather than guess.
"""

import re
from typing import List, Dict

from src.config import KNOWN_DIAGNOSES

# Recognized section headers, matched case-insensitively, allowing for
# common variants across different prescription formats.
DIAGNOSIS_HEADERS = [r"diagnos[ie]s"]
TEST_HEADERS = [
    r"tests?\s*ordered",
    r"investigations?(?:\s+(?:advised|ordered))?",
    r"labs?\s*ordered",
    r"lab\s*tests?",
]

# A line that looks like the START of a different section -- used to know
# where the current section's list of items ends.
ANY_SECTION_HEADER = re.compile(
    r"^\s*(diagnos[ie]s|tests?\s*ordered|investigations?(?:\s+(?:advised|ordered))?|"
    r"labs?\s*ordered|lab\s*tests?|"
    r"prescription|rx|additional advice|advice|medications?|signature)\s*:?\s*$",
    re.IGNORECASE,
)

# Strips leading numbering/bullets like "1.", "2)", "-", "•" from a line.
LEADING_MARKER = re.compile(r"^\s*(?:[\d]+[.)]|[-•*])\s*")


def _extract_section(lines: List[str], header_patterns: List[str]) -> List[str]:
    header_re = re.compile(rf"^\s*(?:{'|'.join(header_patterns)})\s*:?\s*$", re.IGNORECASE)

    items = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if header_re.match(stripped):
            in_section = True
            continue

        if in_section:
            if ANY_SECTION_HEADER.match(stripped):
                break  # a different section started
            item = LEADING_MARKER.sub("", stripped).strip()
            if item:
                items.append(item)

    return items


def extract_structured_fields(text: str) -> Dict[str, List[str]]:
    """Returns {"diagnoses": [...], "ordered_tests": [...]} extracted from
    raw prescription text. Either list may be empty if nothing was found
    -- that's a valid, honest outcome, not an error."""
    lines = text.splitlines()

    diagnoses = _extract_section(lines, DIAGNOSIS_HEADERS)
    ordered_tests = _extract_section(lines, TEST_HEADERS)

    if not diagnoses:
        # Fallback: keyword match against the known vocabulary, same
        # approach as the regex prescription parser.
        text_lower = text.lower()
        diagnoses = [d for d in KNOWN_DIAGNOSES if d in text_lower]

    return {"diagnoses": diagnoses, "ordered_tests": ordered_tests}
