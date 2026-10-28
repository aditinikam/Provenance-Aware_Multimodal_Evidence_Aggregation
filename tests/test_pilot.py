import json
import tempfile
import unittest
from pathlib import Path
from provenance_pilot.core import Evidence, Registry, ProvenanceError, MockWorker, record, posterior, oracle, estimate, approve, Report
from provenance_pilot.data import generate
from provenance_pilot.run import run, summarize, validate_config

CONFIG = {'seed': 562, 'instances': 10, 'prior': .5, 'q': .75, 'threshold': .9, 'workers': 3}


class PilotTests(unittest.TestCase):
    def test_hand_calculated_oracle(self):
        self.assertEqual(posterior([1]), .75)
        self.assertEqual(posterior([1, 1, 1]), 27/28)
        self.assertEqual(posterior([0, 0, 0]), 1/28)
        self.assertEqual(posterior([1, 0]), .5)
        self.assertEqual(posterior([]), .5)
        self.assertEqual(oracle(['a']*3, {'a': 1}), .75)
        self.assertEqual(oracle(['a','b','c'], dict(a=1,b=1,c=1)), 27/28)

    def test_paired_conditions_and_routing(self):
        registry, payloads, truth, cases = generate(CONFIG)
        self.assertEqual(sum(c['y'] for c in cases[::3]), 5)
        for start in range(0, len(cases), 3):
            single, replay, independent = cases[start:start+3]
            self.assertEqual(single['acquisitions'][0], independent['acquisitions'][0])
            self.assertEqual(replay['acquisitions'], single['acquisitions']*3)
            self.assertEqual(len(set(independent['acquisitions'])), 3)
            self.assertEqual(oracle(single['acquisitions'], truth), oracle(replay['acquisitions'], truth))
            self.assertEqual(len({r.payload for r in replay['reports']}), 1)
            for c in (single, replay, independent):
                for r, root in zip(c['reports'], c['acquisitions']):
                    self.assertEqual(registry.validate(r.evidence_id), {root})
                    self.assertEqual(r.value, truth[root])
                    self.assertEqual(payloads[root+'-record'], record(r.value))
        self.assertEqual(sum(n.operation == 'acquire' for n in registry.nodes.values()), 30)

    def test_independent_identical_payloads(self):
        reg = Registry()
        reports = []
        for key in ('a','b','c'):
            reg.add(Evidence(key,(key,),(),'acquire','json'))
            reports.append(MockWorker().report(key,key,record(1)))
        self.assertEqual(estimate('hash',reports).probability,.75)
        self.assertEqual(estimate('lineage',reports,reg).probability,27/28)
        self.assertEqual(len(estimate('hash',reports).groups),1)
        self.assertEqual(len(estimate('lineage',reports,reg).groups),3)

    def test_invalid_ancestry_and_cycles(self):
        reg = Registry()
        reg.add(Evidence('a',('a',),(),'acquire','json'))
        bad = [Evidence('b',('b',),('a',),'route','json'),
               Evidence('b',('a',),('missing',),'route','json'),
               Evidence('b',('a',),(),'route','json'),
               Evidence('b',('b',),('a',),'acquire','json')]
        for node in bad:
            with self.assertRaises(ProvenanceError): reg.add(node)
        reg.nodes['b'] = Evidence('b',('a',),('c',),'route','json')
        reg.nodes['c'] = Evidence('c',('a',),('b',),'route','json')
        with self.assertRaisesRegex(ProvenanceError,'cycle'): reg.validate('b')
        for key in ('missing','b'):
            result = estimate('lineage',[MockWorker().report(key,'w',record(1))],reg)
            self.assertIsNone(result.probability)
            self.assertFalse(approve(result.probability))

    def test_derivation_and_multiroot_abstention(self):
        reg = Registry()
        for key in ('a','b'): reg.add(Evidence(key,(key,),(),'acquire','sensor'))
        reg.derive('image',['a'],'render','image/svg+xml')
        reg.derive('caption',['image'],'caption','text/plain')
        self.assertEqual(reg.validate('caption'),{'a'})
        reg.derive('summary',['caption','b'],'summarize','text/plain')
        self.assertEqual(reg.validate('summary'),{'a','b'})
        self.assertIsNone(estimate('lineage',[MockWorker().report('summary','w',record(1))],reg).probability)

    def test_conflict_abstains(self):
        reg = Registry()
        reg.add(Evidence('a',('a',),(),'acquire','json'))
        reports = [Report('a','w',record(v),v) for v in (0,1)]
        self.assertIsNone(estimate('lineage',reports,reg).probability)

    def test_reproducibility_and_no_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b = Path(tmp)/'a',Path(tmp)/'b'
            rows = run(CONFIG,a)
            run(CONFIG,b)
            left = {str(p.relative_to(a)):p.read_bytes() for p in a.rglob('*') if p.is_file()}
            right = {str(p.relative_to(b)):p.read_bytes() for p in b.rglob('*') if p.is_file()}
            self.assertEqual(left,right)
            for line in (a/'worker_inputs.jsonl').read_text().splitlines():
                item=json.loads(line)
                self.assertEqual(set(item),{'base_id','condition','reports'})
                for report in item['reports']:
                    self.assertEqual(set(report),{'evidence_id','worker_id','payload'})
                    self.assertEqual(set(json.loads(report['payload'])),{'sensor_value'})
            self.assertTrue(all(r['probability']==r['oracle_posterior'] for r in rows if r['method']=='lineage'))
            for s in summarize(rows):
                if s['condition']=='single':
                    self.assertIsNone(s['legitimate_approval_retention_rate'])
                    self.assertEqual(s['legitimate_approval_retention_denominator'],0)
            for row in rows:
                if row['method']=='hash' and row['condition']=='independent':
                    self.assertGreaterEqual(row['false_merge_pairs'],1)

    def test_gate_and_config(self):
        self.assertTrue(approve(.90))
        self.assertFalse(approve(.8999))
        self.assertFalse(approve(None))
        for patch in ({'instances':9},{'q':1},{'workers':4},{'prior':.4}):
            with self.assertRaises(ValueError): validate_config(CONFIG | patch)


if __name__ == '__main__': unittest.main()
