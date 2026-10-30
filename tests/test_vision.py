"""Injected fake transports test software only; never reported as live findings."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from provenance_pilot.vision.client import Session, ConfigurationError, BudgetExceeded, validate_config
from provenance_pilot.vision.protocol import extract, aggregate, METHODS, validate_worker
from provenance_pilot.vision.run import run, jsonlines
from provenance_pilot.checkpoint import read_json
from provenance_pilot.core import Evidence, Registry

ROOT=Path(__file__).resolve().parents[1]

def config():
    c=read_json(ROOT/'configs/real-vision.example.json');c['minimum_request_interval_seconds']=.001;c['bootstrap_replicates']=10
    return c

class Fake:
    def __init__(self):self.requests=[]
    def __call__(self,body):
        self.requests.append(body)
        if body['response_format']['json_schema']['name']=='worker_output':
            out={'observation':0,'description':'test response only','abstain':False}
        else:
            reports=json.loads(body['messages'][1]['content'])['reports']
            ids=[r.get('evidence_id',(r.get('evidence_ids') or [None])[0]) for r in reports]
            out={'probability':.4,'citations':ids,'abstain':False}
        return {'http_status':200,'body':json.dumps({'model':'test-only','usage':{'prompt_tokens':100,'completion_tokens':30},
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps(out)}}]})}

class VisionTests(unittest.TestCase):
    def test_free_only_and_quota_latch(self):
        c=config()
        for field,value in [('budget_usd',1),('billing_disabled_confirmed',False),('endpoint','https://api.openai.com/v1/chat/completions'),('worker_model','other')]:
            bad={**c,field:value}
            with self.assertRaises(ConfigurationError):validate_config(bad)
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            def quota(body):calls.append(body);return {'http_status':429,'body':'{"error":"quota"}'}
            session=Session(c,tmp,quota)
            result=extract(session,'one',b'pixels','image/png')
            self.assertEqual(result['status'],'failure: http_429')
            with self.assertRaises(BudgetExceeded):extract(Session(c,tmp,quota),'two',b'pixels','image/png')
            self.assertEqual(len(calls),1)
            self.assertEqual(extract(Session(c,tmp,quota),'one',b'pixels','image/png'),result)

    def test_interrupted_call_never_reissued_and_cache_tampering_rejected(self):
        from provenance_pilot.checkpoint import atomic_json
        with tempfile.TemporaryDirectory() as tmp:
            fake=Fake();session=Session(config(),tmp,fake)
            original=extract(session,'stable',b'pixels','image/png')
            ledger=read_json(Path(tmp)/'ledger.json');key=original['call_id']
            ledger['calls'][key]['status']='reserved';atomic_json(Path(tmp)/'ledger.json',ledger)
            result=extract(Session(config(),tmp,fake),'stable',b'pixels','image/png')
            self.assertEqual(result['status'],'failure: interrupted_request_outcome_unknown')
            self.assertEqual(len(fake.requests),1)
            ledger['calls'][key]['status']='complete';atomic_json(Path(tmp)/'ledger.json',ledger)
            response=read_json(Path(tmp)/(key+'.json'));response['parsed']['observation']=1
            atomic_json(Path(tmp)/(key+'.json'),response)
            with self.assertRaises(ConfigurationError):extract(Session(config(),tmp,fake),'stable',b'pixels','image/png')

    def test_stopped_resume_preserves_attempted_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=Fake();count=0
            def fail_third(body):
                nonlocal count
                count+=1
                return {'http_status':503,'body':'unavailable'} if count==3 else fake(body)
            run(ROOT/'artifacts/transformations',tmp,config(),2,transport=fail_third)
            before=(Path(tmp)/'results.jsonl').read_bytes()
            self.assertEqual(read_json(Path(tmp)/'run_status.json')['attempted_evaluations'],2)
            run(ROOT/'artifacts/transformations',tmp,config(),2,replay_only=True)
            self.assertEqual(before,(Path(tmp)/'results.jsonl').read_bytes())
            self.assertEqual(count,3)

    def test_schema_and_conflict(self):
        for observation in [True,2,'1']:
            self.assertEqual(validate_worker({'status':'received','parsed':{'observation':observation,'description':'x','abstain':False}})[1],'failure: worker_schema')
        r=Registry();r.add(Evidence('a',('a',),(),'acquire','sensor'));r.derive('copy',['a'],'copy','image/png')
        reports=[{'evidence_id':eid,'observation':v,'status':'ok','description':'x'} for eid,v in [('a',0),('copy',1)]]
        with tempfile.TemporaryDirectory() as tmp:
            fake=Fake();s=Session(config(),tmp,fake)
            self.assertTrue(aggregate(s,'x','lineage_llm',reports,r)['status'].startswith('abstain:'))
            self.assertFalse(fake.requests)

    def test_matched_pipeline_replay_and_two_to_ten_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=Fake();c=config();out=Path(tmp)/'run'
            first=run(ROOT/'artifacts/transformations',out,c,1,transport=fake)
            self.assertEqual(first['valid_outputs'],18)
            rows=jsonlines(out/'results.jsonl');before=(out/'results.jsonl').read_bytes();n=len(fake.requests)
            run(ROOT/'artifacts/transformations',out,c,1,replay_only=True)
            self.assertEqual(before,(out/'results.jsonl').read_bytes())
            run(ROOT/'artifacts/transformations',out,c,2,transport=fake)
            after=jsonlines(out/'results.jsonl');self.assertEqual(after[:18],rows)
            self.assertEqual(len(after),36);self.assertEqual(len(fake.requests),2*n)
            for condition in {r['condition'] for r in after}:
                group=[r for r in after if r['condition']==condition and r['base_id']=='b000']
                self.assertEqual(len({tuple(r['worker_call_ids']) for r in group}),1)
            encoded=json.dumps(fake.requests)
            for forbidden in ('fixture_reading','oracle_posterior','expected_observation','evaluation_assignments'):
                self.assertNotIn(forbidden,encoded)
            derived=[r for r in jsonlines(out/'provenance.jsonl') if r['operation']=='model_image_to_structured_record']
            self.assertEqual(len(derived),2)
            for r in derived:self.assertEqual(r['parent_ids'],[r['root_ids'][0]+'-crop'])
            summary=read_json(out/'extraction_summary.json');self.assertGreater(summary['attempted'],0)
            with self.assertRaises(ConfigurationError):run(ROOT/'artifacts/transformations',out,{**c,'bootstrap_seed':999},2,transport=fake)

    def test_evaluator_intervention_cannot_change_requests(self):
        import shutil
        from provenance_pilot.checkpoint import atomic_json,digest
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'source';shutil.copytree(ROOT/'artifacts/transformations',source)
            a=Fake();run(source,tmp/'a',config(),1,transport=a)
            truth=read_json(source/'evaluator_truth.json')
            truth['acquisition_values']={k:1-v for k,v in truth['acquisition_values'].items()}
            for case in truth['evaluation_assignments']:case['y']=1-case['y']
            atomic_json(source/'evaluator_truth.json',truth)
            manifest=read_json(source/'manifest.json');manifest['evaluator_truth.json']=digest((source/'evaluator_truth.json').read_bytes());atomic_json(source/'manifest.json',manifest)
            b=Fake();run(source,tmp/'b',config(),1,transport=b)
            self.assertEqual(a.requests,b.requests)
            self.assertNotEqual(read_json(tmp/'a'/'extraction_summary.json'),read_json(tmp/'b'/'extraction_summary.json'))

    def test_quota_retains_scheduled_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            status=run(ROOT/'artifacts/transformations',tmp,config(),2,transport=lambda b:{'http_status':429,'body':'quota'})
            self.assertEqual(status['status'],'stopped');self.assertEqual(status['scheduled_evaluations'],36)
            self.assertEqual(status['attempted_evaluations'],0);self.assertEqual(status['failures'],36)
            rows=jsonlines(Path(tmp)/'results.jsonl');self.assertTrue(all(not r['grouping_valid'] for r in rows))
            self.assertTrue(all(s['n']==2 for s in read_json(Path(tmp)/'summary.json')))

if __name__=='__main__':unittest.main()
