"""Atomic, checksummed checkpoints for local offline runs (POSIX file locking)."""
import hashlib
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


class CompatibilityError(ValueError):
    pass


class RunInterrupted(KeyboardInterrupt):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def object_hash(value):
    return digest(canonical(value))


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path, value):
    atomic_bytes(path, canonical(value))


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise CompatibilityError(f'missing or malformed state: {path}') from exc


@contextmanager
def lock(output):
    import fcntl
    with (Path(output)/'.lock').open('a+b') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CompatibilityError('another process owns this run') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def source_snapshot():
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root/'provenance_pilot').rglob('*.py')) + [root/'pyproject.toml', root/'docs/benchmark-design.md']
    hashes = {str(p.relative_to(root)):digest(p.read_bytes()) for p in paths if p.exists()}
    def git(*args):
        try:
            return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    status = git('status','--porcelain','--untracked-files=normal')
    return {'revision':git('rev-parse','HEAD'), 'branch':git('branch','--show-current'),
            'dirty':bool(status) if status is not None else None, 'working_tree_status':status,
            'source_hashes':hashes, 'source_digest':object_hash(hashes)}


def verify_tree(root, manifest):
    root = Path(root)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='manifest.json'}
    if actual != set(manifest):
        raise CompatibilityError(f'artifact inventory mismatch: {root}')
    for name, expected in manifest.items():
        if digest((root/name).read_bytes()) != expected:
            raise CompatibilityError(f'artifact hash mismatch: {root/name}')


class Checkpoints:
    def __init__(self, output, config_id):
        self.output = Path(output)
        self.config_id = config_id
        self.path = self.output/'progress.json'
        self.progress = read_json(self.path) if self.path.exists() else {'config_id':config_id,'chunks':{}}
        if self.progress['config_id'] != config_id:
            raise CompatibilityError('checkpoint configuration mismatch')
        for key, checksum in self.progress['chunks'].items():
            path = self.output/'checkpoints'/f'{key}.json'
            if not path.is_file() or digest(path.read_bytes()) != checksum:
                raise CompatibilityError(f'checkpoint mismatch: {key}')
            self._read(key)

    def _read(self, key):
        entry = read_json(self.output/'checkpoints'/f'{key}.json')
        if entry['config_id'] != self.config_id or entry['key'] != key:
            raise CompatibilityError(f'checkpoint identity mismatch: {key}')
        for checksum in entry['assets']:
            path = self.output/'checkpoint_assets'/checksum
            if not path.is_file() or digest(path.read_bytes()) != checksum:
                raise CompatibilityError(f'checkpoint evidence mismatch: {checksum}')
        return entry

    def get(self, key, input_hash):
        if key not in self.progress['chunks']:
            return None
        entry = self._read(key)
        if entry['input_hash'] != input_hash:
            raise CompatibilityError(f'checkpoint input mismatch: {key}')
        return entry

    def put(self, key, input_hash, rows, inputs, payloads):
        if key in self.progress['chunks']:
            raise CompatibilityError(f'duplicate checkpoint: {key}')
        assets = sorted({digest(payload) for payload in payloads})
        for payload in payloads:
            path = self.output/'checkpoint_assets'/digest(payload)
            if path.exists() and path.read_bytes()!=payload:
                raise CompatibilityError('existing evidence asset mismatch')
            if not path.exists():
                atomic_bytes(path,payload)
        entry = {'key':key,'config_id':self.config_id,'input_hash':input_hash,
                 'rows':rows,'worker_inputs':inputs,'assets':assets}
        path = self.output/'checkpoints'/f'{key}.json'
        atomic_json(path,entry)
        # This index is the commit point. Orphan files from a hard interruption are uncommitted.
        self.progress['chunks'][key] = digest(path.read_bytes())
        atomic_json(self.path,self.progress)
