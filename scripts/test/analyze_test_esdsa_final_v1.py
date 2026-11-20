
"""One-pass, read-only ESDSA TEST comparison; no API calls or tuning.

Inputs: locked evaluator predictions, TEST responses, blinded linkage,
completed provisional references, frozen v2 implementations.
Outputs: final TEST record CSV, summary JSON and readable report.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'results/test_generation_v1/test_responses_v1.csv'
LOCK = ROOT / 'results/test_evaluator_predictions_v1/test_predictions_lock_v1.json'
EVAL_DIR = ROOT / 'results/test_evaluator_predictions_v1'
KEY = ROOT / 'results/test_ai_annotations_v2/test_annotation_blinding_key_v2.csv'
TEMPLATE = ROOT / 'results/test_ai_annotations_v2/test_evidence_template_v2.csv'
TEMPLATE_MANIFEST = ROOT / 'results/test_ai_annotations_v2/test_annotation_template_manifest_v2.json'
REF = ROOT / 'results/test_provisional_references_v1/test_provisional_references_v1.json'
REF_MANIFEST = ROOT / 'results/test_provisional_references_v1/reference_preparation_manifest_v1.json'
POLICY = ROOT / 'data/benchmark/policy_freeze_v2/esdsa_v2_policy_freeze.json'
OUT = ROOT / 'results/test_esdsa_final_analysis_v1'
CSV_OUT = OUT / 'test_esdsa_final_records_v1.csv'
JSON_OUT = OUT / 'test_esdsa_final_results_v1.json'
TXT_OUT = OUT / 'test_esdsa_final_summary_v1.txt'
METHODS = ('scoring_only', 'evidence_aware', 'traceability_v2', 'integrated_v2')
ACTIONABLE = {'ADVANCE', 'DO_NOT_ADVANCE'}
DECISIONS = ACTIONABLE | {'DEFER'}


def need(value, message):
    if not value:
        raise ValueError(message)


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    need(path.is_file(), f'Missing required input: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def load_csv(path):
    need(path.is_file(), f'Missing required input: {path}')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path):
    need(path.is_file(), f'Missing required input: {path}')
    with path.open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def unique(items, key, count, label):
    result = {row[key]: row for row in items}
    need(len(items) == len(result) == count, f'{label}: duplicate/missing IDs')
    return result


def pick(item, *keys):
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def model_criteria(prediction, expected_ids):
    """Accept common schema field names, but never silently infer labels."""
    parsed = prediction.get('parsed_output')
    need(isinstance(parsed, dict), 'Evidence prediction lacks parsed_output object')
    items = pick(parsed, 'criteria', 'criterion_evaluations', 'evaluations')
    need(isinstance(items, list) and len(items) == 3,
         f'Expected three evidence criteria: {prediction["response_id"]}; parsed keys={list(parsed)}')
    out = {}
    for item in items:
        cid = pick(item, 'criterion_id', 'id')
        status = pick(item, 'status', 'evidence_status', 'classification')
        excerpt = pick(item, 'passage', 'excerpt', 'supporting_passage',
                       'supporting_excerpt', 'evidence_excerpt', 'quote')
        need(cid in expected_ids and cid not in out,
             f'Criterion mapping error: {prediction["response_id"]}: {cid}')
        need(status in {'POSITIVE_EVIDENCE', 'NEGATIVE_EVIDENCE', 'INSUFFICIENT_EVIDENCE'},
             f'Unexpected evidence status: {prediction["response_id"]}: {status}')
        need(excerpt is None or isinstance(excerpt, str), 'Evidence excerpt must be text')
        out[cid] = (status, excerpt or '')
    need(set(out) == set(expected_ids), 'Evidence criteria do not match rubric')
    return out


def metrics(rows, method, ref_key):
    n = len(rows)
    actionable = [r for r in rows if r[method] in ACTIONABLE]
    mismatches = [r for r in actionable if r[method] != r[ref_key]]
    unsupported = [r for r in rows if r[method] == 'ADVANCE' and r[ref_key] != 'ADVANCE']
    direct_conflicts = [r for r in rows if r[method] == 'ADVANCE' and r[ref_key] == 'DO_NOT_ADVANCE']
    return {
        'total': n,
        'decisions': dict(Counter(r[method] for r in rows)),
        'actionable': len(actionable),
        'coverage_pct': round(100 * len(actionable) / n, 2),
        'actionable_disagreements': len(mismatches),
        'disagreement_pct_among_actionable': round(100 * len(mismatches) / len(actionable), 2) if actionable else None,
        'advance_not_supported_by_reference': len(unsupported),
        'advance_vs_reference_do_not_advance': len(direct_conflicts),
        'deferrals': n - len(actionable),
    }


def main():
    for path in (CSV_OUT, JSON_OUT, TXT_OUT):
        need(not path.exists(), f'Final output already exists; will not overwrite: {path}')

    frozen = load_json(POLICY)
    need(frozen['policy_version'] == 'ESDSA-v2-development-frozen', 'Unexpected freeze')
    for name in ('audit_traceability_v2.py', 'evaluate_traceability_policy_v2.py',
                 'evaluate_integrated_esdsa_v2.py'):
        need(hash_file(ROOT / "archive/frozen_originals" / name) == frozen['implementation_file_sha256'][name],
             f'Frozen implementation changed: {name}')
    from audit_traceability_v2 import classify
    from evaluate_traceability_policy_v2 import new_decision

    lock = load_json(LOCK)
    need(lock['status'] == 'LOCKED' and hash_file(DATA) == lock['dataset_sha256'],
         'TEST predictions or source dataset no longer match lock')
    for meta in lock['prediction_files'].values():
        path = ROOT / meta['file']
        need(hash_file(path) == meta['sha256'] and meta['records'] == 216,
             f'Locked file altered or incomplete: {path}')

    source = unique(load_csv(DATA), 'response_id', 216, 'TEST source')
    need(all(r['partition'] == 'TEST' for r in source.values()), 'Non-TEST source row')

    predictions = {}
    for method, filename in (('scoring_only', 'scoring_only_test_v1.jsonl'),
                             ('evidence_aware', 'evidence_aware_test_v1.jsonl')):
        predictions[method] = unique(load_jsonl(EVAL_DIR / filename), 'response_id', 216, method)
        need(set(predictions[method]) == set(source), f'{method} IDs do not match dataset')
        for rid, pred in predictions[method].items():
            need(pred['decision'] in DECISIONS and pred['partition'] == 'TEST',
                 f'Invalid decision/partition: {method}/{rid}')
            need(pred['answer_sha256'] == source[rid]['answer_sha256'],
                 f'Source answer changed: {method}/{rid}')

    reference_report = load_json(REF)
    reference_manifest = load_json(REF_MANIFEST)
    need(reference_manifest['status'] == 'COMPLETE', 'Reference preparation incomplete')
    need(reference_manifest['output_sha256'][REF.name] == hash_file(REF),
         'Reference file differs from preparation manifest')
    template_manifest = load_json(TEMPLATE_MANIFEST)
    need(hash_file(TEMPLATE) == template_manifest['evidence_template_sha256'],
         'Evidence template differs from original annotation source')
    template_rows = unique(load_csv(TEMPLATE), 'blinded_response_id', 216, 'TEST annotation template')
    ref_rows = unique(reference_report['all_records'], 'blinded_response_id', 216, 'TEST reference')
    need(set(template_rows) == set(ref_rows), 'Evidence templates and references differ')
    key_rows = unique(load_csv(KEY), 'blinded_response_id', 216, 'blinding key')
    need(set(ref_rows) == set(key_rows), 'Blinding key and reference IDs differ')
    need(len({r['original_response_id'] for r in key_rows.values()}) == 216,
         'Blinding key maps multiple records onto one response')
    need(set(r['original_response_id'] for r in key_rows.values()) == set(source),
         'Blinding key does not cover TEST responses')

    groups = defaultdict(list)
    rows = []
    citation_counts = Counter()
    for bid, ref in ref_rows.items():
        rid = key_rows[bid]['original_response_id']
        src = source[rid]
        evid = predictions['evidence_aware'][rid]
        expected_ids = [c['criterion_id'] for c in ref['criteria']]
        need(len(set(expected_ids)) == 3, f'Invalid reference rubric: {bid}')
        observed = model_criteria(evid, expected_ids)
        criteria = []
        criteria_question = template_rows[bid]['interview_question']
        need(bool(criteria_question), f'Missing original interview question: {bid}')
        for cid in expected_ids:
            status, excerpt = observed[cid]
            if status == 'INSUFFICIENT_EVIDENCE':
                outcome, reason = 'NOT_APPLICABLE', 'insufficient_evidence'
            else:
                # The classifier is the frozen implementation; quote verification
                # is an exact substring check of the candidate answer.
                outcome, reason = classify(excerpt, src['answer'], criteria_question)
            citation_counts[outcome] += 1
            criteria.append({'criterion_id': cid, 'evidence_status': status,
                             'excerpt': excerpt, 'v2_outcome': outcome, 'v2_reason': reason})
        trace_decision, trace_reason = new_decision(criteria)
        need(trace_decision in DECISIONS, f'Invalid frozen decision: {rid}')
        row = {
            'response_id': rid,
            'family_id': src['family_id'],
            'blinded_group_id': ref['blinded_group_id'],
            'semantic_equivalence': ref['semantic_equivalence'],
            'reference_pre_stability': ref['provisional_evidence_decision'],
            'reference_post_stability': ref['provisional_integrated_decision'],
            'manual_reference_adjudication': bool(ref.get('manual_adjudication', False)),
            'scoring_only': predictions['scoring_only'][rid]['decision'],
            'evidence_aware': evid['decision'],
            'traceability_v2': trace_decision,
            'traceability_reason': trace_reason,
            'integrated_v2': None,
            'stability_gate_reason': None,
        }
        need(row['reference_pre_stability'] in DECISIONS and
             row['reference_post_stability'] in DECISIONS, f'Invalid reference: {rid}')
        rows.append(row)
        groups[row['blinded_group_id']].append(row)

    need(len(groups) == 72 and all(len(group) == 3 for group in groups.values()),
         'Stability group size mismatch')
    for gid, group in groups.items():
        states = {r['semantic_equivalence'] for r in group}
        need(len(states) == 1 and next(iter(states)) in {'YES', 'NO', 'UNCERTAIN'},
             f'Inconsistent semantic status: {gid}')
        equivalence = next(iter(states))
        pre = [r['traceability_v2'] for r in group]
        unanimous_actionable = len(set(pre)) == 1 and pre[0] in ACTIONABLE
        for row in group:
            if equivalence == 'YES' and not unanimous_actionable:
                row['integrated_v2'] = 'DEFER'
                row['stability_gate_reason'] = 'EQUIVALENT_GROUP_NOT_UNANIMOUS'
            elif equivalence == 'YES':
                row['integrated_v2'] = row['traceability_v2']
                row['stability_gate_reason'] = 'EQUIVALENT_UNANIMOUS_ACTIONABLE'
            else:
                row['integrated_v2'] = row['traceability_v2']
                row['stability_gate_reason'] = 'STABILITY_NOT_ASSESSED_' + equivalence

    primary = {method: metrics(rows, method, 'reference_pre_stability') for method in METHODS}
    secondary = {method: metrics(rows, method, 'reference_post_stability') for method in METHODS}
    newly_deferred = [r for r in rows if r['traceability_v2'] in ACTIONABLE and r['integrated_v2'] == 'DEFER']
    gate = {
        'new_deferrals': len(newly_deferred),
        'new_deferrals_that_were_pre_reference_disagreements': sum(
            r['traceability_v2'] != r['reference_pre_stability'] for r in newly_deferred),
        'new_deferrals_that_previously_matched_reference': sum(
            r['traceability_v2'] == r['reference_pre_stability'] for r in newly_deferred),
    }
    need(gate['new_deferrals_that_were_pre_reference_disagreements'] +
         gate['new_deferrals_that_previously_matched_reference'] == gate['new_deferrals'],
         'Stability gate attribution failed')

    rows.sort(key=lambda r: r['response_id'])
    report = {
        'stage': 'ESDSA_FINAL_TEST_COMPARISON_V1',
        'completed_utc': datetime.now(timezone.utc).isoformat(),
        'test_responses': len(rows), 'scenario_families': 24, 'semantic_groups': len(groups),
        'comparison_reference': 'AI-assisted provisional evidence reference; not independent ground truth',
        'primary_comparison_pre_stability': primary,
        'secondary_comparison_post_stability': secondary,
        'stability_gate': gate,
        'traceability_outcomes': dict(citation_counts),
        'provisional_reference_manual_adjudications': sum(r['manual_reference_adjudication'] for r in rows),
        'input_sha256': {'dataset': hash_file(DATA), 'prediction_lock': hash_file(LOCK),
                         'references': hash_file(REF), 'blinding_key': hash_file(KEY),
                         'frozen_policy': hash_file(POLICY), 'evidence_template': hash_file(TEMPLATE)},
        'limitations': [
            'The references are AI-assisted rather than independent human ground truth.',
            'The same model family generated responses and annotated most references.',
            'Two reference evidence annotations were manually adjudicated with AI assistance.',
            'TEST scenarios were authored after observing VALIDATION results.',
            'The 216 responses are clustered within 24 scenario families; not 216 independent cases.',
            'Reference post-stability decisions reuse the semantic gate and are not an independent comparator.',
            'Verbatim citation verification is not proof of substantively correct interpretation.',
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with JSON_OUT.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write('\n')

    lines = ['ESDSA — FINAL HELD-OUT TEST RESULTS', '=' * 88,
             '216 responses / 24 scenario families / 72 semantic groups',
             'PRIMARY: disagreement with AI-assisted PRE-STABILITY provisional references',
             'METHOD                  COVERAGE     DISAGREE/ACTIONABLE   ADVANCE!=REF   DEFER',
             '-' * 88]
    for method in METHODS:
        x = primary[method]
        lines.append(f'{method:23} {x["coverage_pct"]:6.2f}%      '
                     f'{x["actionable_disagreements"]:3}/{x["actionable"]:<3} ({x["disagreement_pct_among_actionable"]:5.2f}%)'
                     f'       {x["advance_not_supported_by_reference"]:3}          {x["deferrals"]:3}')
    lines += ['', 'POST-STABILITY reference comparison:']
    for method in METHODS:
        x = secondary[method]
        lines.append(f'{method}: coverage={x["coverage_pct"]:.2f}%; '
                     f'disagreements={x["actionable_disagreements"]}/{x["actionable"]}; '
                     f'ADVANCE!=reference={x["advance_not_supported_by_reference"]}')
    lines += ['', f'New deferrals due to ESDSA stability gate: {gate["new_deferrals"]}',
              f'  Previously disagreed with provisional reference: {gate["new_deferrals_that_were_pre_reference_disagreements"]}',
              f'  Previously matched provisional reference: {gate["new_deferrals_that_previously_matched_reference"]}',
              f'Frozen citation results: {dict(citation_counts)}',
              'CAUTION: AI-assisted provisional reference agreement, NOT independently validated accuracy.',
              f'Records: {CSV_OUT}', f'JSON: {JSON_OUT}']
    TXT_OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    print('No API calls. Source files and frozen policy unchanged.')


if __name__ == '__main__':
    main()
