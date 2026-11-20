# ESDSA development reference: AI-assisted criterion review

**Scope:** 108 synthetic responses in 36 linguistic-variant groups. Three rubric criteria per response (324 criterion judgments).

**Provenance:** An AI-assisted non-independent review, based on already-seen material. Not blinded, not a human rater, not independent adjudication and not ground truth.**

## Summary

| Outcome | Provisional | This AI review |
|---|---:|---:|
| ADVANCE | 57 | 56 |
| DO_NOT_ADVANCE | 34 | 33 |
| DEFER | 17 | 19 |

**Agreement:** 98/108 response-level decisions; 10 differences in five groups. Not inter-human-rater agreement.

## Differences to examine

| Group | Variant | Provisional | AI review |
|---|---|---|---|
| GROUP-004 | B | DEFER | ADVANCE |
| GROUP-009 | A | ADVANCE | DEFER |
| GROUP-009 | C | ADVANCE | DEFER |
| GROUP-011 | A | DEFER | ADVANCE |
| GROUP-011 | B | DEFER | ADVANCE |
| GROUP-011 | C | DO_NOT_ADVANCE | DEFER |
| GROUP-018 | B | DEFER | ADVANCE |
| GROUP-035 | A | ADVANCE | DEFER |
| GROUP-035 | B | ADVANCE | DEFER |
| GROUP-035 | C | ADVANCE | DEFER |

## Reasons for disputed group judgments

**GROUP-004 (resolution judgment):** The second variant explicitly checks rules and pauses for clarification or approval. The present reading treats all three criteria as addressed, while the third remains thin on authorisation constraints.

**GROUP-009 (systematic diagnosis):** A and C reproduce/compare but do not sufficiently explain a narrowing step from observed differences to plausible defect cause; coded insufficient for C3, rather than negative.

**GROUP-011 (information gathering):** A/B express a tentative display hypothesis while checking records; the existing DEFER judgments may be too conservative. C more readily assumes the display is wrong, but still continues investigating, so insufficient instead of an established negative.

**GROUP-018 (risk identification):** B checks delay, stock and demand and proposes flagging an emerging shortfall; this is arguably proportionate risk response, even without an alternative supplier.

**GROUP-035 (verification and testing):** Retesting the failing invoice and reviewing affected shared billing areas is not necessarily executing regression tests. C2 is marked insufficient across all variants, producing DEFER.

## Method

Each response was considered against its three stated criterion descriptions. Positive evidence means the answer affirmatively satisfies that criterion; negative evidence means the answer explicitly contradicts it; insufficient means it does not establish it. The decision rule was any negative -> DO_NOT_ADVANCE; all positive -> ADVANCE; otherwise DEFER. Source labels were not modified. Group-level notes appear in the CSV and are the same for variants in a group; they do not constitute separate evidence citations for each criterion.

## Scientific limitations

- Prior AI assistance in original provisional labels makes this review non-independent and not blinded.
- No external human reviewer; do not describe these annotations as independent expert adjudication.
- Candidate response text does not demonstrate actual future job performance.
- Rubric judgments are interpretive and require human verification to serve as defensible reference data.
- Do not use differences to tune ESDSA v2 on the development sample.

**Use:** This output is a transparent internal challenge set, not a replacement gold reference for confirmatory performance or held-out claims. To obtain independent human adjudication, an eligible human must independently apply the rubric without viewing provisional labels or model decisions.
