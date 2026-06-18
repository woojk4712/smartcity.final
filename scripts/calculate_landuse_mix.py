from __future__ import annotations

import math
import zipfile
from collections import defaultdict

import geopandas as gpd
import pandas as pd

from common import AREAS, OUT, ROOT, ensure_dirs, write_json

CLASSES = ["업무", "상업", "주거", "교육연구", "공공", "기타"]
LANDUSE_SOURCES = {
    "pangyo": ROOT / "판교" / "판교_토지이용계획.zip",
    "cheongna": ROOT / "청라" / "인천_토지이용계획" / "AL_D155_28_20260609.csv",
}


def entropy(shares: dict[str, float]) -> float:
    values = [max(0.0, shares.get(k, 0.0)) for k in CLASSES]
    total = sum(values)
    if total <= 0:
        return 0.0
    return -sum((v / total) * math.log(v / total) for v in values if v > 0) / math.log(len(CLASSES))


def classify_zone(name: str) -> str:
    if "상업" in name or "업무" in name:
        return "상업"
    if "주거" in name:
        return "주거"
    if "공업" in name or "산업" in name:
        return "업무"
    if "학교" in name or "교육" in name or "연구" in name:
        return "교육연구"
    if "공공" in name or "보전" in name or "녹지" in name or "공원" in name:
        return "공공"
    return "기타"


def classify_building_use(name: str) -> str:
    if not name:
        return "기타"
    if "업무" in name or "공장" in name or "지식산업" in name:
        return "업무"
    if "판매" in name or "근린생활" in name or "상가" in name or "숙박" in name:
        return "상업"
    if "주택" in name or "공동주택" in name or "다가구" in name or "아파트" in name:
        return "주거"
    if "교육" in name or "연구" in name or "학교" in name:
        return "교육연구"
    if "공공" in name or "문화" in name or "의료" in name or "운동" in name or "종교" in name:
        return "공공"
    return "기타"


def read_landuse_records(area_key: str, pnu_set: set[str]) -> dict[str, list[str]]:
    source = LANDUSE_SOURCES.get(area_key)
    result: dict[str, list[str]] = defaultdict(list)
    if not source or not source.exists():
        return result

    usecols = ["고유번호", "용도지역지구명"]

    def make_chunks(encoding: str):
        if source.suffix.lower() == ".zip":
            zf = zipfile.ZipFile(source)
            return pd.read_csv(zf.open(zf.namelist()[0]), usecols=usecols, dtype=str, chunksize=200_000, encoding=encoding)
        return pd.read_csv(source, usecols=usecols, dtype=str, chunksize=200_000, encoding=encoding)

    for encoding in ["utf-8-sig", "cp949", "euc-kr"]:
        try:
            chunks = make_chunks(encoding)
            for chunk in chunks:
                chunk = chunk[chunk["고유번호"].isin(pnu_set)]
                for _, row in chunk.iterrows():
                    result[str(row["고유번호"])].append(str(row["용도지역지구명"]))
            return result
        except UnicodeDecodeError:
            result.clear()
            continue

    return result


def building_lum(area_key: str) -> tuple[float | None, list[dict], str]:
    path = OUT / "buildings" / f"{area_key}_buildings.geojson"
    if not path.exists():
        return None, [], "building_data_missing"
    buildings = gpd.read_file(path)
    class_area = defaultdict(float)
    for _, row in buildings.iterrows():
        try:
            gross_floor_area = float(row.get("gross_floor_area_m2") or 0)
        except (TypeError, ValueError):
            gross_floor_area = 0
        if math.isnan(gross_floor_area) or gross_floor_area <= 0:
            continue
        class_area[classify_building_use(str(row.get("main_use") or ""))] += gross_floor_area

    total = sum(class_area.values())
    if total <= 0:
        return None, [], "building_gross_floor_area_missing"
    shares = {name: class_area.get(name, 0.0) / total for name in CLASSES}
    classes = [{"class": name, "share": round(shares[name], 4), "gross_floor_area_m2": round(class_area[name], 1)} for name in CLASSES]
    return round(entropy(shares), 3), classes, "building_main_use_gross_floor_area"


def zoning_lum(area_key: str) -> dict:
    parcels = gpd.read_file(OUT / "parcels" / f"{area_key}_matched_parcels.geojson").to_crs("EPSG:5186")
    parcels["area_m2"] = parcels.geometry.area
    pnu_col = "PNU_NORM" if "PNU_NORM" in parcels.columns else "PNU"
    parcels[pnu_col] = parcels[pnu_col].astype(str)

    records = read_landuse_records(area_key, set(parcels[pnu_col]))
    class_area = defaultdict(float)
    detail_area = defaultdict(float)
    unmatched_area = 0.0
    for _, parcel in parcels.iterrows():
        zones = records.get(str(parcel[pnu_col]), [])
        if not zones:
            unmatched_area += float(parcel["area_m2"])
            class_area["기타"] += float(parcel["area_m2"])
            detail_area["미매칭"] += float(parcel["area_m2"])
            continue
        split_area = float(parcel["area_m2"]) / len(zones)
        for zone in zones:
            class_area[classify_zone(zone)] += split_area
            detail_area[zone] += split_area

    area_m2 = float(parcels["area_m2"].sum())
    shares = {name: class_area.get(name, 0.0) / area_m2 if area_m2 else 0.0 for name in CLASSES}
    return {
        "classes": [{"class": k, "share": round(shares[k], 4), "area_m2": round(area_m2 * shares[k], 1)} for k in CLASSES],
        "zone_details": [
            {"zone": zone, "area_m2": round(area, 1), "share": round(area / area_m2, 4) if area_m2 else 0}
            for zone, area in sorted(detail_area.items(), key=lambda item: item[1], reverse=True)[:20]
        ],
        "unmatched_area_m2": round(unmatched_area, 1),
        "zoning_landuse_mix_index": round(entropy(shares), 3),
    }


def main() -> None:
    ensure_dirs()
    rows = []
    for key, cfg in AREAS.items():
        zoning = zoning_lum(key)
        building_index, building_classes, building_method = building_lum(key)
        selected_index = building_index if building_index is not None else zoning["zoning_landuse_mix_index"]
        rows.append(
            {
                "area_key": key,
                "label": cfg["label"],
                "source": "landuse_plan_pnu_join_area_weighted; building_register_pnu_or_lot_join",
                "classes": zoning["classes"],
                "zone_details": zoning["zone_details"],
                "unmatched_area_m2": zoning["unmatched_area_m2"],
                "zoning_landuse_mix_index": zoning["zoning_landuse_mix_index"],
                "building_landuse_mix_index": building_index,
                "building_use_classes": building_classes,
                "landuse_mix_index": selected_index,
                "lum_method": building_method if building_index is not None else "zoning_area",
            }
        )
    write_json(OUT / "analytics" / "landuse_mix.json", rows)
    for row in rows:
        print(
            f"{row['area_key']}: LUM={row['landuse_mix_index']} "
            f"method={row['lum_method']} unmatched={row['unmatched_area_m2']}"
        )


if __name__ == "__main__":
    main()
