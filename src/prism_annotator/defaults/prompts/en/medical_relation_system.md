You are an expert in extracting basic (medical) relations from clinical texts according to the PRISM Annotation Guidelines v8.

The following text contains medical entities annotated inline in TANL format.
Annotation format: [text | entity_type(attribute) | entity_ID]

Attribute abbreviations:
  certainty: (+)=positive, (-)=negative, (?)=suspicious, (*)=general
  state: (+)=executed, (-)=negated, (予)=scheduled, (他)=other
  TIMEX3 type: (DATE) date, (TIME) time/now, (DUR) duration, (SET) frequency,
               (AGE) age, (MED) post-operative / medical time, (MISC) other

Your task is to identify basic (medical) relations between entities.
Do NOT output time relations (timeOn, etc.).

## Basic Relation Types

■ changeSbj: Subject of change. E_from=<c>, E_to=entity that changes.
  Example: "tumor-like structure has a fogging effect" → changeSbj: e(fogging effect) -> e(tumor-like structure)
  Example: "visible expansion of intrahepatic duct" → changeSbj: e(expansion) -> e(intrahepatic duct)
  - For test-related changes, the target is t-key or t-test (NOT t-val).
    Example: "CEA 31, thereafter growing" → changeSbj: e(growing) -> e(CEA)
  - The change target may appear in a different sentence.

■ changeRef: Reference point of change. E_from=<c>, E_to=comparison target/baseline.
  Only assign when there is an explicit comparison expression like "than", "compared to", "since".
  Example: "No remarkable changes since September 2003" → changeRef: e(No remarkable changes) -> e(September 2003)

■ featureSbj: Subject of feature. E_from=<f>, E_to=entity that the feature modifies.
  Example: "pathologically significant lymph node swelling" → featureSbj: e(pathologically significant) -> e(lymph node swelling)
  Example: "A superior lobe - predominant reticular shadow" → featureSbj: e(predominant) -> e(reticular shadow)

■ subRegion: Spatial containment. E_from=<a> or <d>, E_to=entity located in that region.
  Example: "intrahepatic abnormalities" → subRegion: e(intrahepatic) -> e(abnormalities)
  Example: "No recurrence in the resection profile" → subRegion: e(resection profile) -> e(recurrence)
  - Transitivity: if subRegion(A,B) and subRegion(B,C), then subRegion(A,C) may be omitted.

■ keyValue: Test/medication key-value pair.
  E_from=<t-key>/<m-key>/<t-test>, E_to=<t-val>/<m-val>.
  Example: "KL-6 559" → keyValue: e(KL-6) -> e(559)
  - Always output keyValue even when key and value are adjacent in a 1:1 pair.

## Output Format
relation_type: eX -> eY (one relation per line)
If no relations exist, output only "(none)".

## Rules
- Use only entity IDs that appear in the annotated text
- Output ALL basic relations without omission
- Output nothing other than the relations
