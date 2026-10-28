"""Offline transformation experiment. Mock fixture claims, never vision extraction."""
import argparse
import csv
import json
import platform
import random
from hashlib import sha256
from itertools import combinations
from pathlib import Path

from .core import Evidence, Registry, Report, Estimate, estimate, oracle, approve
from .data import generate
from .run import write_json, jsonl, summarize, validate_config

MODE = 'mock_software_diagnostic_no_vision_extraction'
METHODS = ('naive', 'hash', 'lineage', 'perceptual')
CONDITIONS = ('single_raster', 'exact_replay', 'resized_jpeg', 'cropped_replay', 'cross_modal', 'independent_raster')


def fixture_report(evidence_id, worker_id, payload, fixture_reading):
    """Explicit observation fixture input, not hidden Y or a pixel decoding result."""
    if type(fixture_reading) is not int or fixture_reading not in (0,1):
        raise ValueError('invalid fixture reading')
    return Report(evidence_id, worker_id, payload, fixture_reading)


def synthetic_record(fixture_reading):
    # Deliberately labeled in the actual bytes being hashed.
    return json.dumps({'mode': MODE, 'conversion': 'synthetic_fixture_conversion_not_pixel_extraction',
                       'sensor_value': fixture_reading}, sort_keys=True).encode()


def validate_settings(config):
    base = {k: config[k] for k in ('seed','instances','prior','q','threshold','workers')}
    validate_config(base)
    if config['instances'] != 10:
        raise ValueError('this milestone is restricted to ten evaluation instances')
    if type(config['calibration_roots']) is not int or config['calibration_roots'] < 2:
        raise ValueError('at least two calibration roots required')
    if type(config['calibration_seed']) is not int or config['calibration_seed'] == config['seed']:
        raise ValueError('use a separate calibration seed')
    return base


def add_family(registry, payloads, rasters, readings, root, value, config, style=0):
    from .imaging import render, resize, compress, crop, signal_check
    if root not in registry.nodes:
        registry.add(Evidence(root, (root,), (), 'acquire', 'sensor', {'mode': MODE}))
    original = render(value, style)
    resized = resize(original, config['resize'])
    jpeg = compress(original, config['jpeg_quality'])
    cropped = crop(jpeg, config['crop_box'])
    family = [
        ('png', root, 'render_raster', original, {'size': [320,180], 'style': style, 'renderer': 'seven_segment_v1'}),
        ('resize', root+'-png', 'resize', resized, {'size': config['resize'], 'resampling': 'LANCZOS'}),
        ('jpeg', root+'-png', 'jpeg_compress', jpeg, {'quality': config['jpeg_quality'], 'subsampling': 0, 'optimize': False}),
        ('crop', root+'-jpeg', 'signal_preserving_crop', cropped, {'box': config['crop_box']})]
    checks = []
    for suffix, parent, operation, raster, parameters in family:
        eid = root+'-'+suffix
        registry.derive(eid, [parent], operation, raster.modality, {'mode': MODE, **parameters})
        rasters[eid] = raster
        payloads[eid] = raster.payload
        readings[eid] = value
        check = signal_check(raster, value)
        checks.append({'mode': MODE, 'evidence_id': eid, **check})
        if not check['passed']:
            raise ValueError('signal preservation failed: '+eid)
    eid = root+'-synthetic-record'
    registry.derive(eid, [root+'-crop'], 'synthetic_image_to_record', 'application/json',
                    {'mode': MODE, 'implementation': 'copy_fixture_reading; no pixel extraction'})
    payloads[eid] = synthetic_record(value)
    readings[eid] = value
    return checks


