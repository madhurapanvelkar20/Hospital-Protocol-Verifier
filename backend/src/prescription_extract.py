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

A section ends at the next recognised header, at the first medication line,
or at the first header/footer-style line (doctor name, registration number,
hospital/clinic name, phone, date, signature ...), so letterhead and footer
text is never mistaken for a test or diagnosis.

This never fabricates a diagnosis or test that isn't in the text --
matching the same discipline as src/live_data.py: skip and let the user
fill it in by hand rather than guess.
"""

import re
from typing import List, Dict

from src.agents.parser_agent import looks_like_medication_line
from src.config import KNOWN_DIAGNOSES

# Recognized section headers, matched case-insensitively, allowing for
# common variants across different prescription formats.
DIAGNOSIS_HEADERS = [r"(?:provisional\s+|working\s+|clinical\s+)?diagnos[ie]s"]
TEST_HEADERS = [
    r"tests?\s*ordered",
    r"investigations?(?:\s+(?:advised|ordered|required))?",
    r"ordered\s+(?:tests?|investigations?)",
    r"tests?\s+advised",
    r"labs?\s*ordered",
    r"lab\s*tests?",
]

# A line that looks like the START of a different section -- used to know
# where the current section's list of items ends. Accepts "Header" alone or
# "Header: inline content".
ANY_SECTION_HEADER = re.compile(
    r"^\s*(?:(?:provisional\s+|working\s+|clinical\s+)?diagnos[ie]s|tests?\s*ordered|"
    r"investigations?(?:\s+(?:advised|ordered|required))?|ordered\s+(?:tests?|investigations?)|"
    r"tests?\s+advised|labs?\s*ordered|lab\s*tests?|"
    r"prescription|rx|(?:additional\s+)?advice|medications?|medicines?|drugs?|treatment|"
    r"follow[\s-]*up|signature|notes?|remarks?|plan|allergies|history|complaints?)"
    r"\s*(?::|$)",
    re.IGNORECASE,
)

# Header/footer-style lines (doctor, registration, patient demographics,
# hospital letterhead, phone, signature...) that can never be a test or
# diagnosis. A section stops at the first such line.
_BOUNDARY_START = re.compile(
    r"^\s*(?:dr\b|doctor\b|reg(?:istration)?\b|signature\b|sign\b|stamp\b|date\b|"
    r"patient\b|name\b|age\b|sex\b|gender\b|weight\b|address\b|phone\b|ph\b|tel\b|"
    r"mob(?:ile)?\b|valid\b|licen[cs]e\b|nmc\b|mci\b)",
    re.IGNORECASE,
)
_BOUNDARY_ANYWHERE = re.compile(
    r"\breg\.?\s*(?:no|number)\b"
    r"|\b(?:hospital|clinic|nursing\s+home|medical\s+cent(?:re|er))\b"
    r"|\b(?:ph|tel|phone|mob(?:ile)?)\b\.?\s*[:\-]?\s*[\d(+]",
    re.IGNORECASE,
)

# Strips leading numbering/bullets like "1.", "2)", "-", "*" from a line.
LEADING_MARKER = re.compile(
    r"^\s*(?:[\d]+[.)]|[-\u2022*\u00b7\u25e6\u25aa\u25cf\u25cb\u2023\u2013\u2014\u00b0\u00a2\u00ab\u00bb])\s*"
)
# OCR frequently reads a printed bullet dot as a lone lowercase "e" or "o"
# ("e Serum Potassium"). Only a lone e/o followed by a capitalised word is
# treated as a misread bullet, so real names such as "C Reactive Protein" stay.
_MISREAD_BULLET = re.compile(r"^[eo]\s+(?=[A-Z])")

_COMMA_OUTSIDE_PARENS = re.compile(r",(?![^()]*\))")
_MAX_ITEM_LENGTH = 80


def _is_boundary(line: str) -> bool:
    return bool(
        ANY_SECTION_HEADER.match(line)
        or _BOUNDARY_START.match(line)
        or _BOUNDARY_ANYWHERE.search(line)
        or looks_like_medication_line(line)
    )


def _clean_item(raw: str) -> str:
    item = LEADING_MARKER.sub("", raw).strip()
    item = _MISREAD_BULLET.sub("", item)
    return item.strip(" \t-:;")


def _extract_section(lines: List[str], header_patterns: List[str], split_commas: bool = False) -> List[str]:
    header_re = re.compile(
        rf"^\s*(?:{'|'.join(header_patterns)})\s*(?::\s*(?P<inline>.*?))?\s*$", re.IGNORECASE
    )

    items: List[str] = []
    in_section = False

    def add(candidate: str) -> None:
        parts = _COMMA_OUTSIDE_PARENS.split(candidate) if split_commas else [candidate]
        for part in parts:
            item = _clean_item(part)
            if item and re.search(r"[A-Za-z]", item) and len(item) <= _MAX_ITEM_LENGTH:
                if item.lower() not in {i.lower() for i in items}:
                    items.append(item)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        header = header_re.match(stripped)
        if header:
            if in_section:
                break  # a second copy of the same header ends the first section
            in_section = True
            inline = header.group("inline")
            if inline:
                add(inline)
            continue

        if in_section:
            if _is_boundary(stripped):
                break  # next section, or letterhead/footer text
            add(stripped)

    return items


def extract_structured_fields(text: str) -> Dict[str, List[str]]:
    """Returns {"diagnoses": [...], "ordered_tests": [...]} extracted from
    raw prescription text. Either list may be empty if nothing was found
    -- that's a valid, honest outcome, not an error."""
    lines = text.splitlines()

    diagnoses = _extract_section(lines, DIAGNOSIS_HEADERS)
    ordered_tests = _extract_section(lines, TEST_HEADERS, split_commas=True)

    if not diagnoses:
        # Fallback: keyword match against the known vocabulary, same
        # approach as the regex prescription parser.
        text_lower = text.lower()
        diagnoses = [d for d in KNOWN_DIAGNOSES if d in text_lower]

    return {"diagnoses": diagnoses, "ordered_tests": ordered_tests}
