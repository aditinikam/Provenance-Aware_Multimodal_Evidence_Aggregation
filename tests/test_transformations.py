"""Full milestone suite requires the optional Pillow environment; no downloads."""
import json
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

try:
    import PIL
except ImportError:
    raise unittest.SkipTest('Optional transformation tests require Pillow; use .venv/bin/python')

from provenance_pilot.core import Evidence, Registry, Report, Estimate, estimate, oracle
from provenance_pilot.data import generate
from provenance_pilot.imaging import render, resize, compress, crop, signal_check, decode, encode, Raster
from provenance_pilot.matching import calibrate, feature, distance, perceptual_estimate
from provenance_pilot.transformations import run, add_family, fixture_report, synthetic_record, validate_settings, score, summarize_results

CONFIG = json.loads((Path(__file__).resolve().parents[1]/'configs/transformations.json').read_text())


class TransformationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.tmp.name)/'run'
        cls.rows = run(CONFIG, cls.output)
        cls.provenance = [json.loads(line) for line in (cls.output/'provenance.jsonl').read_text().splitlines()]
        cls.index = {r['evidence_id']:r for r in map(json.loads,(cls.output/'artifacts.jsonl').read_text().splitlines())}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_root_inheritance_and_fixture_values(self):
        reg, payloads, rasters, readings = Registry(), {}, {}, {}
        for value in (0,1):
            root = f'root{value}'
            checks = add_family(reg,payloads,rasters,readings,root,value,CONFIG)
            self.assertTrue(all(c['passed'] for c in checks))
            for suffix in ('png','resize','jpeg','crop','synthetic-record'):
                eid = root+'-'+suffix
                self.assertEqual(reg.validate(eid),{root})
                self.assertEqual(readings[eid],value)
                self.assertTrue(reg.nodes[eid].parameters)
            self.assertEqual(reg.nodes[root+'-crop'].parent_ids,(root+'-jpeg',))
            self.assertEqual(reg.nodes[root+'-synthetic-record'].parent_ids,(root+'-crop',))
            record = json.loads(payloads[root+'-synthetic-record'])
            self.assertEqual(record['sensor_value'],value)
            self.assertIn('not_pixel_extraction',record['conversion'])

    def test_image_dimensions_formats_and_signal(self):
        for value in (0,1):
            original = render(value)
            resized = resize(original,CONFIG['resize'])
            jpeg = compress(original,CONFIG['jpeg_quality'])
            cropped = crop(jpeg,CONFIG['crop_box'])
            self.assertEqual(decode(resized.payload).size,tuple(CONFIG['resize']))
            self.assertEqual(decode(cropped.payload).size,(120,113))
            self.assertTrue(original.payload.startswith(b'\x89PNG'))
            self.assertTrue(jpeg.payload.startswith(b'\xff\xd8'))
            self.assertEqual(len({a.payload for a in (original,resized,jpeg,cropped)}),4)
            self.assertTrue(all(signal_check(a,value)['passed'] for a in (original,resized,jpeg,cropped)))
            self.assertFalse(signal_check(original,1-value)['passed'])

    def test_invalid_transformations_and_destroyed_signal(self):
        source = render(1)
        with self.assertRaises(ValueError): crop(source,(140,60,190,150))
        with self.assertRaises(ValueError): crop(source,(-1,0,320,180))
        with self.assertRaises(ValueError): compress(source,0)
        self.assertFalse(signal_check(resize(source,(32,18)),1)['passed'])
        from PIL import ImageDraw
        destroyed = decode(source.payload)
        ImageDraw.Draw(destroyed).rectangle(source.roi,fill='black')
        self.assertFalse(signal_check(replace(source,payload=encode(destroyed)),1)['passed'])

    def test_claim_boundary_does_not_decode_pixels(self):
        # Malformed pixels are accepted as bytes by the mock, but rejected by the separate audit.
        report = fixture_report('e','worker',b'not image bytes',1)
        self.assertEqual(report.value,1)
        self.assertEqual(report.payload,b'not image bytes')
        with self.assertRaises(Exception): signal_check(Raster(report.payload,'image/png',(0,0,60,90)),1)
        for line in (self.output/'worker_inputs.jsonl').read_text().splitlines():
            row = json.loads(line)
            self.assertEqual(set(row),{'mode','base_id','condition','reports'})
            for r in row['reports']:
                self.assertEqual(set(r),{'evidence_id','worker_id','artifact_id','fixture_reading','reading_source'})
                self.assertEqual(r['reading_source'],'synthetic_fixture_not_pixels')
        # Registry parameters never contain observation labels or hidden-state/oracle annotations.
        for node in self.provenance:
            self.assertFalse({'y','oracle_posterior','sensor_value','fixture_reading'} & set(node.get('parameters',{})))

    def test_calibration_disjoint_and_recomputable(self):
        frozen = json.loads((self.output/'calibration.json').read_text())
        registry = {n['evidence_id']:n for n in map(json.loads,(self.output/'calibration_provenance.jsonl').read_text().splitlines())}
        evaluation_roots = {r for node in self.provenance for r in node['root_ids']}
        self.assertTrue(set(frozen['root_ids']).isdisjoint(evaluation_roots))
        items = []
        # Preserve generation order so floating-point operation order is identical.
        for eid,node in registry.items():
            if node['modality'] in ('image/png','image/jpeg'):
                ext = '.jpg' if node['modality']=='image/jpeg' else '.png'
                items.append((eid,node['root_ids'][0],(self.output/'calibration_evidence'/(eid+ext)).read_bytes()))
        self.assertEqual(calibrate(items),frozen)
        self.assertTrue(all(p['left'].startswith('cal-') and p['right'].startswith('cal-') for p in frozen['pairs']))
        self.assertGreater(frozen['same_root_pairs'],0)
        self.assertGreater(frozen['independent_pairs'],0)
        with self.assertRaises(ValueError): calibrate([('a','root',render(1).payload)])

    def test_methods_hash_actual_bytes_and_keep_oracle(self):
        for row in self.rows:
            hashes = [sha256((self.output/self.index[eid]['path']).read_bytes()).hexdigest() for eid in row['evidence_ids']]
            self.assertEqual(row['payload_hashes'],hashes)
            if row['method']=='lineage':
                self.assertEqual(row['probability'],row['oracle_posterior'])
                self.assertEqual(row['false_merge_pairs'],0)
                self.assertEqual(row['false_split_pairs'],0)
            if row['condition']=='resized_jpeg' and row['method']=='hash':
                self.assertEqual(len(row['groups']),3)
            if row['condition']=='exact_replay' and row['method']=='hash':
                self.assertEqual(len(row['groups']),1)
        original_config = {k:CONFIG[k] for k in ('seed','instances','prior','q','threshold','workers')}
        _,_,original_truth,cases = generate(original_config)
        truth = json.loads((self.output/'evaluator_truth.json').read_text())['acquisition_values']
        for root,value in original_truth.items(): self.assertEqual(truth[root],value)
        for base in {r['base_id'] for r in self.rows}:
            single = next(r['oracle_posterior'] for r in self.rows if r['base_id']==base and r['condition']=='single_raster')
            self.assertTrue(all(r['oracle_posterior']==single for r in self.rows if r['base_id']==base and r['condition']!='independent_raster'))

    def test_matching_controls_and_cross_modal_limit(self):
        controls = list(map(json.loads,(self.output/'controls.jsonl').read_text().splitlines()))
        for kind in ('similar_independent','identical_independent'):
            rows = {r['method']:r for r in controls if r['condition']==kind}
            self.assertEqual(rows['lineage']['probability'],27/28)
            self.assertEqual(rows['perceptual']['false_merge_pairs'],3 if kind=='identical_independent' else 0)
            self.assertEqual(len(set(rows['hash']['payload_hashes'])),1 if kind=='identical_independent' else 3)
            self.assertEqual(rows['hash']['false_merge_pairs'],3 if kind=='identical_independent' else 0)
            self.assertIsNone(rows['lineage']['y'])
            self.assertIsNone(rows['lineage']['brier'])
        for row in self.rows:
            if row['condition']=='cross_modal' and row['method']=='perceptual':
                self.assertEqual(row['unsupported_modality_pairs'],2)
                self.assertGreaterEqual(len(row['groups']),2)
        self.assertGreater(sum(r['false_split_pairs'] for r in self.rows if r['condition']=='cropped_replay' and r['method']=='perceptual'),0)

    def test_conflicts_and_invalid_ancestry_abstain(self):
        reg = Registry()
        reg.add(Evidence('a',('a',),(),'acquire','image/png'))
        payload = render(1).payload
        reports = [Report('a','w0',payload,1),Report('a','w1',payload,0)]
        self.assertIsNone(estimate('lineage',reports,reg).probability)
        self.assertIsNone(perceptual_estimate(reports,['image/png']*2,0).probability)
        self.assertIsNone(estimate('lineage',[Report('missing','w',payload,1)],reg).probability)
        reg.add(Evidence('b',('b',),(),'acquire','image/png'))
        reg.derive('multi',['a','b'],'summary','image/png',{'mode':'mock'})
        self.assertIsNone(estimate('lineage',[Report('multi','w',payload,1)],reg).probability)

    def test_summary_denominators_and_signal_audit(self):
        self.assertEqual(len(self.rows),240)
        summary = json.loads((self.output/'summary.json').read_text())
        self.assertEqual(len(summary),24)
        for row in summary:
            self.assertEqual(row['n'],10)
            if row['condition']=='single_raster':
                self.assertIsNone(row['false_merge_rate'])
                self.assertIsNone(row['false_split_rate'])
                self.assertIsNone(row['legitimate_approval_retention_rate'])
        for file, count in [('signal_checks.jsonl',144),('calibration_signal_checks.jsonl',48)]:
            checks = list(map(json.loads,(self.output/file).read_text().splitlines()))
            self.assertEqual(len(checks),count)
            self.assertTrue(all(c['passed'] for c in checks))

    def test_deterministic_outputs_and_safe_rerun(self):
        other = Path(self.tmp.name)/'second'
        run(CONFIG,other)
        left = {str(p.relative_to(self.output)):p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        right = {str(p.relative_to(other)):p.read_bytes() for p in other.rglob('*') if p.is_file()}
        self.assertEqual(left,right)
        with self.assertRaises(ValueError): run(CONFIG,other)
        with self.assertRaises(ValueError): validate_settings(CONFIG | {'instances':100})
        with self.assertRaises(ValueError): validate_settings(CONFIG | {'calibration_seed':CONFIG['seed']})

    def test_conflict_grouping_remains_available_for_matching_errors(self):
        reg = Registry()
        payload = render(1).payload
        ids = ['left', 'right']
        for eid in ids:
            reg.add(Evidence(eid,(eid,),(),'acquire','image/png'))
        # Conflicting fixture interpretations of byte-identical independent inputs.
        rows, _ = score('conflict','independent_raster',ids,ids,0,reg,
                        dict.fromkeys(ids,payload),{'left':1,'right':0},
                        dict.fromkeys(ids,1),0,CONFIG,'regression_fixture')
        for method in ('hash','perceptual'):
            row = next(r for r in rows if r['method']==method)
            self.assertIsNone(row['probability'])
            self.assertTrue(row['grouping_valid'])
            self.assertEqual(row['groups'],[[0,1]])
            self.assertEqual(row['false_merge_pairs'],1)
            summary = next(s for s in summarize_results(rows) if s['condition']=='independent_raster' and s['method']==method)
            self.assertEqual(summary['abstentions'],1)
            self.assertEqual(summary['failures'],0)
            self.assertEqual(summary['legitimate_approval_retention_denominator'],1)
            self.assertEqual(summary['legitimate_approval_retention_rate'],0)
            self.assertEqual(summary['false_merge_rate'],1)
            self.assertEqual(summary['mean_oracle_posterior'],.9)

    def test_decoding_failure_is_counted_and_not_scored_as_a_partition(self):
        def exercise():
            reg = Registry()
            reg.add(Evidence('a',('a',),(),'acquire','image/png'))
            return score('failure','exact_replay',['a']*3,['a']*3,0,reg,
                         {'a':b'broken PNG'},{'a':1},{'a':1},0,CONFIG,'regression_fixture')[0]
        rows = exercise()
        self.assertEqual(rows,exercise())
        failed = next(r for r in rows if r['method']=='perceptual')
        self.assertTrue(failed['status'].startswith('failure:'))
        self.assertFalse(failed['approved'])
        self.assertIsNone(failed['false_split_pairs'])
        self.assertIsNone(failed['false_merge_pairs'])
        summary = next(s for s in summarize_results(rows) if s['condition']=='exact_replay' and s['method']=='perceptual')
        self.assertEqual(summary['n'],1)
        self.assertEqual(summary['failures'],1)
        self.assertEqual(summary['abstentions'],0)
        self.assertEqual(summary['probability_coverage'],0)
        self.assertEqual(summary['grouping_unavailable_cases'],1)
        self.assertEqual(summary['attempted_same_root_report_pairs'],3)
        self.assertEqual(summary['same_root_report_pairs'],0)
        self.assertIsNone(summary['false_split_rate'])
        self.assertEqual(summary['premature_approval_denominator'],1)
        self.assertEqual(summary['incorrect_approval_denominator'],1)
        self.assertEqual(summary['mean_oracle_posterior'],.75)
        self.assertIsNone(summary['mean_brier'])
        with self.assertRaisesRegex(ValueError,'one modality'):
            perceptual_estimate([Report('a','w',render(1).payload,1)],[],0)

    def test_abstentions_do_not_select_oracle_mean_or_decision_denominators(self):
        normal = next(r.copy() for r in self.rows if r['condition']=='single_raster' and r['method']=='lineage')
        normal.update(oracle_posterior=.25,oracle_approved=False,y=0,approved=False)
        abstained = dict(normal, probability=None, oracle_posterior=27/28, oracle_approved=True,
                         confidence_inflation=None,absolute_confidence_error=None,brier=None,
                         status='abstain: unknown evidence',grouping_valid=False,
                         groups=[],false_merge_pairs=None,false_split_pairs=None)
        s = next(s for s in summarize_results([normal,abstained]) if s['condition']=='single_raster' and s['method']=='lineage')
        self.assertEqual(s['mean_oracle_posterior'],(.25+27/28)/2)
        self.assertEqual(s['oracle_posterior_denominator'],2)
        self.assertEqual(s['valid_probabilities'],1)
        self.assertEqual(s['probability_coverage'],.5)
        self.assertEqual(s['abstentions'],1)
        self.assertEqual(s['premature_approval_denominator'],1)
        self.assertEqual(s['legitimate_approval_retention_denominator'],1)
        self.assertEqual(s['legitimate_approval_retention_rate'],0)
        self.assertEqual(s['incorrect_approval_denominator'],2)

    def test_failed_generation_leaves_explicit_failed_run_record(self):
        out = Path(self.tmp.name)/'failed-generation'
        with self.assertRaisesRegex(ValueError,'signal preservation'):
            run(CONFIG | {'resize':[32,18]},out)
        state = json.loads((out/'run_status.json').read_text())
        self.assertEqual(state['status'],'failed')
        self.assertEqual(state['error_type'],'ValueError')
        self.assertFalse((out/'summary.json').exists())
        self.assertFalse((out/'manifest.json').exists())
        successful = json.loads((self.output/'run_status.json').read_text())
        self.assertEqual(successful['status'],'complete')
        self.assertEqual(successful['attempted_evaluations'],240)
        self.assertEqual(successful['method_failures'],0)

    def test_worker_inputs_are_unchanged_by_evaluator_labels(self):
        captured = []
        def exercise(y,truth):
            reg = Registry()
            reg.add(Evidence('a',('a',),(),'acquire','image/png'))
            from provenance_pilot import transformations
            original = transformations.fixture_report
            def spy(*args):
                captured.append(args)
                return original(*args)
            with patch.object(transformations,'fixture_report',side_effect=spy):
                return score('boundary','single_raster',['a'],['a'],y,reg,
                             {'a':render(1).payload},{'a':1},truth,0,CONFIG,'regression_fixture')
        first,inputs1 = exercise(0,{'a':0})
        second,inputs2 = exercise(1,{'a':1})
        self.assertEqual(captured[0],captured[1])
        self.assertEqual(inputs1,inputs2)
        self.assertEqual([r['probability'] for r in first],[r['probability'] for r in second])
        self.assertNotEqual(first[0]['oracle_posterior'],second[0]['oracle_posterior'])


if __name__=='__main__': unittest.main()
