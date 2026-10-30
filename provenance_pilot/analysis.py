"""Paired cluster-bootstrap diagnostics. No inference about real models."""
import random
from itertools import combinations
from .checkpoint import object_hash
from .transformations import CONDITIONS, METHODS, MODE

METRICS = ('confidence_inflation','absolute_confidence_error','brier',
           'premature_approval','incorrect_approval','legitimate_approval_retention',
           'false_merge_rate','false_split_rate','abstention_rate','failure_rate')


def blocks(rows, conditions=CONDITIONS, methods=METHODS):
    grouped = {}
    for row in rows:
        if row['split'] != 'evaluation':
            raise ValueError('controls must not enter paired evaluation')
        block = grouped.setdefault(row['base_id'],{})
        key = (row['condition'],row['method'])
        if key in block:
            raise ValueError('duplicate evaluation row')
        block[key] = row
    expected = {(c,m) for c in conditions for m in methods}
    if not grouped or any(set(block)!=expected for block in grouped.values()):
        raise ValueError('every base must contain every condition and method')
    return grouped


def resample_blocks(rows, selected_ids):
    grouped = blocks(rows)
    return [row for base in selected_ids for row in grouped[base].values()]


def contribution(row, metric):
    if metric in ('confidence_inflation','absolute_confidence_error','brier'):
        return (row[metric],1) if row[metric] is not None else (0,0)
    if metric == 'premature_approval':
        eligible = not row['oracle_approved']
        return int(eligible and row['approved']),int(eligible)
    if metric == 'incorrect_approval':
        eligible = row['y']==0
        return int(eligible and row['approved']),int(eligible)
    if metric == 'legitimate_approval_retention':
        eligible = row['oracle_approved']
        return int(eligible and row['approved']),int(eligible)
    if metric in ('false_merge_rate','false_split_rate'):
        numerator = row['false_merge_pairs'] if metric=='false_merge_rate' else row['false_split_pairs']
        denominator = row['independent_report_pairs'] if metric=='false_merge_rate' else row['same_root_report_pairs']
        return (numerator,denominator) if row['grouping_valid'] else (0,0)
    return int(row['status'].startswith('abstain:' if metric=='abstention_rate' else 'failure:')),1


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    position = (len(values)-1)*fraction
    lower = int(position)
    upper = min(lower+1,len(values)-1)
    return values[lower]+(position-lower)*(values[upper]-values[lower])


def paired_bootstrap(rows, seed, replicates, conditions=CONDITIONS, methods=METHODS, mode=MODE):
    grouped = blocks(rows, conditions, methods)
    ids = sorted(grouped)
    rng = random.Random(seed)
    # One shared sample of whole base blocks per replicate across ALL contrasts.
    samples = [[rng.randrange(len(ids)) for _ in ids] for _ in range(replicates)]
    contrasts = []
    for condition in conditions:
        for left,right in combinations(methods,2):
            for metric in METRICS:
                values = []
                for base in ids:
                    a = contribution(grouped[base][condition,left],metric)
                    b = contribution(grouped[base][condition,right],metric)
                    # Pairwise complete eligibility: never compare different populations.
                    values.append((a[0],a[1],b[0],b[1]) if a[1] and b[1] else (0,0,0,0))
                def compute(indices):
                    an=ad=bn=bd=0
                    for i in indices:
                        a,d,b,e = values[i]
                        an+=a;ad+=d;bn+=b;bd+=e
                    return (an/ad-bn/bd if ad and bd else None),an,ad,bn,bd
                point,an,ad,bn,bd = compute(range(len(ids)))
                estimates = [compute(sample)[0] for sample in samples]
                valid = [v for v in estimates if v is not None]
                contrasts.append({'mode':mode,'condition':condition,'method_a':left,'method_b':right,
                    'metric':metric,'direction':'A minus B','difference':point,
                    'numerator_a':an,'denominator_a':ad,'numerator_b':bn,'denominator_b':bd,
                    'paired_eligible_bases':sum(v[1]>0 and v[3]>0 for v in values), 'base_instances':len(ids),
                    'ci_lower':percentile(valid,.025),'ci_upper':percentile(valid,.975),
                    'bootstrap_valid_replicates':len(valid),'bootstrap_undefined_replicates':replicates-len(valid),
                    'bootstrap_replicates':replicates})
    design = {'mode':mode,'seed':seed,'replicates':replicates,'unit':'whole base instance',
              'base_ids':ids,'sample_indices_sha256':object_hash(samples),'interval':'95% percentile, linear interpolation',
              'undefined':'exclude undefined replicates; report their count; all undefined => null bounds',
              'population':'paired eligible bases per metric; all attempts retained for decisions/failure rates',
              'interpretation':'Variability of synthetic fixture diagnostics, not real-model performance.'}
    return contrasts,design


def comparison_plot(path, summaries, n):
    colors = ('#ba4d32','#8055a1','#137b72','#3166b1')
    width,height = 1140,650
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#f7f9fc"/><g font-family="sans-serif" fill="#182235">',
           f'<text x="30" y="35" font-size="23">MOCK ONLY | {n} synthetic base instances</text>',
           '<text x="30" y="61" font-size="15">Mean absolute oracle error; no visual extraction or LLM effectiveness claims</text>']
    for k,condition in enumerate(CONDITIONS):
        x=45+(k%3)*370; y=100+(k//3)*245
        svg.append(f'<text x="{x}" y="{y}" font-size="17">{condition}</text>')
        for j,method in enumerate(METHODS):
            value=next(s['mean_absolute_confidence_error'] for s in summaries if s['condition']==condition and s['method']==method)
            bar=0 if value is None else value/.3*150
            bx=x+j*72
            svg.append(f'<rect x="{bx}" y="{y+180-bar}" width="48" height="{max(1,bar)}" fill="{colors[j]}"/>')
            label='undefined' if value is None else f'{value:.3f}'
            svg.append(f'<text x="{bx}" y="{y+170-bar}" font-size="12">{label}</text>')
    for j,method in enumerate(METHODS):
        x=180+j*220
        svg.append(f'<rect x="{x}" y="595" width="16" height="16" fill="{colors[j]}"/><text x="{x+24}" y="609" font-size="16">{method}</text>')
    svg.append('<text x="30" y="637" font-size="12">Shared bar scale: 150 pixels = 0.30 probability error. Pairwise intervals and coverage are in paired_differences.csv.</text></g></svg>')
    path.write_text(''.join(svg))
