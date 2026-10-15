"""Audit existing registration artifacts without changing experiment outputs.

Requires NumPy. Validates saved transforms against every corresponding point;
does not claim ICP convergence or anatomical alignment from matrix validity.
"""
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np


def unlzf(data, expected):
    output = bytearray()
    index = 0
    while index < len(data):
        control = data[index]
        index += 1
        if control < 32:
            length = control + 1
            output.extend(data[index:index+length])
            index += length
        else:
            length = control >> 5
            offset = (control & 31) << 8
            if length == 7:
                length += data[index]
                index += 1
            offset += data[index] + 1
            index += 1
            for _ in range(length + 2):
                output.append(output[-offset])
    if len(output) != expected:
        raise ValueError('invalid LZF decompressed length')
    return output


def xyz(path):
    with path.open('rb') as stream:
        header = {}
        while True:
            line = stream.readline()
            if not line:
                raise ValueError('missing DATA header')
            parts = line.decode('ascii').strip().split()
            if not parts or parts[0].startswith('#'):
                continue
            header[parts[0]] = parts[1:]
            if parts[0] == 'DATA':
                break
        fields = header['FIELDS']
        if header['DATA'] == ['ascii']:
            values = np.loadtxt(stream, ndmin=2)
            counts = list(map(int, header.get('COUNT', ['1'] * len(fields))))
            offsets = np.cumsum([0] + counts[:-1])
            result = values[:, [offsets[fields.index(f)] for f in ('x', 'y', 'z')]]
        elif header['DATA'] == ['binary']:
            counts = list(map(int, header.get('COUNT', ['1'] * len(fields))))
            formats = []
            for typ, size, count in zip(header['TYPE'], header['SIZE'], counts):
                scalar = {'F': 'f', 'U': 'u', 'I': 'i'}[typ] + size
                formats.append((scalar, (count,)) if count != 1 else scalar)
            values = np.frombuffer(stream.read(), dtype=np.dtype({'names': fields, 'formats': formats}))
            result = np.column_stack([values[f] for f in ('x', 'y', 'z')])
        elif header['DATA'] == ['binary_compressed']:
            compressed, uncompressed = struct.unpack('<II', stream.read(8))
            payload = unlzf(stream.read(compressed), uncompressed)
            count = int(header['POINTS'][0])
            sizes = list(map(int, header['SIZE']))
            counts = list(map(int, header.get('COUNT', ['1'] * len(fields))))
            offset = 0
            columns = {}
            for field, size, repeat, typ in zip(fields, sizes, counts, header['TYPE']):
                if field in ('x', 'y', 'z'):
                    columns[field] = np.frombuffer(payload, dtype='<'+{'F':'f', 'U':'u', 'I':'i'}[typ]+str(size), count=count, offset=offset)
                offset += count * size * repeat
            result = np.column_stack([columns[f] for f in ('x', 'y', 'z')])
        else:
            raise ValueError('unsupported compressed PCD')
        if len(result) != int(header['POINTS'][0]) or not len(result):
            raise ValueError('empty cloud or point count mismatch')
        if not np.isfinite(result).all():
            raise ValueError('nonfinite coordinates')
        return result.astype(float)


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)


