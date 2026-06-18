from __future__ import annotations

import json

from common import AREAS, OUT, allocated_sgis_for_geometry, ensure_dirs, load_boundary, write_json


def read_analytics(name: str):
    path = OUT / "analytics" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def by_key(rows):
    return {row["area_key"]: row for row in rows}


def main() -> None:
    ensure_dirs()
    access = by_key(read_analytics("accessibility.json"))
    landuse = by_key(read_analytics("landuse_mix.json"))
    bonus = by_key(read_analytics("bonus_indicators.json"))
    rows = []
    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        geom = boundary.geometry.iloc[0]
        area_m2 = float(geom.area)

        allocated_population, pop_meta = allocated_sgis_for_geometry(key, geom, "인구총괄(총인구)")
        allocated_households, household_meta = allocated_sgis_for_geometry(key, geom, "가구총괄")
        allocated_workers, worker_meta = allocated_sgis_for_geometry(key, geom, "산업분류별(10차_대분류)_종사자수")
        allocated_businesses, business_meta = allocated_sgis_for_geometry(key, geom, "산업분류별(10차_대분류)_총괄사업체수")
        if not allocated_businesses:
            allocated_businesses, business_meta = allocated_sgis_for_geometry(key, geom, "산업분류별(10차_대분류)_사업체수")

        catchment = {}
        for item in access.get(key, {}).get("cumulative_accessibility", []):
            if item.get("minutes") == 60:
                catchment = item

        rows.append(
            {
                "area_key": key,
                "label": cfg["label"],
                "analysis_date": "2023-12-31",
                "boundary_area_m2": round(area_m2, 1),
                "allocated_population": round(allocated_population, 1),
                "allocated_households": round(allocated_households, 1),
                "allocated_workers": round(allocated_workers, 1),
                "allocated_businesses": round(allocated_businesses, 1),
                "commuter_population_60min": catchment.get("allocated_population", 0),
                "commuter_households_60min": catchment.get("allocated_households", 0),
                "commuter_workers_60min": catchment.get("allocated_workers", 0),
                "population_density_per_km2": round(allocated_population / (area_m2 / 1_000_000), 1) if area_m2 else 0,
                "landuse_mix_index": landuse.get(key, {}).get("landuse_mix_index", 0),
                "nearest_station_m": access.get(key, {}).get("nearest_station_m"),
                "station_count_2km": access.get(key, {}).get("station_count_2km", 0),
                "compactness": bonus.get(key, {}).get("compactness", 0),
                "allocation_meta": {
                    "population": pop_meta,
                    "households": household_meta,
                    "workers": worker_meta,
                    "businesses": business_meta,
                },
                "allocation_method": "aggregation_area_weighted",
            }
        )
    write_json(OUT / "analytics" / "summary.json", rows)
    for row in rows:
        print(f"{row['area_key']}: population={row['allocated_population']} density={row['population_density_per_km2']}")


if __name__ == "__main__":
    main()
