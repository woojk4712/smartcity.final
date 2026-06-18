from __future__ import annotations

import geopandas as gpd

from common import AREAS, CRS_METRIC, OUT, ensure_dirs, load_boundary, write_json


def fix_mojibake(value):
    if value is None:
        return value
    text = str(value)
    try:
        return text.encode("latin1").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def include_parcel_by_overlap(parcel_geom, boundary_geom, threshold: float = 0.5) -> tuple[bool, float, float]:
    original_area = parcel_geom.area
    overlap_area = parcel_geom.intersection(boundary_geom).area
    ratio = overlap_area / original_area if original_area else 0.0
    return ratio >= threshold, overlap_area, ratio


def allocate_by_area(value: float, source_area: float, overlap_area: float) -> float:
    return 0.0 if source_area <= 0 else value * (overlap_area / source_area)


def centroid_inside(geom, boundary_geom) -> bool:
    return boundary_geom.contains(geom.centroid)


def build_building_join(area_key: str) -> dict:
    boundary = load_boundary(area_key)
    boundary_geom = boundary.geometry.iloc[0]
    building_path = OUT.parents[1] / "GIS건물통합정보" / "CH_D010_00_20231231.shp"
    if not building_path.exists():
        return {"area_key": area_key, "building_count": 0, "note": "building source missing"}

    buildings = gpd.read_file(building_path).to_crs(CRS_METRIC)
    subset = buildings[buildings.geometry.centroid.within(boundary_geom)].copy()
    subset["overlap_area"] = subset.geometry.area
    subset["overlap_ratio"] = 1.0
    subset["main_use"] = subset.get("A9").map(fix_mojibake) if "A9" in subset else None
    subset["building_area_m2"] = subset.get("A12")
    subset["gross_floor_area_m2"] = subset.get("A14")
    subset["land_area_m2"] = subset.get("A15")
    subset["building_coverage_ratio"] = subset.get("A17")
    subset["floor_area_ratio"] = subset.get("A18")
    subset.to_crs("EPSG:4326").to_file(OUT / "buildings" / f"{area_key}_buildings.geojson", driver="GeoJSON")
    return {"area_key": area_key, "building_count": int(len(subset))}


def main() -> None:
    ensure_dirs()
    reports = [build_building_join(key) for key in AREAS]
    write_json(OUT / "reports" / "spatial_join_report.json", reports)
    for report in reports:
        print(f"{report['area_key']}: buildings={report.get('building_count', 0)}")


if __name__ == "__main__":
    main()
