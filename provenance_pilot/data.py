"""Paired assignments and separate evaluator-only annotations."""
import random
from .core import Evidence, Registry, MockWorker, record


def generate(config):
    rng = random.Random(config['seed'])
    n = config['instances']
    # Stratified balanced fixture; each item has marginal prior 1/2.
    states = [0] * (n // 2) + [1] * (n // 2)
    if n % 2:
        states.append(rng.randrange(2))  # Seeded extra label; imbalance is at most one.
    rng.shuffle(states)
    registry, payloads, truth, cases = Registry(), {}, {}, []
    worker = MockWorker()
    for i, y in enumerate(states):
        base = f'b{i:03d}'
        roots = []
        for j in range(3):
            root = f'{base}-a{j}'
            value = y if rng.random() < config['q'] else 1 - y
            roots.append(root)
            truth[root] = value
            registry.add(Evidence(root, (root,), (), 'acquire', 'sensor'))
            for suffix, modality in [('record', 'application/json'), ('card', 'image/svg+xml')]:
                registry.derive(f'{root}-{suffix}', [root], 'render', modality)
            payloads[f'{root}-record'] = record(value)
            payloads[f'{root}-card'] = card(value)
        for condition, acquisitions in [('single', roots[:1]), ('replay', [roots[0]] * 3), ('independent', roots)]:
            reports = []
            for j, root in enumerate(acquisitions):
                eid = f'{base}-{condition}-r{j}'
                registry.derive(eid, [root + '-record'], 'route', 'application/json')
                payload = payloads[root + '-record']
                payloads[eid] = payload
                reports.append(worker.report(eid, f'worker-{j}', payload))
            cases.append({'base_id': base, 'condition': condition, 'reports': reports,
                          'acquisitions': acquisitions, 'y': y})
    return registry, payloads, truth, cases


def card(value):
    color = '#116466' if value else '#9d423b'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">'
            f'<rect width="320" height="180" rx="12" fill="#f1f5f9"/>'
            f'<text x="24" y="38" font-family="sans-serif" font-size="18">SYNTHETIC SENSOR</text>'
            f'<rect x="24" y="60" width="272" height="94" rx="8" fill="{color}"/>'
            f'<text x="160" y="125" text-anchor="middle" font-family="sans-serif" font-size="54" fill="white">{value}</text></svg>').encode()
