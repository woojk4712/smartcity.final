from __future__ import annotations

import json
import math
import re
from collections import defaultdict

import geopandas as gpd
import pandas as pd

from common import (
    AREAS,
    CRS_METRIC,
    CRS_WEB,
    OUT,
    SGIS_KEYWORDS,
    allocated_sgis_for_geometry,
    ensure_dirs,
    normalize_pnu,
    read_xlsx_first_sheet,
    write_json,
)
from preprocess_spatial_units import BUILDING_REGISTER_PATHS, parse_float, read_building_register


OFFICE_KEYWORDS = ["업무", "오피스", "사무", "금융", "은행", "지식산업"]
COMMERCIAL_KEYWORDS = ["근린생활", "판매", "상가", "숙박", "위락", "운동"]
PUBLIC_EXCLUDE_KEYWORDS = ["학교", "공원", "녹지", "공공공지", "완충녹지", "하천"]
RESIDENTIAL_ONLY_KEYWORDS = ["단독주택", "공동주택", "아파트", "다가구"]
FACILITY_MANAGEMENT_KEYWORDS = ["음악분수", "제어실", "변전실", "펌프실", "기계실", "전기실", "관리동", "관리실", "시설관리"]
FUNCTIONAL_SCORE_THRESHOLD = 3.0


def _read_cheongna_landuse(pnus: set[str]) -> dict[str, list[str]]:
    source = OUT.parents[1] / "청라" / "인천_토지이용계획" / "AL_D155_28_20260609.csv"
    result: dict[str, list[str]] = defaultdict(list)
    if not source.exists():
        return result
    usecols = ["고유번호", "용도지역지구명"]
    for encoding in ["utf-8-sig", "cp949", "euc-kr"]:
        try:
            for chunk in pd.read_csv(source, usecols=usecols, dtype=str, chunksize=200_000, encoding=encoding):
                sub = chunk[chunk["고유번호"].isin(pnus)]
                for _, row in sub.iterrows():
                    result[str(row["고유번호"])].append(str(row["용도지역지구명"]))
            return result
        except UnicodeDecodeError:
            result.clear()
    return result


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _safe_float(value) -> float:
    try:
        number = float(value or 0)
        return 0.0 if math.isnan(number) else number
    except (TypeError, ValueError):
        return 0.0


def _cheongna_building_metrics(pnus: set[str]) -> dict[str, dict]:
    register_path = OUT.parents[1] / BUILDING_REGISTER_PATHS["cheongna"]
    if not register_path.exists():
        return {}
    register = read_building_register(register_path)
    if "주 부속 코드명" in register.columns:
        register = register[register["주 부속 코드명"].fillna("").str.strip().isin(["", "주건축물"])].copy()
    result: dict[str, dict] = {}
    seen_register_numbers = set()
    for _, row in register.iterrows():
        pnu = normalize_pnu(row.get("PNU"))
        if pnu not in pnus:
            continue
        register_no = str(row.get("건축물관리대장번호") or "")
        if register_no and register_no in seen_register_numbers:
            continue
        if register_no:
            seen_register_numbers.add(register_no)
        main_use = str(row.get("주용도") or "")
        other_use = str(row.get("기타용도") or "")
        building_name = str(row.get("건물명") or "")
        text = f"{main_use} {other_use} {building_name}"
        gfa = parse_float(row.get("연면적(㎡)")) or 0.0
        item = result.setdefault(
            pnu,
            {
                "building_count": 0,
                "office_gfa_m2": 0.0,
                "commercial_gfa_m2": 0.0,
                "total_gfa_m2": 0.0,
                "main_uses": set(),
                "building_names": set(),
                "has_hana_or_finance": False,
                "has_residential_only": False,
                "has_facility_management_only": False,
                "facility_management_names": set(),
            },
        )
        item["building_count"] += 1
        item["total_gfa_m2"] += gfa
        if main_use:
            item["main_uses"].add(main_use)
        if building_name:
            item["building_names"].add(building_name)
        if _contains_any(text, OFFICE_KEYWORDS):
            item["office_gfa_m2"] += gfa
        if _contains_any(text, COMMERCIAL_KEYWORDS):
            item["commercial_gfa_m2"] += gfa
        if _contains_any(text, ["하나", "금융", "은행"]):
            item["has_hana_or_finance"] = True
        if main_use and _contains_any(main_use, RESIDENTIAL_ONLY_KEYWORDS) and not _contains_any(text, OFFICE_KEYWORDS + COMMERCIAL_KEYWORDS):
            item["has_residential_only"] = True
        if _contains_any(text, FACILITY_MANAGEMENT_KEYWORDS):
            item["has_facility_management_only"] = True
            item["facility_management_names"].add(building_name or other_use or main_use)
    return result


