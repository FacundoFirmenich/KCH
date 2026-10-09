from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, shape
from shapely.strtree import STRtree

import helical_public_acquisition as acquisition

# Importing the public-acquisition adapter binds the exact, unauthenticated
# Mendeley public identity to the frozen v0.10 runner.  This successor changes
# only the dimensional parsing of external GEM geometries: GeoJSON coordinates
# may legitimately contain Z/M ordinates, while the frozen distance gate is
# explicitly two-dimensional in EPSG:3310.
gate = acquisition.gate


def _flatten_lines(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def fault_index_ordinate_safe(path: Path) -> tuple[tuple[LineString, ...], STRtree, Transformer, int]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("type") != "FeatureCollection":
        raise RuntimeError("fault GeoJSON is not a FeatureCollection")

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    observed_coordinate_dimensions: set[int] = set()

    for feature in root.get("features", []):
        geometry = shape(feature.get("geometry"))
        for line in _flatten_lines(geometry):
            projected: list[tuple[float, float]] = []
            for coordinate in line.coords:
                if len(coordinate) < 2:
                    raise RuntimeError("fault coordinate has fewer than two ordinates")
                observed_coordinate_dimensions.add(len(coordinate))
                longitude = float(coordinate[0])
                latitude = float(coordinate[1])
                x, y = transformer.transform(longitude, latitude)
                projected.append((float(x), float(y)))
            if len(projected) >= 2:
                lines.append(LineString(projected))

    if not lines:
        raise RuntimeError("fault GeoJSON has no admissible line geometries")
    if not observed_coordinate_dimensions.issubset({2, 3, 4}):
        raise RuntimeError(
            "unexpected GEM coordinate dimensions: "
            + ",".join(str(value) for value in sorted(observed_coordinate_dimensions))
        )

    values = tuple(lines)
    return values, STRtree(values), transformer, len(root.get("features", []))


gate.fault_index = fault_index_ordinate_safe


if __name__ == "__main__":
    raise SystemExit(gate.main())
