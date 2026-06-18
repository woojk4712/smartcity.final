from __future__ import annotations

import re
from collections import defaultdict

import geopandas as gpd
import pandas as pd

from common import AREAS, CRS_METRIC, CRS_WEB, OUT, ensure_dirs, normalize_pnu, read_xlsx_first_sheet, write_json


def _read_cheongna_landuse(pnus: set[str]) -> dict[str, list[str]]:
    source = OUT.parents[1] / "청라" / "인천_토지이용계획" / "AL_D155_28_20260609.csv"
    result: dict[str, list[str]] = defaultdict(list)
    if not source.exists():
        return result
    for chunk in pd.read_csv(source, usecols=["고유번호", "용도지역지구명"], dtype=str, chunksize=200_000, encoding="cp949"):
        sub = chunk[chunk["고유번호"].isin(pnus)]
        for _, row in sub.iterrows():
            result[str(row["고유번호"])].append(str(row["용도지역지구명"]))
    return result


def _cheongna_business_filter(parcels: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    parcels = parcels.copy()
    parcels["lot_base"] = parcels["JIBUN"].astype(str).str.extract(r"(\d+)")[0].astype(float)
    landuse = _read_cheongna_landuse(set(parcels["PNU_NORM"]))

    def is_business(row) -> bool:
        zones = landuse.get(str(row["PNU_NORM"]), [])
        has_business_zone = any(("상업지역" in z) or ("준주거지역" in z) for z in zones)
        is_core_lot = 93 <= float(row["lot_base"]) <= 107
        is_cheongna_dong = str(row["PNU_NORM"]).startswith("28260122")
        return is_cheongna_dong and is_core_lot and has_business_zone

    filtered = parcels[parcels.apply(is_business, axis=1)].copy()
    filtered["boundary_rule"] = "청라동 93~107 지번대 + 토지이용계획 상업지역/준주거지역"
    report = {
        "filter_rule": filtered["boundary_rule"].iloc[0] if not filtered.empty else "no_match",
        "source_note": "별도 공식 SHP 부재로 업로드 PNU, 연속지적도, 토지이용계획을 조합해 국제업무지구 경계를 재구성",
        "candidate_before_count": int(len(parcels)),
        "selected_count": int(len(filtered)),
        "candidate_area_m2": round(float(parcels.geometry.area.sum()), 1),
        "selected_area_m2": round(float(filtered.geometry.area.sum()), 1),
    }
    return filtered, report


def build_boundary(area_key: str) -> dict:
    cfg = AREAS[area_key]
    parcels = gpd.read_file(cfg["cadastre"]).to_crs(CRS_METRIC)
    parcels["PNU_NORM"] = parcels["PNU"].map(normalize_pnu)

    lots = read_xlsx_first_sheet(cfg["xlsx"])
    pnu_col = next((c for c in lots.columns if c.lower() == "pnu"), lots.columns[0])
    address_col = next((c for c in lots.columns if "주소" in c), None)
    lots["PNU_NORM"] = lots[pnu_col].map(normalize_pnu)
    wanted = [p for p in lots["PNU_NORM"].dropna().tolist() if p]

    matched_all = parcels[parcels["PNU_NORM"].isin(wanted)].copy()
    filter_report = None
    if area_key == "cheongna":
        matched, filter_report = _cheongna_business_filter(matched_all)
    else:
        matched = matched_all.copy()
        matched["boundary_rule"] = "성남판교 도시지원시설용지 소재지 PNU 전체"

    matched_pnus = set(matched["PNU_NORM"])
    duplicate_pnus = sorted([p for p in set(wanted) if wanted.count(p) > 1])
    missing = lots[~lots["PNU_NORM"].isin(set(matched_all["PNU_NORM"]))].copy()

    if matched.empty:
        raise RuntimeError(f"{area_key}: no parcels matched after boundary filter.")

    unioned = matched.geometry.union_all()
    boundary = gpd.GeoDataFrame(
        [
            {
                "area_key": area_key,
                "name": cfg["label"],
                "boundary_source": cfg["source"],
                "boundary_rule": str(matched["boundary_rule"].iloc[0]),
            }
        ],
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
        "boundary_source": cfg["source"],
        "input_lot_count": len(wanted),
        "matched_before_filter_count": int(len(matched_all)),
        "matched_parcel_count": int(len(matched)),
        "matched_unique_pnu_count": len(matched_pnus),
        "match_rate_before_filter": round(len(set(matched_all["PNU_NORM"])) / len(set(wanted)), 4) if wanted else 0,
        "analysis_area_m2": round(float(boundary.geometry.area.iloc[0]), 1),
        "duplicate_pnus": duplicate_pnus,
        "missing": [
            {"pnu": row["PNU_NORM"], "address": row[address_col] if address_col else ""}
            for _, row in missing.iterrows()
        ],
        "filter_report": filter_report,
    }
    write_json(OUT / "reports" / f"{area_key}_boundary_match_report.json", report)
    return report


def main() -> None:
    ensure_dirs()
    reports = [build_boundary(key) for key in AREAS]
    write_json(OUT / "reports" / "boundary_match_reports.json", reports)
    for report in reports:
        print(
            f"{report['area_key']}: parcels={report['matched_parcel_count']} "
            f"area_m2={report['analysis_area_m2']} source={report['boundary_source']}"
        )


if __name__ == "__main__":
    main()
