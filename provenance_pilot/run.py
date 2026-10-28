import csv
import json
import math
from dataclasses import asdict
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from .core import METHODS, estimate, oracle, approve
from .data import generate


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def validate_config(c):
    if set(c) != {'seed', 'instances', 'prior', 'q', 'threshold', 'workers'}:
        raise ValueError('unexpected or missing config keys')
    if type(c['seed']) is not int or type(c['instances']) is not int or c['instances'] < 2 or c['instances'] % 2:
        raise ValueError('seed must be integer; instances must be positive even integer')
    if c['prior'] != 0.5 or c['workers'] != 3:
        raise ValueError('pilot requires prior 0.5 and three workers')
    if not .5 < c['q'] < 1 or not 0 < c['threshold'] <= 1:
        raise ValueError('invalid reliability or threshold')


def summarize(rows, conditions=('single', 'replay', 'independent'), methods=METHODS):
    summaries = []
    for condition in conditions:
        for method in methods:
            subset = [r for r in rows if r['condition'] == condition and r['method'] == method]
            valid = [r for r in subset if r['probability'] is not None]
            s = {'condition': condition, 'method': method, 'n': len(subset), 'valid_probabilities': len(valid)}
            for field in ('probability', 'oracle_posterior', 'confidence_inflation', 'absolute_confidence_error', 'brier'):
                s['mean_' + field] = sum(r[field] for r in valid) / len(valid) if valid else None
            for metric, eligible, event in [
                ('premature_approval', lambda r: not r['oracle_approved'], lambda r: r['approved']),
                ('incorrect_approval', lambda r: r['y'] == 0, lambda r: r['approved']),
                ('legitimate_approval_retention', lambda r: r['oracle_approved'], lambda r: r['approved'])]:
                population = [r for r in subset if eligible(r)]
                count = sum(event(r) for r in population)
                s[metric + '_numerator'] = count
                s[metric + '_denominator'] = len(population)
                s[metric + '_rate'] = count / len(population) if population else None
            s['false_merge_pairs'] = sum(r['false_merge_pairs'] for r in subset)
            s['independent_report_pairs'] = sum(r['independent_report_pairs'] for r in subset)
            s['false_merge_rate'] = s['false_merge_pairs'] / s['independent_report_pairs'] if s['independent_report_pairs'] else None
            summaries.append(s)
    return summaries


def plot(path, summaries):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="920" height="460" viewBox="0 0 920 460">',
             '<rect width="920" height="460" fill="#f8fafc"/>',
             '<g font-family="sans-serif" fill="#172033">',
             '<text x="30" y="36" font-size="22">Offline mock pilot: probability error against oracle</text>',
             '<text x="30" y="62" font-size="14">Mean absolute error | 10 paired instances | Software diagnostics only</text>']
    colors = {'naive': '#c55a3a', 'hash': '#8164b1', 'lineage': '#16817a'}
    for i, condition in enumerate(('single', 'replay', 'independent')):
        x = 80 + 290 * i
        parts.append(f'<text x="{x}" y="365" font-size="18">{condition}</text>')
        for j, method in enumerate(METHODS):
            value = next(s['mean_absolute_confidence_error'] for s in summaries if s['condition'] == condition and s['method'] == method)
            height = value / .25 * 220
            bx = x + j * 65
            parts.append(f'<rect x="{bx}" y="{330-height:.3f}" width="45" height="{max(height,1):.3f}" fill="{colors[method]}"/>')
            parts.append(f'<text x="{bx}" y="{315-height:.3f}" font-size="13">{value:.3f}</text>')
    for j, method in enumerate(METHODS):
        parts.append(f'<rect x="{220+j*180}" y="402" width="16" height="16" fill="{colors[method]}"/><text x="{244+j*180}" y="416" font-size="16">{method}</text>')
    parts.append('<text x="30" y="100" font-size="12">Bar scale: 220 px = 0.25 probability error; labels give exact rounded values.</text></g></svg>')
    path.write_text(''.join(parts))


