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
    r"(?P<drug>{drugs})\s+(?P<dose>\d+(?:\.\d+)?\s?(?:mg|mcg|µg|ug|g|ml|iu|mEq|units?))\s*"
    r"(?P<route>oral|IV|intravenous|topical|sublingual|subcutaneous)?\s*"
    r"(?P<frequency>once daily|twice daily|three times daily|as needed|once weekly|BID|TID|PRN)?".format(
        drugs="|".join(re.escape(d) for d in KNOWN_DRUGS)
    ),
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Line-based medication parsing (numbered lists, multiline instructions)
# ---------------------------------------------------------------------------
# The single-sentence regex above only recognises the configured vocabulary and
# only reads a frequency that sits directly after the dose. Real prescriptions
# (and OCR output of them) are usually laid out one medicine per line, e.g.
#     1. Apixaban 5 mg - one tablet twice daily
#     4. Pantoprazole 40 mg - one tablet once daily
#        before food
# so this layer reads each medication line separately, keeps drugs that are
# not in KNOWN_DRUGS (flagged recognized=False, never dropped), and pulls the
# frequency from the rest of the line plus any wrapped continuation line.
# Anything not stated in the text is reported as "unspecified", never guessed.

_UNIT = r"(?:mg|mcg|\u00b5g|ug|g|ml|iu|meq|units?)"

_MED_ENTRY = re.compile(
    r"^\s*(?P<marker>(?:\d{1,2}\s*[.)]|[-\u2022*])\s*)?"
    r"(?:(?:tab|tablet|cap|capsule|inj|syp|syrup)\b\.?\s*)?"
    r"(?P<name>[A-Za-z][A-Za-z0-9/-]*(?:\s+[A-Za-z][A-Za-z0-9/-]*)*?)\s*[(:,\-\u2013\u2014]?\s*"
    r"(?P<dose>\d+(?:\.\d+)?\s?" + _UNIT + r")\b\)?"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)

# Words that can precede a number + unit on a non-medication line.
_NOT_DRUG_NAMES = {
    "tablet", "tab", "capsule", "cap", "dose", "weight", "wt", "age", "bp",
    "date", "reg", "ph", "phone", "no", "dr", "rx", "take", "give", "increase",
    "titrate", "total", "max", "maximum", "every", "each", "per",
}
_NOT_MEDICATION_PREFIXES = {
    "patient", "prescribe", "prescribed", "start", "starts", "continue",
    "currently", "additionally", "also", "on", "takes", "taking", "name",
    "sex", "gender", "address", "signature", "sign", "stamp", "doctor",
    "diagnosis", "investigation", "investigations", "tests",
}

_MED_HEADER = re.compile(
    r"^\s*(?:rx|prescription|medications?|medicines?|drugs?|treatment)\s*:?\s*$",
    re.IGNORECASE,
)
_OTHER_HEADER = re.compile(
    r"^\s*(?:(?:provisional\s+|working\s+|clinical\s+)?diagnos[ie]s|tests?\s*ordered|"
    r"investigations?(?:\s+(?:advised|ordered|required))?|ordered\s+(?:tests?|investigations?)|"
    r"labs?\s*ordered|lab\s*tests?|(?:additional\s+)?advice|follow[\s-]*up|signature|notes?|remarks?)"
    r"\s*:?\s*$",
    re.IGNORECASE,
)
_LIST_MARKER = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|[-\u2022*])")
_FOOTER_START = re.compile(r"^\s*(?:dr\b|reg\b|registration\b|signature\b|date\b|patient\b)", re.IGNORECASE)

# Frequency: first matching rule wins (ordered most-specific first).
_COUNT_RULES = [
    (re.compile(r"\b(?:four\s+times|4\s+times)\s*(?:a\s+)?(?:daily|day)?\b|\bqid\b|\bqds\b", re.I), "four times daily"),
    (re.compile(r"\b(?:three\s+times|thrice|3\s+times)\s*(?:a\s+)?(?:daily|day)?\b|\btds\b|\btid\b", re.I), "three times daily"),
    (re.compile(r"\b(?:twice|two\s+times|2\s+times)\s*(?:a\s+)?(?:daily|day)?\b|\bbd\b|\bbid\b", re.I), "twice daily"),
    (re.compile(r"\bonce\s+(?:a\s+)?(?:weekly|week)\b|\bweekly\b", re.I), "once weekly"),
    (re.compile(r"\bonce\s+(?:a\s+)?(?:daily|day)\b|\bod\b|\bqd\b|\bdaily\b", re.I), "once daily"),
    (re.compile(r"\bas\s+needed\b|\bprn\b|\bsos\b|\bwhen\s+required\b", re.I), "as needed"),
]
_EVERY_N_HOURS = re.compile(r"\bevery\s+(\d+)\s*(?:hours?|hrs?)\b", re.I)
_NIGHT = re.compile(r"\b(?:at\s+night|at\s+bedtime|bedtime|nocte|nightly|every\s+night|hs)\b", re.I)
_TIMING_RULES = [
    re.compile(r"\bbefore\s+(?:food|meals?|breakfast|lunch|dinner)\b", re.I),
    re.compile(r"\bafter\s+(?:food|meals?|breakfast|lunch|dinner)\b", re.I),
    re.compile(r"\bwith\s+(?:food|meals?)\b", re.I),
    re.compile(r"\bempty\s+stomach\b", re.I),
    re.compile(r"\b(?:in\s+the\s+)?morning\b", re.I),
]
_ROUTE = re.compile(r"\b(oral|iv|intravenous|topical|sublingual|subcutaneous)\b", re.I)


