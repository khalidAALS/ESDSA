# ESDSA — When AI Should Not Decide

**Evidence Sufficiency and Decision Stability Assessment for Automated Job Interviews**

Research code and experimental materials accompanying *When AI Should Not Decide: Evidence Sufficiency and Decision Stability in Automated Job Interviews*.

**Author:** Khalid Adnan Alsayed  
**Affiliations:** Ducaltus Ltd, London, UK; University of Leicester, Leicester, UK  
**Contact:** [Research@ducaltus.com](mailto:Research@ducaltus.com)  
**ORCID:** [0009-0000-6272-6761](https://orcid.org/0009-0000-6272-6761)

## Overview

ESDSA studies when an LLM-based interview evaluator should issue an actionable competency recommendation and when it should defer. The procedure combines:

- **Criterion-level evidence classification:** positive, negative or insufficient evidence against a three-criterion competency rubric.
- **Deterministic quotation traceability:** checking whether cited supporting excerpts occur in the response. Textual occurrence does not establish semantic correctness.
- **Semantic-equivalence-conditioned decision stability:** for groups annotated as substantively equivalent, retaining actionable recommendations only if all three linguistic variants receive the same actionable decision.

The experimental outcomes are `ADVANCE`, `DO_NOT_ADVANCE` and `DEFER`. They are **not actual employment decisions or validated predictions of candidate suitability**.

## Experimental design

- Three occupational domains: Software Engineering, Customer Support and Operations.
- Twelve competencies (four per domain), each with three assessment criteria.
- A scenario registry of 120 families: 72 DEVELOPMENT, 24 VALIDATION and 24 TEST.
- **60 evaluated families**: 12 DEVELOPMENT, 24 VALIDATION and 24 TEST, yielding **540 synthetic responses** (nine per family).
- Three intended evidence conditions per family and three linguistic variants per condition.
- Four compared approaches: scoring-only, evidence-aware, Traceability v2 and integrated ESDSA v2.

The benchmark responses and most provisional reference annotations were AI-assisted. Reference decisions were **not independently adjudicated ground truth**. The TEST scenarios were constructed after examination of VALIDATION findings, although TEST predictions were locked before reference comparison.

## Main reported results

Disagreement is measured **among actionable recommendations** against AI-assisted *pre-stability provisional references*. Coverage and disagreement must be interpreted together because each approach retains a different subset of responses.

| Approach | VALIDATION coverage | VALIDATION disagreement | TEST coverage | TEST disagreement |
|---|---:|---:|---:|---:|
| Scoring-only | 66.7% | 6.2% (9/144) | 71.30% | 1.95% (3/154) |
| Evidence-aware | 91.7% | 13.1% (26/198) | 92.59% | 4.50% (9/200) |
| Traceability v2 | 88.9% | 13.5% (26/192) | 90.28% | 4.10% (8/195) |
| Integrated ESDSA v2 | 76.9% | 9.0% (15/166) | 85.19% | 3.80% (7/184) |

In TEST, the stability gate deferred 11 previously actionable recommendations; ten had agreed with the provisional references. The results show procedural trade-offs rather than uniformly superior assessment performance.

## Repository layout

```text
src/esdsa/                 Original package and pilot validation utilities
scripts/development/       Pilot and development-stage scripts
scripts/validation/        Validation-stage scripts
scripts/test/              Held-out TEST-stage scripts
scripts/analysis/          Comparative analyses, audits and inspections
scripts/figures/           Figure-generation scripts
scripts/utilities/         Supporting evaluation and policy utilities
data/                      Benchmark materials, rubrics and references
results/                   Recorded model outputs, annotations and analyses
figures/                   Figures in PDF, PNG and SVG formats
archive/frozen_originals/  Byte-identical archived frozen implementations
docs/                      Migration and methodological documentation
tests/                     Existing automated tests
```

**Frozen implementation note:** The original scripts preserved in `archive/frozen_originals/` correspond to recorded frozen-policy hashes. Some working scripts were later stripped of comments and reorganised; their file hashes therefore differ even where their parsed Python syntax trees match. Consult the freeze manifests under `data/benchmark/policy_freeze_v2/` and `docs/repository_migration_v1.json`. Do not treat modified working-file hashes as the original freeze hashes.

## Installation and basic checks

Use Python 3.10 or newer from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

The existing test suite covers basic checks only; passing it **does not establish end-to-end reproduction** of the reported study.

### Inspecting preserved study outputs

The principal saved analyses are available at:

- `results/validation_esdsa_v2_analysis/validation_esdsa_v2_results.json`
- `results/test_esdsa_final_analysis_v1/test_esdsa_final_results_v1.json`
- `results/test_evaluator_predictions_v1/test_predictions_lock_v1.json`
- `data/benchmark/policy_freeze_v2/`

The repository retains experiment-stage scripts and the recorded artifacts needed for methodological inspection. A complete, independently verified **single-command reproduction workflow has not yet been established**. In particular, running generation and evaluation scripts afresh may require API credentials, incur charges and produce different model outputs. Do not assume that rerunning model calls reproduces the original locked predictions.

## Interpretation and limitations

- All interview responses are synthetic; no real applicants or employment outcomes were assessed.
- Provisional references are predominantly AI-assisted; no independent occupational-expert adjudication or inter-annotator reliability study was completed.
- Deterministic quotation matching checks excerpt occurrence, not whether the excerpt is relevant or correctly interpreted.
- Semantic-equivalence annotations may be uncertain or incorrect.
- Responses within scenario families are dependent; descriptive disagreement differences are not proof of statistical superiority.
- No operational recruitment validity, protected-group fairness, employment-law compliance or beneficial effect of deferral has been established.

**This is a research methodology and benchmark, not a production hiring tool or hiring recommendation service.**

## Citation and release status

Paper: *When AI Should Not Decide: Evidence Sufficiency and Decision Stability in Automated Job Interviews*. Citation details and an arXiv identifier will be added once publicly available.

**License:** Not selected yet. Public availability does not by itself grant reuse rights; a license will be decided before release.
