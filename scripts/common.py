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
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
ANALYSIS_DATE = date(2023, 12, 31)
CRS_METRIC = "EPSG:5186"
CRS_WEB = "EPSG:4326"


AREAS = {
    "pangyo": {
        "label": "판교 1테크노밸리",
        "xlsx": ROOT / "판교" / "판교 소재지_2026-06-17.xlsx",
        "cadastre": ROOT / "판교" / "연속지적도_경기_성남시_분당구" / "LSMD_CONT_LDREG_41135_202606.shp",
        "sgis_code": "31023",
        "center": [37.4007, 127.1089],
    },
    "cheongna": {
        "label": "청라국제도시",
        "xlsx": ROOT / "청라" / "청라_소재지_2026-06-17.xlsx",
        "cadastre": ROOT / "청라" / "연속지적도_인천_서구" / "LSMD_CONT_LDREG_28260_202606.shp",
        "sgis_code": "23080",
        "center": [37.5333, 126.6497],
    },
}


def ensure_dirs() -> None:
    for name in ["boundaries", "parcels", "buildings", "transport", "analytics", "reports", "spatial"]:
        (OUT / name).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_xlsx_first_sheet(path: Path) -> pd.DataFrame:
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
    header = rows[0]
    return pd.DataFrame(rows[1:], columns=header).astype(str)


def normalize_pnu(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return re.sub(r"\D", "", text).zfill(19) if re.search(r"\d", text) else ""


def sgis_csv_sum(code: str, keyword: str) -> float:
    folder = ROOT / "인구가구사업체"
    matches = sorted(folder.glob(f"{code}_2023년_{keyword}*.csv"))
    if not matches:
        return 0.0
    total = 0.0
    with matches[0].open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            if row and len(row) >= 4:
                try:
                    total += float(str(row[-1]).replace(",", ""))
                except ValueError:
                    pass
    return total


def sgis_csv_by_oa(code: str, keyword: str) -> dict[str, float]:
    folder = ROOT / "인구가구사업체"
    matches = sorted(folder.glob(f"{code}_2023년_{keyword}*.csv"))
    if not matches:
        return {}
    values: dict[str, float] = {}
    with matches[0].open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            if row and len(row) >= 4:
                try:
                    values[str(row[1])] = values.get(str(row[1]), 0.0) + float(str(row[-1]).replace(",", ""))
                except ValueError:
                    pass
    return values


def aggregation_boundary_path(area_key: str) -> Path | None:
    candidates = {
        "pangyo": ROOT / "집계구 경계3" / "bnd_oa_31023_2025_2Q.shp",
        "cheongna": ROOT / "집계구 경계" / "bnd_oa_23080_2025_2Q.shp",
    }
    path = candidates.get(area_key)
    return path if path and path.exists() else None


def allocated_sgis_for_geometry(area_key: str, geom, keyword: str) -> tuple[float, dict]:
    path = aggregation_boundary_path(area_key)
    if not path:
        return 0.0, {"method": "missing_aggregation_boundary", "features": 0}
    values = sgis_csv_by_oa(AREAS[area_key]["sgis_code"], keyword)
    if not values:
        return 0.0, {"method": "missing_sgis_csv", "features": 0}
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
    return total, {"method": "aggregation_area_weighted", "features": used, "overlap_area_m2": round(overlap_area, 1)}


def load_boundary(area_key: str) -> gpd.GeoDataFrame:
    return gpd.read_file(OUT / "boundaries" / f"{area_key}_boundary.geojson").to_crs(CRS_METRIC)


def rough_compactness(area_m2: float, perimeter_m: float) -> float:
    if perimeter_m <= 0:
        return 0.0
    return max(0.0, min(1.0, (4 * math.pi * area_m2) / (perimeter_m * perimeter_m)))
