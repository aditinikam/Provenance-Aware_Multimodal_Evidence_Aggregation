"""Trusted metadata and model-visible inputs contain no benchmark truth."""
from dataclasses import dataclass, asdict
from fractions import Fraction
from hashlib import sha256
from typing import Protocol
import json


class ProvenanceError(ValueError):
    pass


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    root_ids: tuple[str, ...]
    parent_ids: tuple[str, ...]
    operation: str
    modality: str


class Registry:
    def __init__(self):
        self.nodes: dict[str, Evidence] = {}

    def add(self, node):
        if node.evidence_id in self.nodes:
            raise ProvenanceError('duplicate evidence identifier')
        self.nodes[node.evidence_id] = node
        try:
            self.validate(node.evidence_id)
        except ProvenanceError:
            del self.nodes[node.evidence_id]
            raise
        return node

    def validate(self, evidence_id):
        def visit(key, active):
            if key in active:
                raise ProvenanceError('cycle detected')
            if key not in self.nodes:
                raise ProvenanceError('unknown evidence or parent: ' + key)
            n = self.nodes[key]
            if n.evidence_id != key or not n.root_ids or len(set(n.root_ids)) != len(n.root_ids):
                raise ProvenanceError('invalid identifier or roots')
            if n.operation == 'acquire':
                if n.parent_ids or n.root_ids != (key,):
                    raise ProvenanceError('invalid acquisition')
                return {key}
            if not n.parent_ids:
                raise ProvenanceError('derivation has no parents')
            roots = set()
            for parent in n.parent_ids:
                roots.update(visit(parent, active | {key}))
            if roots != set(n.root_ids):
                raise ProvenanceError('root inheritance mismatch')
            return roots
        return visit(evidence_id, set())

    def derive(self, key, parents, operation, modality):
        if operation == 'acquire':
            raise ProvenanceError('derivation cannot mint acquisition')
        roots = set()
        for parent in parents:
            roots.update(self.validate(parent))
        return self.add(Evidence(key, tuple(sorted(roots)), tuple(parents), operation, modality))

    def export(self):
        return [asdict(n) for n in self.nodes.values()]


def posterior(values, prior=0.5, q=0.75):
    """Exact rational Bayes update; convert only final probability to float."""
    p, reliability = Fraction(str(prior)), Fraction(str(q))
    if not 0 < p < 1 or not Fraction(1, 2) < reliability < 1:
        raise ValueError('require 0<prior<1 and 0.5<q<1')
    odds = p / (1 - p)
    ratio = reliability / (1 - reliability)
    for value in values:
        if type(value) is not int or value not in (0, 1):
            raise ValueError('reading must be binary integer')
        odds *= ratio if value else 1 / ratio
    return float(odds / (1 + odds))


def oracle(acquisition_ids, truth_values, prior=0.5, q=0.75):
    """Evaluator-only API; acquisitions come from the experimental assignment."""
    return posterior([truth_values[k] for k in sorted(set(acquisition_ids))], prior, q)


def record(value):
    return json.dumps({'sensor_value': value}, sort_keys=True).encode()


@dataclass(frozen=True)
class Report:
    evidence_id: str
    worker_id: str
    payload: bytes
    value: int


class WorkerBackend(Protocol):
    def report(self, evidence_id: str, worker_id: str, payload: bytes) -> Report: ...


class MockWorker:
    """Reads a structured record, never pixels, truth, roots, or oracle answers."""
    def report(self, evidence_id, worker_id, payload):
        obj = json.loads(payload)
        value = obj['sensor_value']
        if type(value) is not int or value not in (0, 1):
            raise ValueError('malformed sensor record')
        return Report(evidence_id, worker_id, payload, value)


@dataclass
class Estimate:
    probability: float | None
    groups: list[list[int]]
    status: str = 'ok'


METHODS = ('naive', 'hash', 'lineage')


def estimate(method, reports, registry=None, prior=0.5, q=0.75):
    """Only lineage receives trusted metadata. No method receives evaluator truth."""
    if method not in METHODS:
        raise ValueError('unknown method')
    groups = {}
    try:
        for i, report in enumerate(reports):
            if method == 'naive':
                key = i
            elif method == 'hash':
                key = sha256(report.payload).hexdigest()
            else:
                if registry is None:
                    raise ProvenanceError('missing registry')
                roots = registry.validate(report.evidence_id)
                if len(roots) != 1:
                    raise ProvenanceError('multi-root evidence needs a dependence model')
                key = next(iter(roots))
            groups.setdefault(key, []).append(i)
        values = []
        for group in groups.values():
            claims = {reports[i].value for i in group}
            if len(claims) != 1:
                raise ProvenanceError('conflicting interpretations require reconciliation')
            values.append(claims.pop())
        return Estimate(posterior(values, prior, q), list(groups.values()))
    except ProvenanceError as exc:
        return Estimate(None, [], 'abstain: ' + str(exc))


def approve(probability, threshold=0.90):
    return probability is not None and probability >= threshold