def _previous_cheongna_metrics() -> dict | None:
    boundary_path = OUT / "boundaries" / "cheongna_boundary.geojson"
    if not boundary_path.exists():
        return None
    try:
        old_boundary = gpd.read_file(boundary_path).to_crs(CRS_METRIC)
        geom = old_boundary.geometry.iloc[0]
        population, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["population"])
        workers, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["workers"])
        businesses, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["businesses_total"])
        if not businesses:
            businesses, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["businesses"])

        lum = None
        landuse_path = OUT / "analytics" / "landuse_mix.json"
        if landuse_path.exists():
            for row in json.loads(landuse_path.read_text(encoding="utf-8")):
                if row.get("area_key") == "cheongna":
                    lum = row.get("landuse_mix_index")
                    break

        return {
            "area_m2": round(float(geom.area), 1),
            "businesses": round(float(businesses), 1),
            "workers": round(float(workers), 1),
            "population": round(float(population), 1),
            "job_housing_ratio": round(float(workers) / float(population), 3) if population else None,
            "landuse_mix_index": lum,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _cheongna_functional_filter(parcels: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    parcels = parcels.copy()
    parcels["lot_base"] = parcels["JIBUN"].astype(str).str.extract(r"(\d+)")[0].astype(float)
    pnu_set = set(parcels["PNU_NORM"])
    landuse = _read_cheongna_landuse(pnu_set)
    building_metrics = _cheongna_building_metrics(pnu_set)
    previous_metrics = _previous_cheongna_metrics()

    scores = []
    reasons = []
    selected = []
    for _, row in parcels.iterrows():
        pnu = str(row["PNU_NORM"])
        zones = landuse.get(pnu, [])
        zone_text = " ".join(zones)
        metrics = building_metrics.get(pnu, {})
        office_gfa = _safe_float(metrics.get("office_gfa_m2"))
        commercial_gfa = _safe_float(metrics.get("commercial_gfa_m2"))
        total_gfa = _safe_float(metrics.get("total_gfa_m2"))
        building_count = int(metrics.get("building_count", 0) or 0)
        lot_base = _safe_float(row.get("lot_base"))
        jibun_text = str(row.get("JIBUN") or "")

        score = 0.0
        reason = []
        if office_gfa >= 10_000:
            score += 5.0
            reason.append("업무시설 연면적 10,000㎡ 이상")
        elif office_gfa > 0:
            score += 3.0
            reason.append("업무시설 입지")
        if commercial_gfa >= 10_000:
            score += 3.0
            reason.append("상업시설 연면적 10,000㎡ 이상")
        elif commercial_gfa > 0:
            score += 1.5
            reason.append("상업시설 입지")
        if "중심상업지역" in zone_text:
            score += 2.0
            reason.append("중심상업지역")
        elif "일반상업지역" in zone_text:
            score += 1.5
            reason.append("일반상업지역")
        elif "준주거지역" in zone_text:
            score += 0.75
            reason.append("준주거지역")
        if 93 <= lot_base <= 107:
            score += 1.0
            reason.append("청라 업무상업 중심 지번대")
        if 84 <= lot_base <= 90 or 160 <= lot_base <= 170:
            score += 1.0
            reason.append("청라국제도시역/금융업무 후보 지번대")
        if metrics.get("has_hana_or_finance"):
            score += 4.0
            reason.append("하나·금융업무 키워드")

        pure_exclusion = (
            building_count > 0
            and total_gfa > 0
            and metrics.get("has_residential_only")
            and office_gfa <= 0
            and commercial_gfa <= 0
        )
        public_land = _contains_any(zone_text, PUBLIC_EXCLUDE_KEYWORDS) or bool(re.search(r"(공|녹|학)\s*$", jibun_text))
        facility_management_exclusion = (
            public_land
            and building_count > 0
            and metrics.get("has_facility_management_only")
            and office_gfa <= 0
            and total_gfa < 1_000
        )
        public_exclusion = public_land and score < 4.0
        selected_flag = score >= FUNCTIONAL_SCORE_THRESHOLD and not pure_exclusion and not public_exclusion and not facility_management_exclusion
        if facility_management_exclusion:
            reason.append("공원녹지 시설관리용 독립 필지 제외")
        elif public_exclusion:
            reason.append("공원·녹지·학교 등 공공비업무 필지 제외")
        elif pure_exclusion:
            reason.append("순수 주거 필지 제외")

        scores.append(round(score, 2))
        reasons.append(", ".join(reason) if reason else "업무기능 기준 미달")
        selected.append(selected_flag)

    parcels["functional_score"] = scores
    parcels["functional_boundary_reason"] = reasons
    parcels["boundary_rule"] = "실제 업무기능 기반: 건축물 주용도·연면적, 용도지역, 금융/하나 키워드, 업무상업 중심 지번대 종합"
    filtered = parcels[selected].copy()
    excluded_facilities = parcels[
        parcels["functional_boundary_reason"].str.contains("공원녹지 시설관리용 독립 필지 제외", regex=False, na=False)
    ].copy()

    if filtered.empty:
        raise RuntimeError("cheongna: no parcels selected by functional business boundary criteria.")

    building_totals = _cheongna_building_metrics(set(filtered["PNU_NORM"]))
    included_building_count = sum(int(v.get("building_count", 0) or 0) for v in building_totals.values())
    included_office_gfa = sum(_safe_float(v.get("office_gfa_m2")) for v in building_totals.values())
    included_commercial_gfa = sum(_safe_float(v.get("commercial_gfa_m2")) for v in building_totals.values())

    geom = filtered.geometry.union_all()
    workers, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["workers"])
    businesses, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["businesses_total"])
    if not businesses:
        businesses, _ = allocated_sgis_for_geometry("cheongna", geom, SGIS_KEYWORDS["businesses"])

    report = {
        "filter_rule": filtered["boundary_rule"].iloc[0],
        "source_note": "본 시스템은 계획상 용지 기준이 아니라 실제 업무기능이 형성된 지역을 기준으로 업무지구를 정의하였다.",
        "candidate_before_count": int(len(parcels)),
        "selected_count": int(len(filtered)),
        "candidate_area_m2": round(float(parcels.geometry.area.sum()), 1),
        "selected_area_m2": round(float(filtered.geometry.area.sum()), 1),
        "included_building_count": int(included_building_count),
        "included_office_gfa_m2": round(float(included_office_gfa), 1),
        "included_commercial_gfa_m2": round(float(included_commercial_gfa), 1),
        "included_businesses": round(float(businesses), 1),
        "included_workers": round(float(workers), 1),
        "score_threshold": FUNCTIONAL_SCORE_THRESHOLD,
        "exclusion_rule": "공원·녹지·학교·단독주택·공동주택과 음악분수제어실 등 시설관리용 독립 필지는 제외한다. 단, 업무시설 필지 내부 부속건축물은 필지의 주 기능이 업무·상업이면 유지한다.",
        "excluded_facility_management_parcels": [
            {
                "pnu": str(row.get("PNU_NORM")),
                "jibun": str(row.get("JIBUN")),
                "reason": str(row.get("functional_boundary_reason")),
                "area_m2": round(float(row.geometry.area), 1),
                "building_names": sorted(list(building_metrics.get(str(row.get("PNU_NORM")), {}).get("facility_management_names", []))),
            }
            for _, row in excluded_facilities.iterrows()
        ],
        "excluded_facility_management_count": int(len(excluded_facilities)),
        "selected_reason_counts": {
            str(reason): int(count)
            for reason, count in filtered["functional_boundary_reason"].value_counts().head(20).items()
        },
    }
    return filtered, report


