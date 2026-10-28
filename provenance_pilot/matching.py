"""Offline pixel-similarity fixture. No ancestry, claims, or oracle input at inference."""
from itertools import combinations
from .imaging import decode
from .core import Estimate, posterior


def feature(payload):
    # Full-frame color thumbnail; intentionally not a semantic or cross-modal matcher.
    from PIL import Image
    try:
        image = decode(payload).resize((16,16), Image.Resampling.BILINEAR)
    except OSError as exc:
        # Pillow's error may contain a BytesIO memory address; keep failure rows stable.
        raise ValueError('raster payload cannot be decoded') from exc
    return tuple(component/255 for pixel in image.get_flattened_data() for component in pixel)


def distance(a, b):
    return sum(abs(x-y) for x,y in zip(a,b)) / len(a)


def calibrate(items):
    """Calibration-only (id, root, bytes) tuples. Balanced pair error, low-threshold ties."""
    features = [feature(payload) for _,_,payload in items]
    pairs = [{'left': items[i][0], 'right': items[j][0],
              'same_root': items[i][1] == items[j][1], 'distance': distance(features[i], features[j])}
             for i,j in combinations(range(len(items)),2)]
    positives = sum(p['same_root'] for p in pairs)
    negatives = len(pairs)-positives
    if not positives or not negatives:
        raise ValueError('calibration requires both same-root and independent pairs')
    candidates = sorted({-1.0, *(p['distance'] for p in pairs)})
    scores = []
    for threshold in candidates:
        fn = sum(p['same_root'] and p['distance'] > threshold for p in pairs)
        fp = sum(not p['same_root'] and p['distance'] <= threshold for p in pairs)
        scores.append((.5*(fn/positives+fp/negatives),threshold,fn,fp))
    loss, threshold, fn, fp = min(scores)
    return {'mode': 'mock_software_diagnostic', 'threshold': threshold, 'objective': 'balanced pair error; smallest threshold breaks ties',
            'balanced_error': loss, 'false_splits': fn, 'same_root_pairs': positives,
            'false_merges': fp, 'independent_pairs': negatives,
            'root_ids': sorted({root for _,root,_ in items}), 'pairs': pairs,
            'feature': '16x16 full-frame RGB mean absolute distance, range 0..1'}


def perceptual_estimate(reports, modalities, threshold, prior=.5, q=.75):
    if len(reports) != len(modalities):
        raise ValueError('one modality is required per report')
    features = [feature(r.payload) if m in ('image/png','image/jpeg') else None for r,m in zip(reports,modalities)]
    groups = [{i} for i in range(len(reports))]
    for i,j in combinations(range(len(reports)),2):
        # Unsupported modalities remain separate, even if their JSON bytes match.
        if features[i] is not None and features[j] is not None and distance(features[i],features[j]) <= threshold:
            a = next(g for g in groups if i in g)
            b = next(g for g in groups if j in g)
            if a is not b:
                a.update(b)
                groups.remove(b)
    groups = sorted([sorted(g) for g in groups], key=lambda g:g[0])
    values = [{reports[i].value for i in group} for group in groups]
    if any(len(v) != 1 for v in values):
        return Estimate(None, groups, 'abstain: conflicting interpretations require reconciliation')
    return Estimate(posterior([next(iter(v)) for v in values],prior,q), groups)
