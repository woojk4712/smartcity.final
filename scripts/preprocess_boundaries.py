from __future__ import annotations

import geopandas as gpd

from common import AREAS, CRS_METRIC, CRS_WEB, OUT, ensure_dirs, normalize_pnu, read_xlsx_first_sheet, write_json


def build_boundary(area_key: str) -> dict:
    cfg = AREAS[area_key]
    parcels = gpd.read_file(cfg["cadastre"]).to_crs(CRS_METRIC)
    parcels["PNU_NORM"] = parcels["PNU"].map(normalize_pnu)

    lots = read_xlsx_first_sheet(cfg["xlsx"])
    pnu_col = next((c for c in lots.columns if c.lower() == "pnu"), lots.columns[0])
    address_col = next((c for c in lots.columns if "주소" in c), None)
    lots["PNU_NORM"] = lots[pnu_col].map(normalize_pnu)
    wanted = [p for p in lots["PNU_NORM"].dropna().tolist() if p]

    matched = parcels[parcels["PNU_NORM"].isin(wanted)].copy()
    matched_pnus = set(matched["PNU_NORM"])
    duplicate_pnus = sorted([p for p in set(wanted) if wanted.count(p) > 1])
    missing = lots[~lots["PNU_NORM"].isin(matched_pnus)].copy()

    if matched.empty:
        raise RuntimeError(f"{area_key}: no parcels matched. Check PNU column and cadastre file.")

    unioned = matched.geometry.union_all()
    boundary = gpd.GeoDataFrame(
        [{"area_key": area_key, "name": cfg["label"], "source": "xlsx_pnu_cadastre_union"}],
        geometry=[unioned],
        crs=CRS_METRIC,
    )
    boundary["area_m2"] = boundary.geometry.area
    boundary["perimeter_m"] = boundary.geometry.length

    boundary.to_crs(CRS_WEB).to_file(OUT / "boundaries" / f"{area_key}_boundary.geojson", driver="GeoJSON")
    matched.to_crs(CRS_WEB).to_file(OUT / "parcels" / f"{area_key}_matched_parcels.geojson", driver="GeoJSON")

    report = {
        "area_key": area_key,
        "label": cfg["label"],
        "input_lot_count": len(wanted),
        "matched_parcel_count": int(len(matched)),
        "matched_unique_pnu_count": len(matched_pnus),
        "match_rate": round(len(matched_pnus) / len(set(wanted)), 4) if wanted else 0,
        "duplicate_pnus": duplicate_pnus,
        "missing": [
            {"pnu": row["PNU_NORM"], "address": row[address_col] if address_col else ""}
            for _, row in missing.iterrows()
        ],
    }
    write_json(OUT / "reports" / f"{area_key}_boundary_match_report.json", report)
    return report


def main() -> None:
    ensure_dirs()
    reports = [build_boundary(key) for key in AREAS]
    write_json(OUT / "reports" / "boundary_match_reports.json", reports)
    for report in reports:
        print(f"{report['area_key']}: match_rate={report['match_rate']} matched={report['matched_unique_pnu_count']}/{report['input_lot_count']}")


if __name__ == "__main__":
    main()
