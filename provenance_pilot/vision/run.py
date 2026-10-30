"""Opt-in real vision pilot on synthetic stimuli; evaluator labels stay local."""
import argparse
import csv
import io
import json
from itertools import combinations
from pathlib import Path
from ..checkpoint import atomic_bytes, atomic_json, canonical, digest, object_hash, read_json, source_snapshot, verify_tree, lock
from ..core import Evidence, Registry, oracle, approve
from ..run import summarize
from ..transformations import CONDITIONS
from ..analysis import paired_bootstrap
from .client import Session, BudgetExceeded, ConfigurationError
from .protocol import METHODS, extract, aggregate

MODE='real_gemini_responses_on_synthetic_sensor_images'


def jsonlines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def write_lines(path, rows):
    atomic_bytes(path,b''.join(canonical(r) for r in rows))


def write_csv(path, rows):
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows);atomic_bytes(path,stream.getvalue().encode())


def load_source(source):
    source=Path(source)
    manifest=read_json(source/'manifest.json');verify_tree(source,manifest)
    registry=Registry()
    for row in jsonlines(source/'provenance.jsonl'):
        registry.nodes[row['evidence_id']]=Evidence(row['evidence_id'],tuple(row['root_ids']),tuple(row['parent_ids']),row['operation'],row['modality'],row.get('parameters',{}))
    for eid in registry.nodes: registry.validate(eid)
    index={r['evidence_id']:r for r in jsonlines(source/'artifacts.jsonl')}
    payloads={eid:(source/item['path']).read_bytes() for eid,item in index.items()}
    if any(digest(payloads[eid])!=item['sha256'] for eid,item in index.items()):
        raise ConfigurationError('source artifact hash mismatch')
    # Deliberately allowlist routing fields; fixture readings cannot cross this boundary.
    jobs=[{'base_id':r['base_id'],'condition':r['condition'],
           'artifact_ids':[x['artifact_id'] for x in r['reports']]} for r in jsonlines(source/'worker_inputs.jsonl') if r['base_id']!='control']
    return registry,index,payloads,jobs,object_hash(manifest)


def evaluate(result,job,reports,truth):
    """Evaluator-only boundary. Never used in constructing model requests."""
    assignment=next(r for r in truth['evaluation_assignments'] if r['base_id']==job['base_id'] and r['condition']==job['condition'])
    roots=assignment['acquisitions'];reference=oracle(roots,truth['acquisition_values']);p=result['probability'];y=assignment['y']
    pairs=set(combinations(range(len(roots)),2));independent={pair for pair in pairs if roots[pair[0]]!=roots[pair[1]]};shared=pairs-independent
    # LLM citations do not define a grouping. Only trusted preprocessing has a known partition.
    grouping=(job['method']=='lineage_llm' and len(reports)==len(roots) and
              not result['status'].startswith('failure:') and 'unknown' not in result['status'])
    return {'mode':MODE,'split':'evaluation',**job,**result,'report_ids':[r['evidence_id'] for r in reports],
        'worker_call_ids':[r.get('call_id') for r in reports], 'payload_hashes':[r['payload_sha256'] for r in reports],
        'oracle_posterior':reference,'y':y,'approved':approve(p,.9),'oracle_approved':approve(reference,.9),
        'premature_approval':approve(p,.9) and not approve(reference,.9),'incorrect_approval':approve(p,.9) and y==0,
        'confidence_inflation':p-reference if p is not None else None,'absolute_confidence_error':abs(p-reference) if p is not None else None,
        'brier':(p-y)**2 if p is not None else None,'grouping_valid':grouping,
        'false_merge_pairs':0 if grouping else None,'false_split_pairs':0 if grouping else None,
        'independent_report_pairs':len(independent),'same_root_report_pairs':len(shared)}


def summarize_real(rows):
    summaries=summarize(rows,CONDITIONS,METHODS)
    for s in summaries:
        sub=[r for r in rows if r['condition']==s['condition'] and r['method']==s['method']]
        s.update(mode=MODE,abstentions=sum(r['status'].startswith('abstain:') for r in sub),
                 failures=sum(r['status'].startswith('failure:') for r in sub),
                 not_attempted=sum(not r['attempted'] for r in sub),oracle_posterior_denominator=len(sub))
        for metric in ('probability','confidence_inflation','absolute_confidence_error','brier'):
            vals=[r[metric] for r in sub if r[metric] is not None]
            s[metric+'_numerator']=sum(vals);s[metric+'_denominator']=len(vals)
        grouped=[r for r in sub if r['grouping_valid']]
        s['grouping_valid_cases']=len(grouped);s['grouping_unavailable_cases']=len(sub)-len(grouped)
        s['false_split_pairs']=sum(r['false_split_pairs'] for r in grouped)
        s['same_root_report_pairs']=sum(r['same_root_report_pairs'] for r in grouped)
        s['false_split_rate']=s['false_split_pairs']/s['same_root_report_pairs'] if s['same_root_report_pairs'] else None
    return summaries


