# Synthetic Violation Benchmark

## What this is

`generate_benchmark.py` builds 48 synthetic prescription cases directly
from `data/interactions.json` and `data/monitoring_requirements.json`,
across 5 categories:

| Category | Count | Expected result |
|---|---|---|
| `clean` | 16 | No violations |
| `missing_test` | 12 | The specific withheld test(s) flagged |
| `drug_drug` | 10 | The specific interaction flagged |
| `drug_diagnosis` | 5 | The specific contraindication flagged |
| `multiple` | 5 | An interaction + missing test(s), together |

`run_evaluation.py` runs three systems against every case and reports
case accuracy, violation recall, and false-positive rate:

- **`no_agent`** — always predicts "no violations" (naive floor)
- **`retrieval_only`** — runs retrieval but skips the Cross-Check and
  Missing-Test agents (approximates a plain-RAG system with no
  structured knowledge graph)
- **`full_pipeline`** — the complete 5-agent system

Run both with:
```bash
python benchmark/generate_benchmark.py
python benchmark/run_evaluation.py
```

## Current result

```
System            Case Accuracy   Violation Recall  False Positive Rate
no_agent          0.333           0.0               0.0
retrieval_only    0.333           0.0               0.0
full_pipeline     1.0             1.0               0.0
```

## Important limitation — read before citing this in your paper

**The full pipeline scoring 100% here is expected, not impressive**, and
you should not present it as strong evidence of the system's real-world
accuracy. Here's why: every benchmark case's *expected answer* was
generated from the exact same `interactions.json` /
`monitoring_requirements.json` files that the Cross-Check and
Missing-Test agents look up. The benchmark is testing "does the code
correctly implement a dictionary lookup against its own dictionary" —
which it obviously does, deterministically, every time. This makes it a
useful **regression test** (if you break the lookup logic while
extending the code, this will catch it), but it is not an independent
measurement of how well the system generalizes to real clinical text or
guidelines it wasn't built from.

To make this a genuine, citable evaluation for your paper, you need at
least one of:

1. **Held-out cases**: write benchmark cases from a source *not* used to
   build `interactions.json`/`monitoring_requirements.json` — e.g. pull
   10-15 interaction pairs from a public reference (a drug interaction
   database, or a published guideline) that weren't used when the
   knowledge graph was authored, so the system has to actually retrieve
   and reason over guideline text it wasn't hand-fitted to.
2. **Real baselines**: `retrieval_only` and `no_agent` here are honest
   floors, but your synopsis specifically calls for **plain-LLM** and
   **plain-RAG-with-an-LLM** baselines — i.e., actually prompting an LLM
   with the prescription and (for plain-RAG) the retrieved chunk, and
   scoring its free-text answer. That requires the LLM parser/explainer
   path (see `backend/src/agents/llm_parser_agent.py`) to be wired in
   and run against the same 48 cases, so the comparison is apples to
   apples.
3. **Noisy/free-text cases**: right now every case is generated from a
   template (`"{Drug} {dose} oral {frequency}"`), which is exactly the
   pattern the regex parser expects. Add cases with more natural,
   varied phrasing (the way a real clinician might write a note) to see
   whether the parser holds up outside its comfort zone — this is
   likely where the biggest accuracy drop would show up.

The evaluation harness itself (the recall / false-positive / accuracy
computation) is reusable as-is — what needs to change is the *source* of
the cases, not the scoring code.