def _parse_frequency(text: str) -> str:
    """Reads frequency/timing wording that is actually present in `text`."""
    count = None
    m = _EVERY_N_HOURS.search(text)
    if m:
        count = f"every {m.group(1)} hours"
    else:
        for pattern, canonical in _COUNT_RULES:
            if pattern.search(text):
                count = canonical
                break

    timings = []
    if _NIGHT.search(text):
        timings.append("at night")
    for pattern in _TIMING_RULES:
        m = pattern.search(text)
        if m:
            timings.append(re.sub(r"\s+", " ", m.group(0).lower()))

    if count and timings:
        return f"{count}, {', '.join(timings)}"
    if count:
        return count
    if timings:
        if "at night" in timings:
            return ", ".join(timings)
        return f"unspecified ({', '.join(timings)})"
    return "unspecified"


def _parse_route(text: str) -> str:
    m = _ROUTE.search(text)
    if not m:
        return "unspecified"
    value = m.group(1).lower()
    return "IV" if value in ("iv", "intravenous") else value


# OCR often reads the large "Rx" symbol (or a margin mark) as 2-4 stray
# characters ("OM", "Rx", "R/", "Wx") that end up on the same line as the first
# medicine, e.g. "OM 1) Apixaban 5 mg". Drop such a prefix when it is directly
# followed by a list marker, or when it is a literal Rx / R/ token.
_STRAY_BEFORE_MARKER = re.compile(r"^\s*[^\s\d]{1,4}\s+(?=\d{1,2}\s*[.)]\s*[A-Za-z])")
_RX_TOKEN = re.compile(r"^\s*(?:rx|r/|\u211e)[\s:.\-]+(?=[A-Za-z\d])", re.IGNORECASE)


def _strip_stray_prefix(line: str) -> str:
    stripped = _RX_TOKEN.sub("", line, count=1)
    if stripped == line:
        stripped = _STRAY_BEFORE_MARKER.sub("", line, count=1)
    return stripped.strip()


def _looks_like_instruction(line: str) -> bool:
    """True for a wrapped continuation line such as 'before food'."""
    if _MED_ENTRY.match(line) or _LIST_MARKER.match(line):
        return False
    if _MED_HEADER.match(line) or _OTHER_HEADER.match(line) or _FOOTER_START.match(line):
        return False
    return bool(
        _EVERY_N_HOURS.search(line)
        or _NIGHT.search(line)
        or any(p.search(line) for p, _ in _COUNT_RULES)
        or any(p.search(line) for p in _TIMING_RULES)
    )


def looks_like_medication_line(line: str) -> bool:
    """Public helper (also used by src/prescription_extract.py to stop a
    tests/diagnosis section at the first medication line)."""
    m = _MED_ENTRY.match(_strip_stray_prefix(line))
    return bool(
        m
        and m.group("name").strip("-").lower().split()[0] not in _NOT_DRUG_NAMES | _NOT_MEDICATION_PREFIXES
    )


def _split_medication_line(line: str) -> List[str]:
    """Split only where the next comma/semicolon-delimited segment is another
    dose-bearing medication, preserving punctuation in dosage instructions."""
    starts = [0]
    for separator in re.finditer(r"[,;]", line):
        if _MED_ENTRY.match(line[separator.end():].strip()):
            starts.append(separator.end())
    if len(starts) == 1:
        return [line]
    segments = []
    for index, start in enumerate(starts):
        end = starts[index + 1] - 1 if index + 1 < len(starts) else len(line)
        segments.append(line[start:end].strip(" ,;"))
    return segments