def export(output,rows,workers,registry,truth,config,status):
    write_lines(output/'results.jsonl',rows);write_lines(output/'worker_reports.jsonl',workers.values());write_lines(output/'provenance.jsonl',registry.export())
    summaries=summarize_real(rows);atomic_json(output/'summary.json',summaries);write_csv(output/'summary.csv',summaries)
    extraction=[]
    for report in workers.values():
        roots=registry.validate(report['evidence_id']);root=next(iter(roots));expected=truth['acquisition_values'][root]
        extraction.append({'call_id':report['call_id'],'evidence_id':report['evidence_id'],'root_id':root,'expected_observation':expected,
            'observed':report['observation'],'status':report['status'],'correct':report['observation']==expected if report['status']=='ok' else None})
    write_lines(output/'extraction_evaluation.jsonl',extraction)
    valid=[r for r in extraction if r['correct'] is not None];correct=sum(r['correct'] for r in valid)
    atomic_json(output/'extraction_summary.json',{'mode':MODE,'attempted':len(extraction),'resolved':len(valid),'correct':correct,
        'accuracy_resolved':correct/len(valid) if valid else None,'accuracy_all_attempts':correct/len(extraction) if extraction else None,
        'unresolved':len(extraction)-len(valid),'unit':'unique cached extraction call; repeated calls are not independent base instances'})
    differences,design=paired_bootstrap(rows,config['bootstrap_seed'],config['bootstrap_replicates'],methods=METHODS,mode=MODE)
    design['interpretation']='Exploratory variability across synthetic base instances with cached real model responses; not general real-world performance or model-sampling uncertainty.'
    atomic_json(output/'bootstrap.json',design);atomic_json(output/'paired_differences.json',differences);write_csv(output/'paired_differences.csv',differences)
    atomic_json(output/'run_status.json',status)
    # Simple fixed-scale SVG, including undefined values explicitly.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="590"><rect width="100%" height="100%" fill="white"/><g font-family="sans-serif" fill="#162538"><text x="25" y="30" font-size="20">Real Gemini responses | synthetic sensor stimuli | exploratory pilot</text>']
    for i,s in enumerate(summaries):
        x=25+(i//3%3)*330;y=75+(i//9)*240+(i%3)*58;value=s['mean_absolute_confidence_error'];label='undefined' if value is None else f'{value:.4f}'
        if i%3==0:svg.append(f'<text x="{x}" y="{y-12}">{s["condition"]}</text>')
        svg.append(f'<text x="{x}" y="{y+7}" font-size="12">{s["method"]}: {label} (valid {s["valid_probabilities"]}/{s["n"]})</text>')
        svg.append(f'<rect x="{x}" y="{y+15}" width="{(value or 0)*280}" height="15" fill="#247b90"/>')
    svg.append('<text x="25" y="560" font-size="13">Mean absolute oracle error; bar scale 280 px = 1.0. Failures remain in decision denominators.</text></g></svg>')
    atomic_bytes(output/'comparison.svg',''.join(svg).encode())


def run(source,output,config,instances=2,replay_only=False,transport=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with lock(output):
        registry,index,payloads,jobs,source_id=load_source(source)
        bases=sorted({j['base_id'] for j in jobs})
        if instances<1 or instances>len(bases):raise ConfigurationError('requested instance count exceeds source dataset')
        identity={'config':config,'source_manifest_sha256':source_id,'protocol_revision':2}
        path=output/'resolved_config.json'
        if path.exists() and read_json(path)!=identity:raise ConfigurationError('incompatible source or configuration')
        if not path.exists():
            atomic_json(path,identity);atomic_json(output/'code_revision.json',source_snapshot())
        elif read_json(output/'code_revision.json')['source_digest']!=source_snapshot()['source_digest']:
            raise ConfigurationError('source code changed since this run; use a new output directory')
        jobs=[j for j in jobs if j['base_id'] in bases[:instances]]
        session=Session(config,output/'cache',transport,replay_only)
        # Truth is only passed to evaluator functions, never extract/aggregate.
        truth=read_json(Path(source)/'evaluator_truth.json')
        checkpoint=read_json(output/'progress.json') if (output/'progress.json').exists() else {'rows':[],'sha256':object_hash([])}
        if object_hash(checkpoint['rows'])!=checkpoint['sha256']:
            raise ConfigurationError('result checkpoint integrity mismatch')
        prior_rows={(r['base_id'],r['condition'],r['method']):r for r in checkpoint['rows']}
        atomic_json(output/'run_status.json',{'mode':MODE,'status':'running','instances':instances,'scheduled_evaluations':len(jobs)*len(METHODS)})
        rows=[];workers={};stop=None
        for job in jobs:
            reports=[]
            for i,original in enumerate(job['artifact_ids']):
                synthetic=original.endswith('-synthetic-record')
                parent=original.replace('-synthetic-record','-crop') if synthetic else original
                eid=original.replace('-synthetic-record','-model-record') if synthetic else parent
                # Same artifact/worker cache across conditions and methods. Distinct worker indices get independent calls.
                logical='derive:'+eid if synthetic else f'extract:{parent}:worker{i}'
                if logical not in workers:
                    try:
                        report=extract(session,logical,payloads[parent],index[parent]['modality'])
                        if synthetic:
                            registry.derive(eid,[parent],'model_image_to_structured_record','application/json',{'model':config['worker_model'],'call_id':report['call_id']})
                            payloads[eid]=canonical(report);atomic_bytes(output/'evidence'/(eid+'.json'),payloads[eid])
                        report.update(evidence_id=eid,payload_sha256=digest(payloads[eid]),image_parent_id=parent)
                        workers[logical]=report
                        if session.ledger.get('stopped_reason'):stop=session.ledger['stopped_reason']
                    except BudgetExceeded as exc:stop=str(exc)
                if logical in workers:reports.append(workers[logical])
            for method in METHODS:
                attempted=False
                previous=prior_rows.get((job['base_id'],job['condition'],method))
                if previous and previous.get('attempted'):
                    result={k:previous[k] for k in ('probability','citations','status','call_id')};attempted=True
                elif stop is None:
                    try:
                        result=aggregate(session,f'{job["base_id"]}:{job["condition"]}:{method}',method,reports,registry);attempted=True
                        if session.ledger.get('stopped_reason'):stop=session.ledger['stopped_reason']
                    except BudgetExceeded as exc:
                        stop=str(exc);result={'probability':None,'citations':[],'status':'failure: stopped_before_request','call_id':None}
                else:result={'probability':None,'citations':[],'status':'failure: not_attempted_after_stop','call_id':None}
                row=evaluate(result,{**job,'method':method},reports,truth);row['attempted']=attempted
                rows.append(row)
            atomic_json(output/'progress.json',{'rows':rows,'sha256':object_hash(rows)})
        status={'mode':MODE,'status':'stopped' if stop else 'complete','stop_reason':stop,'instances':instances,
                'scheduled_evaluations':len(jobs)*len(METHODS),'attempted_evaluations':sum(r['attempted'] for r in rows),
                'valid_outputs':sum(r['probability'] is not None for r in rows),'failures':sum(r['status'].startswith('failure:') for r in rows),
                'spending_cap_usd':0,'billing_disabled_user_confirmed':True,'paid_fallback':False}
        export(output,rows,workers,registry,truth,config,status)
        atomic_json(output/'evidence_index.json',[{'evidence_id':eid,'sha256':digest(data),'source_path':str(Path(source)/index[eid]['path']) if eid in index else 'evidence/'+eid+'.json'} for eid,data in payloads.items() if eid in {r['evidence_id'] for r in workers.values()}])
        for name in ('contact_sheet.png','controls_contact_sheet.png'):
            atomic_bytes(output/name,(Path(source)/name).read_bytes())
        atomic_json(output/'manifest.json',{str(p.relative_to(output)):digest(p.read_bytes()) for p in output.rglob('*') if p.is_file() and p.name not in ('.lock','manifest.json')})
        return status


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',default='artifacts/transformations');parser.add_argument('--output',required=True)
    parser.add_argument('--config',default='configs/real-vision.example.json');parser.add_argument('--instances',type=int,default=2);parser.add_argument('--replay-only',action='store_true')
    args=parser.parse_args()
    try:
        result=run(args.source,args.output,read_json(args.config),args.instances,args.replay_only)
    except BaseException as exc:
        path=Path(args.output)/'run_status.json'
        if path.exists() and read_json(path).get('status')=='running':
            state=read_json(path);state.update(status='failed',error_type=type(exc).__name__,detail='Execution interrupted or raised; retain cache and checkpoint for review.')
            atomic_json(path,state)
        raise
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
