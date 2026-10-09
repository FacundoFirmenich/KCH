from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Iterable

from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, mapping, shape
from shapely.strtree import STRtree

RAW_URL = (
    'https://raw.githubusercontent.com/GEMScienceTools/gem-global-active-faults/'
    '56816508ad92fd6846dad1163b1c8c01376a2cd1/'
    'geojson/gem_active_faults_harmonized.geojson'
)
EXPECTED_SHA256 = '37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1'
USED_IDS = [0,1,2,12,13,14,27,85,86,91,92,142,198,212,213,224,225,227,228,229,230,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,255,256,257,258,259,260,261,263,264,265,266,267,269,270,271,307,309,310,311,312,330,331,349]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def flatten(geom) -> Iterable[LineString]:
    if isinstance(geom, LineString):
        yield geom
    elif isinstance(geom, MultiLineString):
        yield from geom.geoms


def project_line(line: LineString, transformer: Transformer) -> LineString:
    return LineString([
        transformer.transform(float(coordinate[0]), float(coordinate[1]))
        for coordinate in line.coords
    ])


def endpoint_distance(a: LineString, b: LineString) -> float:
    ae = [a.coords[0], a.coords[-1]]
    be = [b.coords[0], b.coords[-1]]
    return min(math.hypot(x1-x2, y1-y2) for x1,y1 in ae for x2,y2 in be)


def main(source: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    observed = sha256(source)
    if observed != EXPECTED_SHA256:
        raise SystemExit(f'fault source SHA mismatch: {observed}')
    root = json.loads(source.read_text(encoding='utf-8'))
    transformer = Transformer.from_crs('EPSG:4326', 'EPSG:3310', always_xy=True)

    original_lines: list[LineString] = []
    projected: list[LineString] = []
    properties: list[dict] = []
    feature_index: list[int] = []
    part_index: list[int] = []
    for fi, feature in enumerate(root.get('features', [])):
        geom = shape(feature.get('geometry'))
        for pi, line in enumerate(flatten(geom)):
            if len(line.coords) < 2:
                continue
            original_lines.append(line)
            projected.append(project_line(line, transformer))
            properties.append(dict(feature.get('properties') or {}))
            feature_index.append(fi)
            part_index.append(pi)

    if max(USED_IDS) >= len(projected):
        raise SystemExit(f'used line id outside flattened network: max={max(USED_IDS)} n={len(projected)}')

    tree = STRtree(projected)
    relevant = set(USED_IDS)
    nearest_used_distance: dict[int, float] = {i: 0.0 for i in USED_IDS}
    for uid in USED_IDS:
        line = projected[uid]
        for cid in map(int, tree.query(line.buffer(5000.0))):
            d = float(line.distance(projected[cid]))
            if d <= 5000.0:
                relevant.add(cid)
                nearest_used_distance[cid] = min(nearest_used_distance.get(cid, float('inf')), d)

    used_set = set(USED_IDS)
    adjacency_rows = []
    for i in sorted(USED_IDS):
        for j in sorted(map(int, tree.query(projected[i].buffer(5000.0)))):
            if j <= i or j not in used_set:
                continue
            d = float(projected[i].distance(projected[j]))
            if d > 5000.0:
                continue
            adjacency_rows.append({
                'line_i': i,
                'line_j': j,
                'geometry_distance_m': d,
                'endpoint_distance_m': endpoint_distance(projected[i], projected[j]),
                'adjacent_250m': d <= 250.0,
                'adjacent_1km': d <= 1000.0,
                'near_5km': d <= 5000.0,
            })

    with (out / 'used_segment_adjacency.csv').open('w', newline='', encoding='utf-8') as f:
        fields = list(adjacency_rows[0]) if adjacency_rows else [
            'line_i','line_j','geometry_distance_m','endpoint_distance_m','adjacent_250m','adjacent_1km','near_5km'
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(adjacency_rows)

    features = []
    line_rows = []
    for idx in sorted(relevant):
        p = dict(properties[idx])
        p.update({
            'flattened_line_index': idx,
            'source_feature_index': feature_index[idx],
            'source_part_index': part_index[idx],
            'selected_event_segment': idx in used_set,
            'nearest_selected_segment_distance_m': float(nearest_used_distance.get(idx, float('nan'))),
        })
        features.append({'type':'Feature','properties':p,'geometry':mapping(original_lines[idx])})
        line_rows.append({
            'flattened_line_index': idx,
            'source_feature_index': feature_index[idx],
            'source_part_index': part_index[idx],
            'selected_event_segment': idx in used_set,
            'length_m': float(projected[idx].length),
            'nearest_selected_segment_distance_m': float(nearest_used_distance.get(idx, float('nan'))),
            'catalog_id': str(properties[idx].get('catalog_id','')),
            'name': str(properties[idx].get('name','')),
            'fz_name': str(properties[idx].get('fz_name','')),
            'slip_type': str(properties[idx].get('slip_type','')),
        })

    (out / 'relevant_fault_network.geojson').write_text(
        json.dumps({'type':'FeatureCollection','features':features}, ensure_ascii=False, sort_keys=True, separators=(',',':')) + '\n',
        encoding='utf-8'
    )
    with (out / 'relevant_fault_lines.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(line_rows[0]))
        writer.writeheader(); writer.writerows(line_rows)

    summary = {
        'format':'KCH_HELICAL_V0_9_A_EXTERNAL_FAULT_NETWORK_AUDIT_INPUT',
        'source_url':RAW_URL,
        'source_sha256':EXPECTED_SHA256,
        'flattened_line_count':len(projected),
        'selected_event_segment_count':len(USED_IDS),
        'relevant_line_count_within_5km':len(relevant),
        'used_pair_count_within_5km':len(adjacency_rows),
        'used_pair_count_within_1km':sum(r['adjacent_1km'] for r in adjacency_rows),
        'used_pair_count_within_250m':sum(r['adjacent_250m'] for r in adjacency_rows),
        'used_line_ids':USED_IDS,
        'outputs':{
            'geojson_sha256':sha256(out/'relevant_fault_network.geojson'),
            'line_csv_sha256':sha256(out/'relevant_fault_lines.csv'),
            'adjacency_csv_sha256':sha256(out/'used_segment_adjacency.csv'),
        },
        'authority_ceiling':'NONE',
    }
    (out / 'NETWORK_AUDIT_INPUT_RECEIPT.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: extract_fault_subset.py SOURCE_GEOJSON OUTPUT_DIR')
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
