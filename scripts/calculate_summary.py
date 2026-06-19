from __future__ import annotations

import json
import math
from collections import Counter

import geopandas as gpd

from common import AREAS, OUT, SGIS_KEYWORDS, allocated_sgis_for_geometry, ensure_dirs, load_boundary, write_json


def read_analytics(name: str):
    path = OUT / "analytics" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def by_key(rows):
    return {row["area_key"]: row for row in rows}


def read_report(name: str):
    path = OUT / "reports" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def round_display(value) -> int:
    return int(round(float(value or 0)))


def building_metrics(area_key: str) -> dict:
    path = OUT / "buildings" / f"{area_key}_buildings.geojson"
    if not path.exists():
        return {"count": 0, "avg_far": None, "gross_floor_area_m2": 0, "land_area_m2": 0, "main_use_composition": []}
    gdf = gpd.read_file(path)
    count = len(gdf)
    far_values = []
    for value in gdf.get("floor_area_ratio", []):
        try:
            number = float(value)
            if not math.isnan(number) and number > 0:
                far_values.append(number)
        except (TypeError, ValueError):
            pass
    gross_floor_area = 0.0
    land_area = 0.0
    use_counter = Counter()
    use_floor_area = Counter()
    for _, row in gdf.iterrows():
        main_use = str(row.get("main_use") or "")
        if main_use and main_use not in ["None", "nan"]:
            use_counter[main_use] += 1
        try:
            gfa = float(row.get("gross_floor_area_m2") or 0)
        except (TypeError, ValueError):
            gfa = 0.0
        try:
            la = float(row.get("land_area_m2") or 0)
        except (TypeError, ValueError):
            la = 0.0
        if math.isnan(gfa):
            gfa = 0.0
        if math.isnan(la):
            la = 0.0
        gross_floor_area += gfa
        land_area += la
        if main_use and gfa > 0:
            use_floor_area[main_use] += gfa
    return {
        "count": int(count),
        "avg_far": round(sum(far_values) / len(far_values), 1) if far_values else None,
        "gross_floor_area_m2": round(gross_floor_area, 1),
        "land_area_m2": round(land_area, 1),
        "main_use_composition": [
            {
                "main_use": name,
                "count": count,
                "share": round(count / len(gdf), 4) if len(gdf) else 0,
                "gross_floor_area_m2": round(use_floor_area.get(name, 0), 1),
                "floor_area_share": round(use_floor_area.get(name, 0) / gross_floor_area, 4) if gross_floor_area else 0,
            }
            for name, count in use_counter.most_common()
        ],
    }


def catchment_meta_features(item: dict, key: str) -> int:
    meta = item.get("allocation_meta", {}).get(key, {})
    if "features" in meta:
        return int(meta.get("features") or 0)
    return int(sum((region or {}).get("features", 0) for region in meta.get("regions", {}).values()))


def cheongna_previous_boundary_metrics(existing_validation: dict) -> dict | None:
    old = existing_validation.get("cheongna", {}) if isinstance(existing_validation, dict) else {}
    if old.get("boundary_comparison", {}).get("previous"):
        return old["boundary_comparison"]["previous"]
    if not old or old.get("boundary_basis") == AREAS["cheongna"]["boundary_basis"]:
        return None
    return {
        "boundary_basis": old.get("boundary_basis"),
        "area_m2": old.get("boundary_area_m2"),
        "businesses": old.get("total_businesses"),
        "workers": old.get("total_workers"),
        "population": old.get("total_population"),
        "job_housing_ratio": old.get("job_housing_ratio"),
        "landuse_mix_index": old.get("landuse_mix_index"),
        "parcel_count": old.get("parcel_count"),
        "building_count": old.get("building_count"),
    }


