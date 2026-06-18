from __future__ import annotations

from common import AREAS, OUT, ensure_dirs, load_boundary, rough_compactness, write_json


def main() -> None:
    ensure_dirs()
    rows = []
    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        area_m2 = float(boundary.geometry.area.iloc[0])
        perimeter_m = float(boundary.geometry.length.iloc[0])
        rows.append(
            {
                "area_key": key,
                "label": cfg["label"],
                "source": "computed_boundary_geometry_plus_sample_missing_indicators",
                "area_km2": round(area_m2 / 1_000_000, 3),
                "perimeter_km": round(perimeter_m / 1000, 3),
                "compactness": round(rough_compactness(area_m2, perimeter_m), 3),
                "road_density_km_per_km2": None,
                "official_company_count": None,
                "note": "도로망, 공식 입주기업, 매출 지표 원자료가 추가되면 실제값으로 대체",
            }
        )
    write_json(OUT / "analytics" / "bonus_indicators.json", rows)
    for row in rows:
        print(f"{row['area_key']}: area_km2={row['area_km2']} compactness={row['compactness']}")


if __name__ == "__main__":
    main()