def _boundary_comparison(previous: dict | None, current: dict) -> dict | None:
    if not previous or previous.get("error"):
        return previous
    fields = ["area_m2", "businesses", "workers", "job_housing_ratio", "landuse_mix_index"]
    comparison = {"previous": previous, "current": current, "change": {}}
    for field in fields:
        old = previous.get(field)
        new = current.get(field)
        if old is None or new is None:
            comparison["change"][field] = None
        else:
            comparison["change"][field] = {
                "absolute": round(float(new) - float(old), 4),
                "ratio": round((float(new) / float(old) - 1) if float(old) else 0, 4),
            }
    return comparison


def build_boundary(area_key: str) -> dict:
    cfg = AREAS[area_key]
    parcels = gpd.read_file(cfg["cadastre"]).to_crs(CRS_METRIC)
    parcels["PNU_NORM"] = parcels["PNU"].map(normalize_pnu)

    lots = read_xlsx_first_sheet(cfg["xlsx"])
    pnu_col = next((c for c in lots.columns if str(c).lower() == "pnu"), lots.columns[0])
    address_col = next((c for c in lots.columns if "주소" in str(c)), None)
    lots["PNU_NORM"] = lots[pnu_col].map(normalize_pnu)
    wanted = [p for p in lots["PNU_NORM"].dropna().tolist() if p]

    matched_all = parcels[parcels["PNU_NORM"].isin(wanted)].copy()
    filter_report = None
    if area_key == "cheongna":
        matched, filter_report = _cheongna_functional_filter(matched_all)
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