def _extract_medication_lines(text: str):
    """Returns [(position, drug_dict)] for every medication line found."""
    results = []
    in_other_section = False
    current = None  # [pos, drug_dict, continuation_text]
    pos = 0

    def finish():
        nonlocal current
        if current is not None:
            _pos, drug, extra = current
            full = f"{drug.pop('_rest')} {extra}".strip()
            drug["frequency"] = _parse_frequency(full)
            drug["route"] = _parse_route(full)
            results.append((_pos, drug))
        current = None

    for raw in text.splitlines(keepends=True):
        line = raw.strip()
        line_pos = pos
        pos += len(raw)
        if not line:
            continue  # OCR often inserts blank lines between wrapped lines
        line = _strip_stray_prefix(line)
        if not line:
            continue

        if _MED_HEADER.match(line):
            finish()
            in_other_section = False
            continue
        if _OTHER_HEADER.match(line):
            finish()
            in_other_section = True
            continue
        if _FOOTER_START.match(line):
            finish()
            continue
        if in_other_section:
            candidate = _MED_ENTRY.match(line)
            if not candidate:
                continue
            candidate_name = candidate.group("name").strip("-").lower()
            candidate_rest = candidate.group("rest")
            has_instructions = bool(
                _ROUTE.search(candidate_rest)
                or _parse_frequency(candidate_rest) != "unspecified"
            )
            if (
                candidate_name not in KNOWN_DRUGS
                and not candidate.group("marker")
                and not has_instructions
            ):
                continue
            in_other_section = False

        segments = _split_medication_line(line)
        found_medication = False
        for segment in segments:
            m = _MED_ENTRY.match(segment)
            if not m:
                continue

            name = m.group("name").strip("-").lower()
            first_word = name.split()[0]
            known = name in KNOWN_DRUGS
            rest = m.group("rest")
            if (
                first_word not in _NOT_DRUG_NAMES | _NOT_MEDICATION_PREFIXES
            ):
                finish()
                drug = {
                    "name": name,
                    "dose": m.group("dose").strip(),
                    "route": "unspecified",
                    "frequency": "unspecified",
                    "recognized": known,
                    "_rest": rest,
                }
                current = [line_pos + m.start("name"), drug, ""]
                found_medication = True

        if found_medication:
            continue

        if current is not None and _looks_like_instruction(line):
            current[2] = f"{current[2]} {line}".strip()
            continue

        finish()

    finish()
    return results


def _extract_drugs(text: str) -> List[Dict[str, Any]]:
    entries: Dict[str, Any] = {}  # name -> (position, drug_dict)

    # 1) Line-based medication entries (all drugs, known or not).
    for position, drug in _extract_medication_lines(text):
        entries.setdefault(drug["name"], (position, drug))

    # 2) Sentence-style text, e.g. "Prescribe Metformin 500mg oral twice daily".
    for match in DOSE_PATTERN.finditer(text):
        name = match.group("drug").lower()
        if name in entries:
            continue
        entries[name] = (match.start(), {
            "name": name,
            "dose": (match.group("dose") or "unspecified").strip(),
            "route": (match.group("route") or "unspecified").strip(),
            "frequency": (match.group("frequency") or "unspecified").strip(),
            "recognized": True,
        })

    # 3) Fallback: catch drug names mentioned without a clean dose pattern
    # (e.g. "also takes Ibuprofen ... for pain") so nothing is silently dropped.
    for drug in KNOWN_DRUGS:
        if drug in entries:
            continue
        found = re.search(rf"\b{re.escape(drug)}\b", text, re.IGNORECASE)
        if found:
            entries[drug] = (found.start(), {
                "name": drug, "dose": "unspecified", "route": "unspecified",
                "frequency": "unspecified", "recognized": True,
            })

    return [drug for _, drug in sorted(entries.values(), key=lambda item: item[0])]


def _extract_diagnoses(text: str, hint: Optional[str]) -> List[str]:
    if hint:
        diagnoses = []
        for candidate in re.split(r"[;,]", hint):
            candidate = candidate.strip().lower()
            if not candidate:
                continue
            matched = next(
                (
                    known for known in sorted(KNOWN_DIAGNOSES, key=len, reverse=True)
                    if re.search(rf"\b{re.escape(known)}\b", candidate)
                ),
                candidate,
            )
            if matched not in diagnoses:
                diagnoses.append(matched)
        return diagnoses

    matches = []
    for diagnosis in KNOWN_DIAGNOSES:
        for match in re.finditer(rf"\b{re.escape(diagnosis)}\b", text, re.IGNORECASE):
            matches.append((match.start(), diagnosis))
    diagnoses = []
    for _, diagnosis in sorted(matches):
        if diagnosis not in diagnoses:
            diagnoses.append(diagnosis)
    return diagnoses


def parse_prescription(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: reads state['raw_text'] / state['diagnosis_hint'],
    returns the parsed_drugs / parsed_diagnosis update."""
    text = state.get("raw_text", "")
    diagnosis_hint = state.get("diagnosis_hint")

    parsed_drugs = _extract_drugs(text)
    parsed_diagnoses = _extract_diagnoses(text, diagnosis_hint)

    return {
        "parsed_drugs": parsed_drugs,
        "parsed_diagnoses": parsed_diagnoses,
        "parsed_diagnosis": ", ".join(parsed_diagnoses) or None,
    }