def boundary_comparison(previous: dict | None, current: dict) -> dict | None:
    if not previous:
        return None
    fields = ["area_m2", "businesses", "workers", "job_housing_ratio", "landuse_mix_index"]
    result = {"previous": previous, "current": current, "change": {}}
    for field in fields:
        old = previous.get(field)
        new = current.get(field)
        if old is None or new is None:
            result["change"][field] = None
            continue
        old_f = float(old)
        new_f = float(new)
        result["change"][field] = {
            "absolute": round(new_f - old_f, 4),
            "ratio": round((new_f / old_f - 1) if old_f else 0, 4),
        }
    return result


def main() -> None:
    ensure_dirs()
    access = by_key(read_analytics("accessibility.json"))
    landuse = by_key(read_analytics("landuse_mix.json"))
    industry = by_key(read_analytics("industry.json"))
    bonus = by_key(read_analytics("bonus_indicators.json"))
    spatial = by_key(read_analytics("spatial_accessibility.json"))
    existing_validation = read_report("validation_report.json")
    boundary_reports = by_key(read_report("boundary_match_reports.json") or [])
    cheongna_previous = cheongna_previous_boundary_metrics(existing_validation)
    rows = []
    validation = {}

    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        geom = boundary.geometry.iloc[0]
        area_m2 = float(geom.area)
        parcels = gpd.read_file(OUT / "parcels" / f"{key}_matched_parcels.geojson")
        buildings = building_metrics(key)

        allocated_population, pop_meta = allocated_sgis_for_geometry(key, geom, SGIS_KEYWORDS["population"])
        allocated_households, household_meta = allocated_sgis_for_geometry(key, geom, SGIS_KEYWORDS["households"])
        allocated_workers, worker_meta = allocated_sgis_for_geometry(key, geom, SGIS_KEYWORDS["workers"])
        allocated_businesses, business_meta = allocated_sgis_for_geometry(key, geom, SGIS_KEYWORDS["businesses_total"])
        if not allocated_businesses:
            allocated_businesses, business_meta = allocated_sgis_for_geometry(key, geom, SGIS_KEYWORDS["businesses"])

        catchment = {item["minutes"]: item for item in access.get(key, {}).get("cumulative_accessibility", [])}
        catchment_30 = catchment.get(30, {})
        catchment_60 = catchment.get(60, {})
        pop_int = round_display(allocated_population)
        households_int = round_display(allocated_households)
        workers_int = round_display(allocated_workers)
        businesses_int = round_display(allocated_businesses)
        job_housing_ratio = round(workers_int / pop_int, 3) if pop_int else None
        functional_report = (boundary_reports.get(key, {}) or {}).get("filter_report") or {}
        current_boundary_metrics = {
            "boundary_basis": cfg["boundary_basis"],
            "area_m2": round(area_m2, 1),
            "businesses": businesses_int,
            "workers": workers_int,
            "population": pop_int,
            "job_housing_ratio": job_housing_ratio,
            "landuse_mix_index": landuse.get(key, {}).get("landuse_mix_index", 0),
            "parcel_count": int(len(parcels)),
            "building_count": buildings["count"],
        }
        comparison = boundary_comparison(cheongna_previous, current_boundary_metrics) if key == "cheongna" else None

        row_data = {
                "area_key": key,
                "label": cfg["label"],
                "analysis_date": "2023-12-31",
                "boundary_source": cfg["source"],
                "boundary_definition": cfg["definition"],
                "boundary_basis": cfg["boundary_basis"],
                "boundary_note": cfg["boundary_note"],
                "boundary_area_calculation_method": "구역 면적은 경계 GeoJSON을 EPSG:5179 좌표계로 변환한 뒤 산출하였다.",
                "boundary_area_m2": round(area_m2, 1),
                "boundary_area_km2": round(area_m2 / 1_000_000, 4),
                "allocated_population": round(allocated_population, 1),
                "allocated_households": round(allocated_households, 1),
                "allocated_workers": round(allocated_workers, 1),
                "allocated_businesses": round(allocated_businesses, 1),
                "display_population": pop_int,
                "display_households": households_int,
                "display_workers": workers_int,
                "display_businesses": businesses_int,
                "commuter_population_30min": round_display(catchment_30.get("allocated_population")),
                "commuter_population_60min": round_display(catchment_60.get("allocated_population")),
                "commuter_workers_30min": round_display(catchment_30.get("allocated_workers")),
                "commuter_workers_60min": round_display(catchment_60.get("allocated_workers")),
                "population_density_per_km2": round(allocated_population / (area_m2 / 1_000_000), 1) if area_m2 else 0,
                "landuse_mix_index": landuse.get(key, {}).get("landuse_mix_index", 0),
                "zoning_landuse_mix_index": landuse.get(key, {}).get("zoning_landuse_mix_index"),
                "building_landuse_mix_index": landuse.get(key, {}).get("building_landuse_mix_index"),
                "lum_method": landuse.get(key, {}).get("lum_method"),
                "avg_floor_area_ratio": buildings["avg_far"],
                "building_count": buildings["count"],
                "building_gross_floor_area_m2": buildings["gross_floor_area_m2"],
                "building_land_area_m2": buildings["land_area_m2"],
                "job_housing_ratio": job_housing_ratio,
                "nearest_station_m": access.get(key, {}).get("nearest_station_m"),
                "station_count_2km": access.get(key, {}).get("station_count_2km", 0),
                "compactness": bonus.get(key, {}).get("compactness", 0),
                "bus_stop_count": spatial.get(key, {}).get("bus_stop_count"),
                "bus_stop_density_per_km2": spatial.get(key, {}).get("bus_stop_density_per_km2"),
                "road_length_km": spatial.get(key, {}).get("road_length_km"),
                "road_network_density_km_per_km2": spatial.get(key, {}).get("road_network_density_km_per_km2"),
                "nearest_highway_ic_km": spatial.get(key, {}).get("nearest_highway_ic_km"),
                "nearest_highway_ic_name": spatial.get(key, {}).get("nearest_highway_ic_name"),
                "station_area_ratio_500m": spatial.get(key, {}).get("station_area_ratio_500m"),
                "station_area_ratio_1km": spatial.get(key, {}).get("station_area_ratio_1km"),
                "station_count_500m": spatial.get(key, {}).get("station_count_500m"),
                "station_count_1km": spatial.get(key, {}).get("station_count_1km"),
                "allocation_meta": {
                    "population": pop_meta,
                    "households": household_meta,
                    "workers": worker_meta,
                    "businesses": business_meta,
                },
                "allocation_method": "aggregation_area_weighted_internal; display values rounded",
        }
        if functional_report:
            row_data["functional_boundary_metrics"] = functional_report
        if comparison:
            row_data["boundary_comparison"] = comparison
        rows.append(row_data)

        validation_data = {
            "label": cfg["label"],
            "boundary_source": cfg["source"],
            "boundary_definition": cfg["definition"],
            "boundary_basis": cfg["boundary_basis"],
            "boundary_note": cfg["boundary_note"],
            "boundary_area_calculation_method": "구역 면적은 경계 GeoJSON을 EPSG:5179 좌표계로 변환한 뒤 산출하였다.",
            "boundary_area_m2": round(area_m2, 1),
            "boundary_area_km2": round(area_m2 / 1_000_000, 4),
            "building_count": buildings["count"],
            "building_gross_floor_area_m2": buildings["gross_floor_area_m2"],
            "building_land_area_m2": buildings["land_area_m2"],
            "parcel_count": int(len(parcels)),
            "aggregation_count_population": pop_meta.get("features", 0),
            "aggregation_count_households": household_meta.get("features", 0),
            "aggregation_count_businesses": business_meta.get("features", 0),
            "aggregation_count_workers": worker_meta.get("features", 0),
            "total_population": pop_int,
            "total_households": households_int,
            "total_businesses": businesses_int,
            "total_workers": workers_int,
            "landuse_mix_index": landuse.get(key, {}).get("landuse_mix_index", 0),
            "zoning_landuse_mix_index": landuse.get(key, {}).get("zoning_landuse_mix_index"),
            "building_landuse_mix_index": landuse.get(key, {}).get("building_landuse_mix_index"),
            "lum_method": landuse.get(key, {}).get("lum_method"),
            "avg_floor_area_ratio": buildings["avg_far"],
            "job_housing_ratio": job_housing_ratio,
            "reachable_station_30_count": int(catchment_30.get("reachable_station_count") or 0),
            "reachable_station_60_count": int(catchment_60.get("reachable_station_count") or 0),
            "reachable_station_delta_60_30": int(catchment_60.get("reachable_station_count") or 0)
            - int(catchment_30.get("reachable_station_count") or 0),
            "aggregation_count_30min_population": catchment_meta_features(catchment_30, "population"),
            "aggregation_count_60min_population": catchment_meta_features(catchment_60, "population"),
            "commuter_population_30min": round_display(catchment_30.get("allocated_population")),
            "commuter_population_60min": round_display(catchment_60.get("allocated_population")),
            "commuter_population_delta_60_30": round_display(catchment_60.get("allocated_population"))
            - round_display(catchment_30.get("allocated_population")),
            "commuter_workers_30min": round_display(catchment_30.get("allocated_workers")),
            "commuter_workers_60min": round_display(catchment_60.get("allocated_workers")),
            "commuter_workers_delta_60_30": round_display(catchment_60.get("allocated_workers"))
            - round_display(catchment_30.get("allocated_workers")),
            "bus_stop_count": spatial.get(key, {}).get("bus_stop_count"),
            "bus_stop_density_per_km2": spatial.get(key, {}).get("bus_stop_density_per_km2"),
            "bus_stop_note": spatial.get(key, {}).get("bus_stop_note"),
            "road_length_km": spatial.get(key, {}).get("road_length_km"),
            "road_network_density_km_per_km2": spatial.get(key, {}).get("road_network_density_km_per_km2"),
            "road_note": spatial.get(key, {}).get("road_note"),
            "nearest_highway_ic_km": spatial.get(key, {}).get("nearest_highway_ic_km"),
            "nearest_highway_ic_name": spatial.get(key, {}).get("nearest_highway_ic_name"),
            "ic_note": spatial.get(key, {}).get("ic_note"),
            "station_area_ratio_500m": spatial.get(key, {}).get("station_area_ratio_500m"),
            "station_area_ratio_1km": spatial.get(key, {}).get("station_area_ratio_1km"),
            "station_count_500m": spatial.get(key, {}).get("station_count_500m"),
            "station_count_1km": spatial.get(key, {}).get("station_count_1km"),
            "building_main_use_composition": buildings["main_use_composition"],
        }
        if functional_report:
            validation_data["functional_boundary_metrics"] = functional_report
            validation_data["included_parcel_count"] = functional_report.get("selected_count")
            validation_data["included_building_count"] = functional_report.get("included_building_count")
            validation_data["included_office_gfa_m2"] = functional_report.get("included_office_gfa_m2")
            validation_data["included_businesses"] = functional_report.get("included_businesses")
            validation_data["included_workers"] = functional_report.get("included_workers")
            validation_data["final_area_m2"] = validation_data["boundary_area_m2"]
        if comparison:
            validation_data["boundary_comparison"] = comparison
        validation[key] = validation_data

    write_json(OUT / "analytics" / "summary.json", rows)
    write_json(OUT / "reports" / "validation_report.json", validation)
    for row in rows:
        print(
            f"{row['area_key']}: population={row['display_population']} "
            f"workers={row['display_workers']} businesses={row['display_businesses']}"
        )


if __name__ == "__main__":
    main()