def score(base_id, condition, ids, assignments, y, registry, payloads, readings, truth, threshold, config, split):
    from .matching import perceptual_estimate
    # Router changes envelopes only; report payload is the actual artifact bytes.
    reports = []
    for i, eid in enumerate(ids):
        rid = f'{base_id}-{condition}-worker{i}'
        registry.derive(rid, [eid], 'route', registry.nodes[eid].modality, {'mode': MODE, 'worker': i})
        reports.append(fixture_report(rid, f'worker-{i}', payloads[eid], readings[eid]))
    reference = oracle(assignments, truth, config['prior'], config['q'])
    all_pairs = set(combinations(range(len(ids)),2))
    independent = {pair for pair in all_pairs if assignments[pair[0]] != assignments[pair[1]]}
    shared = all_pairs-independent
    rows = []
    modalities = [registry.nodes[eid].modality for eid in ids]
    for method in METHODS:
        try:
            result = perceptual_estimate(reports, modalities, threshold, config['prior'], config['q']) if method == 'perceptual' else estimate(
                method, reports, registry if method == 'lineage' else None, config['prior'], config['q'])
        except (OSError, ValueError) as exc:
            # Expected decoding/validation failures remain attempted evaluations.
            # Programming errors still propagate and mark the entire run failed.
            result = Estimate(None, [], f'failure: {type(exc).__name__}: {exc}')
        p = result.probability
        members = [i for group in result.groups for i in group]
        grouping_valid = sorted(members) == list(range(len(reports))) and all(result.groups)
        merged = {pair for group in result.groups for pair in combinations(group,2)}
        approved, eligible = approve(p,config['threshold']), approve(reference,config['threshold'])
        rows.append({'mode': MODE, 'split': split, 'base_id': base_id, 'condition': condition, 'method': method,
                     'evidence_ids': ids, 'report_ids': [r.evidence_id for r in reports],
                     'payload_hashes': [sha256(r.payload).hexdigest() for r in reports],
                     'probability': p, 'oracle_posterior': reference, 'y': y, 'status': result.status,
                     'groups': result.groups, 'approved': approved, 'oracle_approved': eligible,
                     'premature_approval': approved and not eligible,
                     'incorrect_approval': approved and y == 0 if y is not None else None,
                     'confidence_inflation': p-reference if p is not None else None,
                     'absolute_confidence_error': abs(p-reference) if p is not None else None,
                     'brier': (p-y)**2 if p is not None and y is not None else None,
                     'grouping_valid': grouping_valid,
                     'false_merge_pairs': len(merged & independent) if grouping_valid else None, 'independent_report_pairs': len(independent),
                     'false_split_pairs': len(shared-merged) if grouping_valid else None, 'same_root_report_pairs': len(shared),
                     'unsupported_modality_pairs': sum(not all(modalities[k] in ('image/png','image/jpeg') for k in pair) for pair in all_pairs) if method == 'perceptual' else 0})
    inputs = {'mode': MODE, 'base_id': base_id, 'condition': condition, 'reports': [
        {'evidence_id': r.evidence_id, 'worker_id': r.worker_id, 'artifact_id': eid,
         'fixture_reading': r.value, 'reading_source': 'synthetic_fixture_not_pixels'} for r,eid in zip(reports,ids)]}
    return rows, inputs


def summarize_results(rows):
    """Attempted-case decision denominators; matching rates require a valid partition."""
    summaries = summarize(rows, CONDITIONS, METHODS)
    for summary in summaries:
        subset = [r for r in rows if r['condition']==summary['condition'] and r['method']==summary['method']]
        grouped = [r for r in subset if r['grouping_valid']]
        summary['mode'] = MODE
        summary['oracle_posterior_denominator'] = len(subset)
        summary['probability_coverage'] = summary['valid_probabilities']/len(subset) if subset else None
        summary['grouping_valid_cases'] = len(grouped)
        summary['grouping_unavailable_cases'] = len(subset)-len(grouped)
        summary['attempted_independent_report_pairs'] = sum(r['independent_report_pairs'] for r in subset)
        summary['attempted_same_root_report_pairs'] = sum(r['same_root_report_pairs'] for r in subset)
        summary['false_split_pairs'] = sum(r['false_split_pairs'] for r in grouped)
        summary['same_root_report_pairs'] = sum(r['same_root_report_pairs'] for r in grouped)
        summary['false_split_rate'] = summary['false_split_pairs']/summary['same_root_report_pairs'] if summary['same_root_report_pairs'] else None
        summary['abstentions'] = sum(r['status'].startswith('abstain:') for r in subset)
        summary['failures'] = sum(r['status'].startswith('failure:') for r in subset)
        summary['non_probability_cases'] = sum(r['probability'] is None for r in subset)
        summary['unsupported_modality_pairs'] = sum(r['unsupported_modality_pairs'] for r in subset)
    return summaries