def run(config, output):
    validate_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    evidence_dir = output / 'evidence'
    evidence_dir.mkdir(exist_ok=True)
    registry, payloads, truth, cases = generate(config)
    write_json(output / 'config.json', config)
    jsonl(output / 'registry.jsonl', registry.export())
    for eid, payload in payloads.items():
        extension = '.svg' if eid.endswith('-card') else '.json'
        (evidence_dir / (eid + extension)).write_bytes(payload)
    # This is the only exported input surface intended for future model adapters.
    jsonl(output / 'worker_inputs.jsonl', [
        {'base_id': c['base_id'], 'condition': c['condition'], 'reports': [
            {'evidence_id': r.evidence_id, 'worker_id': r.worker_id, 'payload': r.payload.decode()}
            for r in c['reports']]} for c in cases])
    write_json(output / 'evaluator_truth.json', {'acquisition_values': truth, 'cases': [
        {k: v for k, v in c.items() if k != 'reports'} for c in cases]})
    rows = []
    for c in cases:
        reference = oracle(c['acquisitions'], truth, config['prior'], config['q'])
        for method in METHODS:
            result = estimate(method, c['reports'], registry if method == 'lineage' else None, config['prior'], config['q'])
            p = result.probability
            all_pairs = list(combinations(range(len(c['reports'])), 2))
            independent = {(a,b) for a,b in all_pairs if c['acquisitions'][a] != c['acquisitions'][b]}
            merged = {pair for group in result.groups for pair in combinations(group, 2)}
            row = {'base_id': c['base_id'], 'condition': c['condition'], 'method': method,
                   'probability': p, 'oracle_posterior': reference, 'y': c['y'],
                   'approved': approve(p, config['threshold']), 'oracle_approved': approve(reference, config['threshold']),
                   'status': result.status, 'groups': result.groups,
                   'confidence_inflation': p-reference if p is not None else None,
                   'absolute_confidence_error': abs(p-reference) if p is not None else None,
                   'brier': (p-c['y'])**2 if p is not None else None,
                   'false_merge_pairs': len(independent & merged), 'independent_report_pairs': len(independent)}
            row['premature_approval'] = row['approved'] and not row['oracle_approved']
            row['incorrect_approval'] = row['approved'] and c['y'] == 0
            # Direction-normalized measure is diagnostic only, for replay logs.
            row['copy_weight'] = ((2 * truth[c['acquisitions'][0]] - 1) * math.log(p/(1-p)) / math.log(config['q']/(1-config['q'])) - 1) / 2 if c['condition'] == 'replay' and p is not None else None
            rows.append(row)
    jsonl(output / 'results.jsonl', rows)
    summary = summarize(rows)
    write_json(output / 'summary.json', summary)
    with (output / 'summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    plot(output / 'comparison.svg', summary)
    # Explicit positive control outside the sampled ten-instance metric population.
    from .core import Registry, Evidence, MockWorker, record
    diagnostic_registry = Registry()
    reports = []
    for i in range(3):
        eid = f'diagnostic-{i}'
        diagnostic_registry.add(Evidence(eid, (eid,), (), 'acquire', 'application/json'))
        reports.append(MockWorker().report(eid, f'worker-{i}', record(1)))
    write_json(output / 'identical_independent_diagnostic.json', {
        'included_in_pilot_metrics': False, 'description': 'Three distinct acquisitions with byte-identical positive payloads',
        'oracle_posterior': oracle([r.evidence_id for r in reports], {r.evidence_id: 1 for r in reports}),
        'methods': {m: asdict(estimate(m, reports, diagnostic_registry if m == 'lineage' else None)) for m in METHODS}})
    files = [p for p in output.rglob('*') if p.is_file() and p.name != 'manifest.json']
    write_json(output / 'manifest.json', {str(p.relative_to(output)): sha256(p.read_bytes()).hexdigest() for p in sorted(files)})
    return rows
