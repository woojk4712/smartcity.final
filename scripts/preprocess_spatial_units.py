from __future__ import annotations

import re
import zipfile
import math
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import pandas as pd

from common import AREAS, CRS_METRIC, CRS_WEB, OUT, ensure_dirs, normalize_pnu, write_json


BUILDING_REGISTER_PATHS = {
    "pangyo": Path("판교") / "판교_건축물대장" / "건축물조서.xlsx",
    "cheongna": Path("청라") / "인천광역시 서구 경서동 일원_건축물대장" / "건축물조서.xlsx",
}

HEADER_ROW_INDEX = 1
MAIN_BUILDING_VALUE = "주건축물"


def include_parcel_by_overlap(parcel_geom, boundary_geom, threshold: float = 0.5) -> tuple[bool, float, float]:
    original_area = parcel_geom.area
    overlap_area = parcel_geom.intersection(boundary_geom).area
    ratio = overlap_area / original_area if original_area else 0.0
    return ratio >= threshold, overlap_area, ratio


def allocate_by_area(value: float, source_area: float, overlap_area: float) -> float:
    return 0.0 if source_area <= 0 else value * (overlap_area / source_area)


def centroid_inside(geom, boundary_geom) -> bool:
    return boundary_geom.contains(geom.centroid)


def xlsx_rows(path: Path) -> list[list[str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//a:t", ns)))

        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in root.findall(".//a:row", ns):
            values: dict[int, str] = {}
            max_col = -1
            for fallback_index, cell in enumerate(row.findall("a:c", ns)):
                ref = cell.get("r", "")
                col_index = column_index(ref) if ref else fallback_index
                max_col = max(max_col, col_index)
                value_node = cell.find("a:v", ns)
                value = "" if value_node is None else value_node.text or ""
                if cell.get("t") == "s" and value:
                    value = shared[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//a:t", ns))
                values[col_index] = value
            if max_col >= 0:
                rows.append([values.get(i, "") for i in range(max_col + 1)])
    return rows


def column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    value = 0
    for letter in letters:
        value = value * 26 + (ord(letter) - ord("A") + 1)
    return max(value - 1, 0)


def read_building_register(path: Path) -> pd.DataFrame:
    rows = xlsx_rows(path)
    headers = [h.strip() for h in rows[HEADER_ROW_INDEX]]
    records = []
    for row in rows[HEADER_ROW_INDEX + 1 :]:
        padded = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded[: len(headers)])))
    return pd.DataFrame(records)


def parse_float(value) -> float | None:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
        return None if math.isnan(number) else number
    except ValueError:
        return None


def lot_key(value) -> str:
    text = "" if value is None else str(value).strip()
    match = re.search(r"(\d+)(?:\s*-\s*(\d+))?", text)
    if not match:
        return ""
    main = str(int(match.group(1)))
    sub = match.group(2)
    return f"{main}-{int(sub)}" if sub else main


def parcel_lot_key(value) -> str:
    text = re.sub(r"[^0-9-]", "", "" if value is None else str(value))
    return lot_key(text)


def building_properties(row: pd.Series, match_method: str) -> dict:
    return {
        "PNU": normalize_pnu(row.get("PNU")),
        "address": row.get("주소") or "",
        "road_address": row.get("도로명주소") or "",
        "lot": row.get("지번") or "",
        "building_register_no": row.get("건축물관리대장번호") or "",
        "building_name": row.get("건물명") or "",
        "dong_name": row.get("동명칭") or "",
        "main_or_annex": row.get("주 부속 코드명") or "",
        "main_use": row.get("주용도") or "",
        "other_use": row.get("기타용도") or "",
        "land_area_m2": parse_float(row.get("대지면적(㎡)")),
        "building_area_m2": parse_float(row.get("건축면적(㎡)")),
        "building_coverage_ratio": parse_float(row.get("건폐율(%)")),
        "gross_floor_area_m2": parse_float(row.get("연면적(㎡)")),
        "far_calc_floor_area_m2": parse_float(row.get("용적률산정용연면적(㎡)")),
        "floor_area_ratio": parse_float(row.get("용적률(%)")),
        "households": parse_float(row.get("가구수(가구)")),
        "units": parse_float(row.get("세대수(세대)")),
        "ground_floors": parse_float(row.get("지상층수")),
        "underground_floors": parse_float(row.get("지하층수")),
        "approval_date": row.get("사용승인일") or "",
        "source": f"building_register_xlsx_{match_method}",
    }