def _run(config, output):
    # Optional import means the original pilot remains dependency-free.
    import PIL
    from PIL import features
    from .imaging import contact_sheet
    from .matching import calibrate
    base_config = validate_settings(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    evidence = output/'evidence'
    evidence.mkdir()
    registry, payloads, truth, cases = generate(base_config)
    rasters, readings, checks = {}, {}, []
    # Evaluation acquisitions are exactly those generated by the original pilot.
    for root,value in truth.items():
        checks += add_family(registry,payloads,rasters,readings,root,value,config)

    calibration_registry, calibration_payloads, calibration_rasters, calibration_readings = Registry(), {}, {}, {}
    calibration_checks = []
    rng = random.Random(config['calibration_seed'])
    for i in range(config['calibration_roots']):
        root = f'cal-{i:03d}'
        # Calibration need only ancestry labels and observation appearances, not Y.
        value = rng.randrange(2)
        calibration_checks += add_family(calibration_registry,calibration_payloads,calibration_rasters,calibration_readings,root,value,config,style=i%3)
    calibration_items = [(eid, next(iter(calibration_registry.validate(eid))),r.payload) for eid,r in calibration_rasters.items()]
    calibration = calibrate(calibration_items)
    evaluation_roots = set(truth)
    if not evaluation_roots.isdisjoint(calibration['root_ids']):
        raise ValueError('calibration and evaluation acquisition roots overlap')
    # Threshold is frozen before any evaluation method is invoked.
    write_json(output/'calibration.json', calibration)
    cal_dir = output/'calibration_evidence'
    cal_dir.mkdir()
    for eid,payload in calibration_payloads.items():
        extension = '.jpg' if calibration_registry.nodes[eid].modality == 'image/jpeg' else '.png' if eid in calibration_rasters else '.json'
        (cal_dir/(eid+extension)).write_bytes(payload)
    jsonl(output/'calibration_provenance.jsonl', calibration_registry.export())
    jsonl(output/'calibration_signal_checks.jsonl',calibration_checks)

    rows, inputs, assignments = [], [], []
    for case in (c for c in cases if c['condition']=='independent'):
        root, r1, r2 = case['acquisitions']
        variants = {
            'single_raster': ([root+'-png'], [root]),
            'exact_replay': ([root+'-png']*3, [root]*3),
            'resized_jpeg': ([root+'-png',root+'-resize',root+'-jpeg'], [root]*3),
            'cropped_replay': ([root+'-png',root+'-jpeg',root+'-crop'], [root]*3),
            'cross_modal': ([root+'-png',root+'-crop',root+'-synthetic-record'], [root]*3),
            'independent_raster': ([r+'-png' for r in (root,r1,r2)], [root,r1,r2])}
        for condition,(ids,roots) in variants.items():
            result, worker_input = score(case['base_id'],condition,ids,roots,case['y'],registry,payloads,readings,truth,calibration['threshold'],config,'evaluation')
            rows += result
            inputs.append(worker_input)
            assignments.append({'base_id':case['base_id'],'condition':condition,'acquisitions':roots,'y':case['y']})

    # Constructed controls; not sampled cases and never mixed into headline summaries.
    controls = []
    for kind in ('similar_independent','identical_independent'):
        roots = [f'control-{kind}-{i}' for i in range(3)]
        for i,root in enumerate(roots):
            truth[root] = 1
            checks += add_family(registry,payloads,rasters,readings,root,1,config,style=i if kind=='similar_independent' else 0)
        result, worker_input = score('control',kind,[r+'-png' for r in roots],roots,None,registry,payloads,readings,truth,calibration['threshold'],config,'constructed_control')
        controls += result
        inputs.append(worker_input)
    root = 'b000-a0'
    result, worker_input = score('control','different_looking_shared_root',[root+'-png',root+'-resize',root+'-crop'],[root]*3,None,registry,payloads,readings,truth,calibration['threshold'],config,'constructed_control')
    controls += result
    inputs.append(worker_input)

    artifact_index = []
    for eid,payload in payloads.items():
        modality = registry.nodes[eid].modality
        extension = {'image/svg+xml':'.svg','image/png':'.png','image/jpeg':'.jpg','application/json':'.json'}[modality]
        file = evidence/(eid+extension)
        file.write_bytes(payload)
        artifact_index.append({'mode':MODE,'evidence_id':eid,'path':str(file.relative_to(output)),
                               'modality':modality,'sha256':sha256(payload).hexdigest()})
    sheet_rows = [(f'b{i:03d}',[(name,rasters[f'b{i:03d}-a0-{suffix}']) for name,suffix in
                              [('original PNG','png'),('resized PNG','resize'),('compressed JPEG','jpeg'),('crop of JPEG','crop')]]) for i in range(10)]
    contact_sheet(output/'contact_sheet.png',sheet_rows)
    control_rows = [(kind, [(f'acquisition {i}',rasters[f'control-{kind}-{i}-png']) for i in range(3)]) for kind in ('similar_independent','identical_independent')]
    contact_sheet(output/'controls_contact_sheet.png',control_rows, 'Each row contains THREE DISTINCT acquisition roots with positive fixture readings.')
    jsonl(output/'provenance.jsonl',registry.export())
    jsonl(output/'artifacts.jsonl',artifact_index)
    jsonl(output/'signal_checks.jsonl',checks)
    jsonl(output/'worker_inputs.jsonl',inputs)
    jsonl(output/'results.jsonl',rows)
    jsonl(output/'controls.jsonl',controls)
    write_json(output/'evaluator_truth.json',{'mode':MODE,'acquisition_values':truth,'evaluation_assignments':assignments,
                                           'note':'Constructed controls have no sampled hidden state and no Brier or incorrect-approval metric.'})
    summaries = summarize_results(rows)
    write_json(output/'summary.json',summaries)
    with (output/'summary.csv').open('w',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    write_json(output/'config.json',{'mode':MODE, **config})
    write_json(output/'environment.json',{'mode':MODE,'python':platform.python_version(),'pillow':PIL.__version__,
                                       'jpeg_codec':features.version_codec('jpg')})
    (output/'README.txt').write_text('MOCK SOFTWARE DIAGNOSTICS ONLY. No vision extraction or LLM calls.\n'
        'Worker fixture readings are observations, not hidden states. Evaluator truth and signal checks are not worker inputs.\n'
        'PNG/JPEG crops may omit visible mock labels; all files belong to this synthetic fixture dataset.\n'
        'Calibration roots and constructed controls are separate from the ten evaluation instances.\n')
    write_json(output/'run_status.json', {'mode': MODE, 'status': 'complete', 'attempted_evaluations': len(rows),
                                        'method_failures': sum(r['status'].startswith('failure:') for r in rows),
                                        'abstentions': sum(r['status'].startswith('abstain:') for r in rows),
                                        'signal_checks': len(checks)+len(calibration_checks)})
    write_json(output/'manifest.json',{str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'})
    return rows


def run(config, output):
    """A failed generation cannot masquerade as a completed benchmark."""
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('use an empty output directory to prevent stale artifacts')
    output.mkdir(parents=True, exist_ok=True)
    write_json(output/'run_status.json', {'mode': MODE, 'status': 'running'})
    try:
        return _run(config, output)
    except Exception as exc:
        write_json(output/'run_status.json', {'mode': MODE, 'status': 'failed',
                   'error_type': type(exc).__name__, 'error': str(exc),
                   'note': 'Incomplete run: do not treat partial files as benchmark results.'})
        raise


def main():
    parser = argparse.ArgumentParser(description='Offline MOCK raster transformations and matching diagnostics; no vision extraction.')
    parser.add_argument('--config',type=Path,default=Path('configs/transformations.json'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/transformations'))
    args = parser.parse_args()
    try:
        rows = run(json.loads(args.config.read_text()),args.output)
    except ModuleNotFoundError as exc:
        if exc.name == 'PIL':
            parser.error('Pillow is required for this optional milestone. Use a Python environment with Pillow 12.3.0 installed; the original pilot remains dependency-free.')
        raise
    print(f'MOCK ONLY: wrote {len(rows)} evaluations to {args.output.resolve()}; no vision-model extraction.')


if __name__ == '__main__':
    main()
