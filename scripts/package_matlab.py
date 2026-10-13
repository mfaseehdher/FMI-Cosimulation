"""Pipeline 1 packages only completed MATLAB outputs, with checksums."""
from __future__ import annotations

import argparse
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from artifact_tools import ROOT, cases, contained, digest, read_json, source_fingerprint, write_json


def package(output):
    environment = read_json(ROOT / 'build' / 'matlab_environment.json')
    experiments = cases()
    ids = [m['id'] for _, _, m in experiments]
    if not environment.get('build_complete') or not environment.get('fmu_exports_requested'):
        raise ValueError('A completed MATLAB build with FMU exports is required')
    if sorted(environment['experiment_ids']) != ids:
        raise ValueError('MATLAB did not build the complete experiment set')
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Bundle output must be empty; choose a fresh output directory')
    output.mkdir(parents=True, exist_ok=True)
    capabilities = {}
    for folder, cfg, meta in experiments:
        status = read_json(folder / 'reference' / 'reference_status.json')
        if status['build_id'] != environment['build_id']:
            raise ValueError(f"{meta['id']}: stale MATLAB reference")
        expected = 'SUCCESS' if meta['matlab_expectation'] == 'success' else 'EXPECTED_ALGEBRAIC_FAILURE'
        if status['status'] != expected:
            raise ValueError(f"{meta['id']}: unexpected MATLAB reference outcome")
        files = [folder / 'config.json', folder / 'experiment.json']
        files.extend((folder / 'models').glob('*.slx'))
        files.append(folder / 'reference' / 'reference_status.json')
        if expected == 'SUCCESS':
            files.extend([folder / 'reference' / 'reference.csv', folder / 'reference' / 'matlab_trace.csv'])
        for spec in cfg['components'].values():
            if spec['type'] != 'fmu':
                continue
            file = contained(folder, spec['file'])
            with zipfile.ZipFile(file) as archive:
                xml = ET.fromstring(archive.read('modelDescription.xml'))
                if not any(n.startswith('binaries/win64/') and n.endswith('.dll') for n in archive.namelist()):
                    raise ValueError(f'{file.name}: Windows 64-bit binary missing')
            cs = xml.find('CoSimulation')
            if xml.get('fmiVersion') != '2.0' or cs is None or cs.get('canGetAndSetFMUstate') not in ('true', '1'):
                raise ValueError(f'{file.name}: FMI 2.0 CS with native state restore is required')
            variables = {v.get('name') for v in xml.findall('./ModelVariables/ScalarVariable')}
            if not {'Bias', 'Feedback', 'Out', 'Gain'} <= variables:
                raise ValueError(f'{file.name}: required adder interface missing')
            capabilities[file.relative_to(ROOT).as_posix()] = {
                'generation_tool': xml.get('generationTool'), 'co_simulation': dict(cs.attrib)}
            files.append(file)
        for file in files:
            destination = output / file.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
    shutil.copy2(ROOT / 'build' / 'matlab_environment.json', output / 'matlab_environment.json')
    manifest = {'schema_version': 1, 'source_revision': os.getenv('GITHUB_SHA', 'local'),
                'run_id': os.getenv('GITHUB_RUN_ID', 'local'),
                'run_attempt': os.getenv('GITHUB_RUN_ATTEMPT', '1'),
                'experiment_ids': ids, 'source_fingerprint': source_fingerprint(),
                'matlab_environment': environment, 'fmu_capabilities': capabilities,
                'files': {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    write_json(output / 'manifest.json', manifest)
    print(f'Packaged {len(ids)} experiments with source/file hashes: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build' / 'matlab_bundle')
    package(parser.parse_args().output_dir)
