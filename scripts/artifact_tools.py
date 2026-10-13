"""Shared, strict file/provenance handling for the two separate pipelines."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(path):
    data = Path(path).read_bytes()
    if Path(path).suffix != '.slx':
        data = data.decode('utf-8-sig').replace('\r\n', '\n').encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def contained(root, relative):
    root = Path(root).resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError(f'Unsafe artifact path: {relative}')
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError(f'Artifact path leaves its root: {relative}')
    return result


def cases(root=ROOT):
    found = sorted((Path(root) / 'experiments').glob('*/config.json'))
    if not found:
        raise ValueError('No experiment configurations found')
    return [(p.parent, read_json(p), read_json(p.parent / 'experiment.json')) for p in found]


def source_fingerprint():
    files = {ROOT / 'requirements.txt', ROOT / 'provenance.json', ROOT / '.gitattributes'}
    for folder, pattern in (('src', '*.py'), ('scripts', '*.py'), ('tests', '*.py'),
                            ('matlab', '*.m'), ('.github/workflows', '*.yml')):
        files.update((ROOT / folder).rglob(pattern))
    for folder, _, _ in cases():
        files.update((folder / 'config.json', folder / 'experiment.json'))
        files.update((folder / 'models').glob('*.slx'))
    return {p.relative_to(ROOT).as_posix(): source_digest(p) for p in sorted(files)}


def verify_bundle(folder, expected_revision=None, expected_run_id=None, expected_attempt=None):
    folder = Path(folder)
    manifest = read_json(folder / 'manifest.json')
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported artifact manifest version')
    for key, expected in (('source_revision', expected_revision), ('run_id', expected_run_id),
                          ('run_attempt', expected_attempt)):
        if expected is not None and str(manifest.get(key)) != str(expected):
            raise ValueError(f'Artifact {key} does not match the requested build')
    if manifest['source_fingerprint'] != source_fingerprint():
        raise ValueError('Artifact and checked-out experiment/master sources differ')
    actual_files = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p != folder / 'manifest.json'}
    if actual_files != set(manifest['files']):
        raise ValueError('Artifact contains missing or unlisted files')
    for relative, expected in manifest['files'].items():
        file = contained(folder, relative)
        if not file.is_file() or digest(file) != expected:
            raise ValueError(f'Missing or modified build artifact: {relative}')
        if relative in manifest['source_fingerprint'] and source_digest(file) != manifest['source_fingerprint'][relative]:
            raise ValueError(f'Artifact input differs from its source revision: {relative}')
    ids = [meta['id'] for _, _, meta in cases(folder)]
    if ids != manifest['experiment_ids'] or ids != [meta['id'] for _, _, meta in cases(ROOT)]:
        raise ValueError('Artifact experiment set differs from its manifest')
    return manifest