def build_building_join(area_key: str) -> dict:
    root = OUT.parents[1]
    xlsx_path = root / BUILDING_REGISTER_PATHS[area_key]
    parcels_path = OUT / "parcels" / f"{area_key}_matched_parcels.geojson"
    if not xlsx_path.exists() or not parcels_path.exists():
        empty = gpd.GeoDataFrame([], geometry=[], crs=CRS_WEB)
        empty.to_file(OUT / "buildings" / f"{area_key}_buildings.geojson", driver="GeoJSON")
        return {"area_key": area_key, "building_count": 0, "note": "building register or parcels missing"}

    parcels = gpd.read_file(parcels_path).to_crs(CRS_METRIC)
    pnu_col = "PNU_NORM" if "PNU_NORM" in parcels.columns else "PNU"
    parcels[pnu_col] = parcels[pnu_col].map(normalize_pnu)
    parcels["lot_key"] = parcels.get("JIBUN", "").map(parcel_lot_key)
    parcel_by_pnu = {row[pnu_col]: row for _, row in parcels.iterrows() if row[pnu_col]}
    parcel_by_lot = {row["lot_key"]: row for _, row in parcels.iterrows() if row["lot_key"]}

    register = read_building_register(xlsx_path)
    if "주 부속 코드명" in register.columns:
        register = register[register["주 부속 코드명"].fillna("").str.strip().isin(["", MAIN_BUILDING_VALUE])].copy()

    features = []
    matched_by_pnu = 0
    matched_by_lot = 0
    unmatched_rows = []
    seen_register_numbers = set()
    for _, row in register.iterrows():
        register_no = str(row.get("건축물관리대장번호") or "")
        if register_no and register_no in seen_register_numbers:
            continue
        pnu = normalize_pnu(row.get("PNU"))
        parcel = parcel_by_pnu.get(pnu)
        match_method = "pnu"
        if parcel is not None:
            matched_by_pnu += 1
        else:
            key = lot_key(row.get("지번"))
            parcel = parcel_by_lot.get(key)
            match_method = "lot"
            if parcel is not None:
                matched_by_lot += 1

        if parcel is None:
            unmatched_rows.append({"PNU": pnu, "lot": row.get("지번") or "", "building_name": row.get("건물명") or ""})
            continue

        if register_no:
            seen_register_numbers.add(register_no)
        props = building_properties(row, match_method)
        props["matched_parcel_pnu"] = parcel[pnu_col]
        props["matched_parcel_lot"] = parcel.get("JIBUN", "")
        features.append(props | {"geometry": parcel.geometry.centroid})

    buildings = gpd.GeoDataFrame(features, geometry="geometry", crs=CRS_METRIC)
    buildings.to_crs(CRS_WEB).to_file(OUT / "buildings" / f"{area_key}_buildings.geojson", driver="GeoJSON")

    gross_floor_area = 0.0
    far_values = []
    for value in buildings.get("gross_floor_area_m2", []):
        try:
            number = float(value)
            if not math.isnan(number):
                gross_floor_area += number
        except (TypeError, ValueError):
            pass
    for value in buildings.get("floor_area_ratio", []):
        try:
            number = float(value)
            if not math.isnan(number) and number > 0:
                far_values.append(number)
        except (TypeError, ValueError):
            pass
    return {
        "area_key": area_key,
        "building_source": str(xlsx_path),
        "building_count": int(len(buildings)),
        "matched_by_pnu": matched_by_pnu,
        "matched_by_lot": matched_by_lot,
        "unmatched_register_rows": int(len(unmatched_rows)),
        "unmatched_sample": unmatched_rows[:30],
        "gross_floor_area_m2": round(gross_floor_area, 1),
        "avg_floor_area_ratio": round(sum(far_values) / len(far_values), 1) if far_values else None,
        "method": "building register xlsx matched to analysis parcels by PNU, falling back to lot number",
    }


def main() -> None:
    ensure_dirs()
    reports = [build_building_join(key) for key in AREAS]
    write_json(OUT / "reports" / "spatial_join_report.json", reports)
    for report in reports:
        print(
            f"{report['area_key']}: buildings={report.get('building_count', 0)} "
            f"pnu={report.get('matched_by_pnu', 0)} lot={report.get('matched_by_lot', 0)}"
        )


if __name__ == "__main__":
    main()