def audit(experiment, destination):
    registration = experiment / 'registration'
    config = json.loads((experiment / 'pipeline/registration.json').read_text())
    import re
    pattern = re.compile(config['dataset']['include_filename_regex'])
    sources = sorted(p for p in (experiment / 'preprocessing/clouds').rglob('*.pcd') if pattern.fullmatch(p.name))
    manifest = {r['source']: r for r in csv.DictReader((registration / 'manifest.csv').open())}
    rows = []
    for source in sources:
        relative = source.relative_to(experiment / 'preprocessing/clouds')
        row = {'source': str(relative), 'manifest_status': manifest.get(str(relative), {}).get('status', 'missing')}
        issues = []
        try:
            before = xyz(source)
            after = xyz(registration / 'registrations' / relative)
            matrix = np.loadtxt(registration / 'transforms' / relative.with_suffix('.mat'))
            if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
                raise ValueError('invalid 4x4 matrix')
            rotation = matrix[:3, :3]
            determinant = np.linalg.det(rotation)
            orthogonality = np.max(np.abs(rotation.T @ rotation - np.eye(3)))
            row.update(points=len(before), determinant=determinant, orthogonality_max_error=orthogonality,
                       translation_norm=float(np.linalg.norm(matrix[:3, 3])),
                       rotation_degrees=float(np.degrees(np.arccos(np.clip((np.trace(rotation)-1)/2, -1, 1)))))
            if abs(determinant - 1) > 1e-3 or orthogonality > 1e-3 or not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-6):
                issues.append('nonrigid_matrix')
            if before.shape != after.shape:
                issues.append('point_count_mismatch')
            else:
                # cloudPartitioning sorts the source in place by the last axis.
                axis = ('x', 'y', 'z').index(config['processing']['fields'][-1])
                before = before[np.argsort(before[:, axis])]
                predicted = before @ rotation.T + matrix[:3, 3]
                error = np.linalg.norm(predicted - after, axis=1)
                # std::sort does not define ordering among equal coordinates.
                boundaries = np.r_[0, np.flatnonzero(np.diff(before[:, axis]))+1, len(before)]
                for start, end in zip(boundaries[:-1], boundaries[1:]):
                    if end-start > 1:
                        distances = np.linalg.norm(predicted[start:end, None, :] - after[None, start:end, :], axis=2)
                        error[start:end] = np.maximum(distances.min(axis=0), distances.min(axis=1))
                row['transform_residual_max'] = float(error.max())
                row['transform_residual_rms'] = float(np.sqrt(np.mean(error**2)))
                # Matrix writer rounds coefficients to six decimal places.
                if error.max() > 0.002:
                    issues.append('saved_cloud_inconsistent_with_matrix')
            if row['manifest_status'] not in ('processed', 'skipped'):
                issues.append('manifest_not_successful')
        except Exception as exc:
            issues.append(str(exc))
        row['issues'] = '; '.join(issues)
        row['artifact_status'] = 'review' if issues else 'consistent'
        rows.append(row)
    destination.mkdir(parents=True, exist_ok=True)
    write_csv(destination / 'faces.csv', rows)
    aligned = []
    for source in sources:
        if not source.name.endswith('_N_N_0.pcd'):
            continue
        relative = source.relative_to(experiment / 'preprocessing/clouds')
        row = {'source': str(relative)}
        try:
            x = xyz(source)
            y = xyz(registration / 'reference_mask/aligned_gallery' / relative)
            if x.shape != y.shape:
                raise ValueError('point count mismatch')
            u, _, vt = np.linalg.svd((x-x.mean(0)).T @ (y-y.mean(0)))
            fix = np.eye(3)
            fix[2, 2] = np.linalg.det(u @ vt)
            rotation = u @ fix @ vt
            error = np.linalg.norm((x-x.mean(0)) @ rotation - (y-y.mean(0)), axis=1)
            row.update(rigid_fit_residual_max=float(error.max()), status='consistent' if error.max() < .002 else 'review')
        except Exception as exc:
            row.update(status='review', issue=str(exc))
        aligned.append(row)
    write_csv(destination / 'mask_gallery.csv', aligned)
    logs = []
    for log in sorted(registration.rglob('*.log')):
        logs.append({'path': str(log.relative_to(experiment)), 'text': log.read_text(errors='replace')})
    summary = {'experiment': experiment.name, 'selected_faces': len(sources),
               'manifest_statuses': dict(Counter(r['manifest_status'] for r in rows)),
               'artifact_statuses': dict(Counter(r['artifact_status'] for r in rows)),
               'mask_gallery_statuses': dict(Counter(r['status'] for r in aligned)),
               'logs_found': len(logs), 'logs': logs,
               'limitations': ['Successful stdout/stderr were not persisted.', 'ICP convergence was not checked or recorded.',
                               'Rigid matrix and consistent output do not certify anatomical alignment.']}
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k:v for k,v in summary.items() if k != 'logs'}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('data/results/BOSPHORUS/experiments'))
    args = parser.parse_args()
    for experiment in sorted(args.results.iterdir()):
        if (experiment / 'pipeline/registration.json').exists():
            audit(experiment, experiment / 'audit/registration')
    experiments = sorted(p for p in args.results.iterdir() if (p / 'registration/reference_mask/aligned_gallery').exists())
    if len(experiments) == 2:
        first, second = experiments
        differences = []
        for p in sorted((first / 'registration/reference_mask/aligned_gallery').rglob('*.pcd')):
            q = second / p.relative_to(first)
            if q.exists() and hashlib.sha256(p.read_bytes()).digest() != hashlib.sha256(q.read_bytes()).digest():
                a, b = xyz(p), xyz(q)
                differences.append({'source': str(p.relative_to(first)), 'same_shape': a.shape == b.shape,
                                    'max_coordinate_difference': float(np.max(np.abs(a-b))) if a.shape == b.shape else ''})
        write_csv(args.results / 'mask_gallery_differences.csv', differences)
