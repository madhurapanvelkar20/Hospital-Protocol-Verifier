# Clinical coverage audit

## Scope and limitations

This audit compares the 18 medicine names explicitly listed in the supplied
handover text with the active parser vocabulary, local protocol documents,
`monitoring_requirements.json`, `interactions.json`, and regression tests.
The handover refers to a separate `Protocol_Verifier_Clinical_Review_List(1).docx`,
but that DOCX was not present in the attachments or workspace. Consequently,
the exact expected per-medicine monitoring rules, aliases, interaction and
contraindication inventory, severity labels, recommendations, and source labels
cannot be verified here. The status column does not treat absent active rules
as clinically required omissions.

All clinical content in this project is demonstration data, not an official
prescribing standard or clinically validated decision support.

## Medicine inventory

`Parser` confirms whether the medicine is in `KNOWN_DRUGS`. `Monitoring`,
`interactions`, and `contraindications` describe only active structured data.
The parser inventory is covered by a data-driven numbered-prescription test;
configured interaction, contraindication, and monitoring rules are also
exercised by data-driven regressions. Rows without configured rules have parser
coverage only.

| Reference medicine | Parser | Active guideline document | Monitoring rule | Drug-drug interactions | Drug-diagnosis contraindications | Tests | Status |
|---|---|---|---|---|---|---|---|
| Lisinopril | Yes | Hypertension management | Yes | Furosemide; Losartan | Pregnancy | Parser; monitoring; interaction; contraindication | Matched by name; DOCX rule details unverified |
| Metformin | Yes | Type 2 diabetes management | Yes | None | Renal impairment | Parser; monitoring; contraindication | Matched by name; DOCX rule details unverified |
| Warfarin | Yes | Warfarin anticoagulation | Yes | Ibuprofen; Amoxicillin; Clopidogrel | None | Parser; monitoring; interaction | Matched by name; DOCX rule details unverified |
| Methotrexate | Yes | Rheumatoid arthritis methotrexate | Yes | Ibuprofen | None | Parser; monitoring; interaction | Matched by name; DOCX rule details unverified |
| Simvastatin | Yes | Statin therapy | Yes | None | None | Parser; monitoring | Matched by name; DOCX rule details unverified |
| Furosemide | Yes | Heart-failure diuretic management | Yes | Lisinopril; Digoxin | None | Parser; monitoring; interaction | Matched by name; DOCX rule details unverified |
| Ibuprofen | Yes | No standalone document | No | Warfarin; Methotrexate; Clopidogrel; Prednisone | Peptic ulcer disease | Parser; interaction; contraindication | Matched by name; DOCX rule details unverified |
| Amoxicillin | Yes | No standalone document | No | Warfarin | None | Parser; interaction | Matched by name; DOCX rule details unverified |
| Digoxin | Yes | Digoxin therapy | Yes | Furosemide | Renal impairment | Parser; monitoring; interaction; contraindication | Matched by name; DOCX rule details unverified |
| Levothyroxine | Yes | Levothyroxine hypothyroidism | Yes | None | None | Parser; monitoring | Matched by name; DOCX rule details unverified |
| Omeprazole | Yes | Omeprazole GERD | No | Clopidogrel | None | Parser; interaction | Matched by name; DOCX rule details unverified |
| Clopidogrel | Yes | Clopidogrel antiplatelet | Yes | Omeprazole; Warfarin; Ibuprofen | None | Parser; monitoring; interaction | Matched by name; DOCX rule details unverified |
| Insulin | Yes | Insulin therapy | Yes | None | None | Parser; monitoring | Matched by name; DOCX rule details unverified |
| Losartan | Yes | Losartan hypertension | Yes | Lisinopril | Pregnancy | Parser; monitoring; interaction; contraindication | Matched by name; DOCX rule details unverified |
| Prednisone | Yes | Prednisone corticosteroid | Yes | Ibuprofen | None | Parser; monitoring; interaction | Matched by name; DOCX rule details unverified |
| Amlodipine | Yes | Amlodipine hypertension | No | None | None | Parser only | Matched by name; DOCX rule details unverified |
| Telmisartan | Yes | No matching document | No | None | None | Parser only | Requires review; no active structured rules |
| Atorvastatin | Yes | Statin therapy (general statin text) | No | None | None | Parser; retrieval and unassessed-status regression | Requires review; no active structured rules |

No duplicates were found in `KNOWN_DRUGS`. Telmisartan and Atorvastatin were
added to that inventory because the handover explicitly lists them; no
monitoring, interaction, or contraindication rules were inferred for either.
Atorvastatin's local retrieval uses the statin guideline text that refers to
“Simvastatin and other statins”; that retrieval association is not an added
clinical rule.

## Active rule data

- **Monitoring:** 12 medicine keys: Warfarin, Metformin, Methotrexate,
  Simvastatin, Furosemide, Lisinopril, Digoxin, Levothyroxine, Clopidogrel,
  Insulin, Losartan, and Prednisone. Multi-component requirements are evaluated
  independently; the explicitly configured eGFR/serum-creatinine alternative
  and Serum Potassium-to-Potassium matching are scoped in the detector.
- **Drug-drug:** 10 configured pairs: Warfarin–Ibuprofen, Warfarin–Amoxicillin,
  Methotrexate–Ibuprofen, Lisinopril–Furosemide, Digoxin–Furosemide,
  Clopidogrel–Omeprazole, Clopidogrel–Warfarin, Clopidogrel–Ibuprofen,
  Prednisone–Ibuprofen, and Lisinopril–Losartan. The regression suite checks
  every pair in both input orders.
- **Drug-diagnosis:** 5 configured pairs: Metformin–Renal impairment,
  Lisinopril–Pregnancy, Losartan–Pregnancy, Ibuprofen–Peptic ulcer disease,
  and Digoxin–Renal impairment.
- **Explicit coverage gap:** no Lisinopril–Potassium Chloride interaction
  exists in the active interaction data. The medicine is preserved and shown
  as not assessed; the pair has not been added or represented as checked.

