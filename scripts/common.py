from __future__ import annotations

import csv
import json
import math
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
ANALYSIS_DATE = date(2023, 12, 31)
CRS_METRIC = "EPSG:5186"
CRS_WEB = "EPSG:4326"

AREAS = {
    "pangyo": {
        "label": "제1판교테크노밸리",
        "xlsx": ROOT / "판교" / "판교 소재지_2026-06-17.xlsx",
        "cadastre": ROOT / "판교" / "연속지적도_경기_성남시_분당구" / "LSMD_CONT_LDREG_41135_202606.shp",
        "sgis_code": "31023",
        "source": "성남시 지구단위계획 자료 또는 성남판교 도시지원시설용지 고시 자료",
        "definition": "제1판교테크노밸리는 성남판교 택지개발지구 내 도시지원시설용지 및 업무연구시설이 집중된 제1판교 구역으로 정의한다.",
        "boundary_basis": "성남판교 도시지원시설용지 기준",
        "boundary_note": "업로드 소재지 PNU와 연속지적도를 매칭한 뒤 도시지원시설용지 필지를 병합하였다.",
    },
    "cheongna": {
        "label": "청라국제업무지구",
        "xlsx": ROOT / "청라" / "청라_소재지_2026-06-17.xlsx",
        "cadastre": ROOT / "청라" / "연속지적도_인천_서구" / "LSMD_CONT_LDREG_28260_202606.shp",
        "sgis_code": "23080",
        "source": "건축물대장, 연속지적도, 토지이용계획, SGIS 2023 집계자료를 결합한 실제 업무기능 기반 경계",
        "definition": "청라국제업무지구는 계획상 국제업무용지뿐 아니라 업무시설·상업시설 연면적, 중심·일반상업지역, 금융업무·하나드림타운 관련 필지, 사업체·종사자 집적을 종합해 실제 업무기능이 형성된 업무·상업 중심지로 정의한다.",
        "boundary_basis": "실제 업무기능 기반 필지 클러스터",
        "boundary_note": "순수 공동주택, 학교, 공원, 단독주택 위주 필지와 업무시설이 없는 상업주거지역은 제외하고, 업무시설 또는 상업시설 비중이 높은 필지를 클러스터링하였다.",
    },
}

SGIS_KEYWORDS = {
    "population": "인구총괄(총인구)",
    "households": "가구총괄",
    "workers": "산업분류별(10차_대분류)_종사자수",
    "businesses_total": "산업분류별(10차_대분류)_총괄사업체수",
    "businesses": "산업분류별(10차_대분류)_사업체수",
}


def ensure_dirs() -> None:
    for name in ["boundaries", "parcels", "buildings", "transport", "analytics", "reports", "spatial"]:
        (OUT / name).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_xlsx_first_sheet(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    try:
        return pd.read_excel(path, dtype=str)
    except ImportError:
        return _read_xlsx_stdlib(path)


def _read_xlsx_stdlib(path: Path) -> pd.DataFrame:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//a:t", ns)))
        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in root.findall(".//a:row", ns):
            values = []
            for cell in row.findall("a:c", ns):
                val_node = cell.find("a:v", ns)
                val = "" if val_node is None else val_node.text or ""
                if cell.get("t") == "s" and val:
                    val = shared[int(val)]
                values.append(val)
            rows.append(values)
    return pd.DataFrame(rows[1:], columns=rows[0]).astype(str)


def normalize_pnu(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return re.sub(r"\D", "", text).zfill(19) if re.search(r"\d", text) else ""


def load_boundary(area_key: str) -> gpd.GeoDataFrame:
    return gpd.read_file(OUT / "boundaries" / f"{area_key}_boundary.geojson").to_crs(CRS_METRIC)


def aggregation_boundary_paths() -> dict[str, Path]:
    candidates = {
        "23080": ROOT / "집계구 경계" / "bnd_oa_23080_2025_2Q.shp",
        "31023": ROOT / "집계구 경계3" / "bnd_oa_31023_2025_2Q.shp",
        "11": ROOT / "집계구 경계2" / "bnd_oa_11_2025_2Q.shp",
    }
    return {code: path for code, path in candidates.items() if path.exists()}


def sgis_csv_path(code: str, keyword: str) -> Path | None:
    matches = sorted((ROOT / "인구가구사업체").glob(f"{code}_2023년_{keyword}*.csv"))
    return matches[0] if matches else None


def sgis_csv_by_oa(code: str, keyword: str) -> dict[str, float]:
    path = sgis_csv_path(code, keyword)
    if not path:
        return {}
    values: dict[str, float] = {}
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 4:
                try:
                    values[str(row[1])] = values.get(str(row[1]), 0.0) + float(str(row[-1]).replace(",", ""))
                except ValueError:
                    pass
    return values


def sgis_csv_sum(code: str, keyword: str) -> float:
    return sum(sgis_csv_by_oa(code, keyword).values())


def allocated_sgis_for_geometry(area_key: str, geom, keyword: str) -> tuple[float, dict]:
    code = AREAS[area_key]["sgis_code"]
    path = aggregation_boundary_paths().get(code)
    values = sgis_csv_by_oa(code, keyword)
    if not path:
        return 0.0, {"method": "missing_aggregation_boundary", "features": 0, "sgis_code": code}
    if not values:
        return 0.0, {"method": "missing_sgis_csv", "features": 0, "sgis_code": code}
    return _allocate_from_boundary(path, values, geom, code)


def allocated_sgis_for_geometry_all_available(geom, keyword: str) -> tuple[float, dict]:
    total = 0.0
    meta = {"method": "aggregation_area_weighted_multi_region", "regions": {}, "missing_value_regions": []}
    for code, path in aggregation_boundary_paths().items():
        values = sgis_csv_by_oa(code, keyword)
        if not values:
            meta["missing_value_regions"].append(code)
            continue
        value, region_meta = _allocate_from_boundary(path, values, geom, code)
        total += value
        meta["regions"][code] = region_meta
    return total, meta


def _allocate_from_boundary(path: Path, values: dict[str, float], geom, code: str) -> tuple[float, dict]:
    oa = gpd.read_file(path).to_crs(CRS_METRIC)
    bbox = gpd.GeoSeries([geom], crs=CRS_METRIC).total_bounds
    oa = oa.cx[bbox[0] : bbox[2], bbox[1] : bbox[3]].copy()
    total = 0.0
    used = 0
    overlap_area = 0.0
    for _, row in oa.iterrows():
        source_area = row.geometry.area
        if source_area <= 0:
            continue
        inter_area = row.geometry.intersection(geom).area
        if inter_area <= 0:
            continue
        used += 1
        overlap_area += inter_area
        total += values.get(str(row["TOT_OA_CD"]), 0.0) * (inter_area / source_area)
    return total, {
        "method": "aggregation_area_weighted",
        "sgis_code": code,
        "features": used,
        "overlap_area_m2": round(overlap_area, 1),
    }


def rough_compactness(area_m2: float, perimeter_m: float) -> float:
    if perimeter_m <= 0:
        return 0.0
    return max(0.0, min(1.0, (4 * math.pi * area_m2) / (perimeter_m * perimeter_m)))
