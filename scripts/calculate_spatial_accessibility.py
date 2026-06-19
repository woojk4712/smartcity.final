from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from calculate_accessibility import load_active_network
from common import AREAS, CRS_METRIC, OUT, ROOT, ensure_dirs, load_boundary, write_json


BUS_SOURCES = {
    "pangyo": ROOT / "판교" / "경기도 성남시 버스정류장 현황_20240329.csv",
    "cheongna": ROOT / "청라" / "인천광역시_정류장별 이용승객현황_20231130.csv",
}

ROAD_FILE_KEYWORDS = ["road", "roads", "도로", "osm"]
IC_FILE_KEYWORDS = ["ic", "interchange", "고속도로", "나들목"]
SPATIAL_EXTENSIONS = {".shp", ".geojson", ".gpkg"}


def read_csv_any(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    for encoding in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(path, dtype=str, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, encoding="utf-8", encoding_errors="ignore")


def first_existing(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def bus_stops_for_area(area_key: str, boundary: gpd.GeoDataFrame) -> dict:
    source = BUS_SOURCES.get(area_key)
    if not source:
        return {"count": None, "density": None, "source": None, "note": "정류장 원자료 경로가 설정되지 않음"}
    source_label = str(source.relative_to(ROOT)) if source.exists() else str(source)
    df = read_csv_any(source)
    if df is None:
        return {"count": None, "density": None, "source": source_label, "note": "정류장 원자료 없음"}

    lon_col = first_existing(list(df.columns), ["경도", "lon", "lng", "longitude", "x"])
    lat_col = first_existing(list(df.columns), ["위도", "lat", "latitude", "y"])
    if not lon_col or not lat_col:
        return {
            "count": None,
            "density": None,
            "source": source_label,
            "note": "정류장별 승하차 원자료에 좌표 컬럼이 없어 구역 내 공간 포함 여부를 계산하지 않음",
        }

    lon = pd.to_numeric(df[lon_col].astype(str).str.strip(), errors="coerce")
    lat = pd.to_numeric(df[lat_col].astype(str).str.strip(), errors="coerce")
    valid = df[lon.notna() & lat.notna()].copy()
    valid[lon_col] = lon[lon.notna() & lat.notna()]
    valid[lat_col] = lat[lon.notna() & lat.notna()]

    id_col = first_existing(list(valid.columns), ["정류장번호(ID)", "정류소아이디", "정류장ID", "정류소ID", "표준정류장ID"])
    if id_col:
        valid = valid.drop_duplicates(subset=[id_col])
    else:
        valid = valid.drop_duplicates(subset=[lon_col, lat_col])

    stops = gpd.GeoDataFrame(valid, geometry=gpd.points_from_xy(valid[lon_col], valid[lat_col]), crs="EPSG:4326").to_crs(CRS_METRIC)
    within = stops[stops.geometry.within(boundary.geometry.iloc[0])]
    area_km2 = float(boundary.geometry.area.iloc[0]) / 1_000_000
    count = int(len(within))
    return {
        "count": count,
        "density": round(count / area_km2, 2) if area_km2 else None,
        "source": source_label,
        "note": f"{source.name}의 위경도 좌표를 구역 경계와 공간조인",
    }


def find_spatial_files(keywords: list[str]) -> list[Path]:
    skip_parts = {"node_modules", "dist", "pages_deploy", "public", "data", ".git"}
    matches = []
    for path in ROOT.rglob("*"):
        if path.suffix.lower() not in SPATIAL_EXTENSIONS:
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        lower = path.name.lower()
        if any(keyword.lower() in lower for keyword in keywords):
            matches.append(path)
    return sorted(matches)


def road_metrics(boundary: gpd.GeoDataFrame) -> dict:
    files = find_spatial_files(ROAD_FILE_KEYWORDS)
    if not files:
        return {
            "length_km": None,
            "density": None,
            "source": None,
            "note": "OSM 도로망 또는 도로 중심선 공간파일이 없어 산정하지 않음",
        }
    area_km2 = float(boundary.geometry.area.iloc[0]) / 1_000_000
    total_m = 0.0
    used = []
    geom = boundary.geometry.iloc[0]
    for path in files:
        try:
            roads = gpd.read_file(path).to_crs(CRS_METRIC)
        except Exception:
            continue
        roads = roads[roads.geometry.notna()].copy()
        if roads.empty:
            continue
        total_m += float(roads.geometry.intersection(geom).length.sum())
        used.append(str(path.relative_to(ROOT)))
    length_km = total_m / 1000
    return {
        "length_km": round(length_km, 3),
        "density": round(length_km / area_km2, 3) if area_km2 else None,
        "source": used,
        "note": "도로 중심선과 구역 경계 교차 길이 합산",
    }


def nearest_ic(boundary: gpd.GeoDataFrame) -> dict:
    files = find_spatial_files(IC_FILE_KEYWORDS)
    if not files:
        return {
            "distance_km": None,
            "name": None,
            "source": None,
            "note": "고속도로 IC 위치 공간파일이 없어 산정하지 않음",
        }
    centroid = boundary.geometry.iloc[0].centroid
    best = None
    for path in files:
        try:
            gdf = gpd.read_file(path).to_crs(CRS_METRIC)
        except Exception:
            continue
        for _, row in gdf.iterrows():
            if row.geometry is None:
                continue
            distance_km = float(row.geometry.distance(centroid)) / 1000
            name = row.get("name") or row.get("명칭") or row.get("IC명") or row.get("시설명")
            candidate = (distance_km, name, path)
            if best is None or candidate[0] < best[0]:
                best = candidate
    if best is None:
        return {"distance_km": None, "name": None, "source": [str(p.relative_to(ROOT)) for p in files], "note": "IC geometry 없음"}
    return {
        "distance_km": round(best[0], 2),
        "name": best[1] or "이름 없음",
        "source": str(best[2].relative_to(ROOT)),
        "note": "구역 중심점과 최근접 IC geometry 간 거리",
    }


def station_area_ratios(boundary: gpd.GeoDataFrame, stations: gpd.GeoDataFrame) -> dict:
    geom = boundary.geometry.iloc[0]
    area_m2 = float(geom.area)
    ratios = {}
    counts = {}
    for radius in [500, 1000]:
        buffers = stations.geometry.buffer(radius).union_all()
        inter_area = float(buffers.intersection(geom).area)
        ratios[f"ratio_{radius}m"] = round((inter_area / area_m2) * 100, 2) if area_m2 else None
        counts[f"station_count_{radius}m"] = int((stations.geometry.distance(geom) <= radius).sum())
    return {**ratios, **counts}


def main() -> None:
    ensure_dirs()
    stations, _ = load_active_network()
    rows = []
    validation = {}
    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        area_km2 = float(boundary.geometry.area.iloc[0]) / 1_000_000
        bus = bus_stops_for_area(key, boundary)
        road = road_metrics(boundary)
        ic = nearest_ic(boundary)
        station = station_area_ratios(boundary, stations)

        row = {
            "area_key": key,
            "label": cfg["label"],
            "area_km2": round(area_km2, 4),
            "bus_stop_count": bus["count"],
            "bus_stop_density_per_km2": bus["density"],
            "bus_stop_source": bus["source"],
            "bus_stop_note": bus["note"],
            "road_length_km": road["length_km"],
            "road_network_density_km_per_km2": road["density"],
            "road_source": road["source"],
            "road_note": road["note"],
            "nearest_highway_ic_km": ic["distance_km"],
            "nearest_highway_ic_name": ic["name"],
            "ic_source": ic["source"],
            "ic_note": ic["note"],
            "station_area_ratio_500m": station["ratio_500m"],
            "station_area_ratio_1km": station["ratio_1000m"],
            "station_count_500m": station["station_count_500m"],
            "station_count_1km": station["station_count_1000m"],
            "station_catchment_source": "subway_network/network/nodes.tsv; 2023-12-31 기준 운영 중 역",
            "method": "구역 경계는 EPSG:5186에서 면적·거리 계산 후 결과 GeoJSON/JSON 저장",
        }
        rows.append(row)
        validation[key] = row
        print(
            f"{key}: bus_density={row['bus_stop_density_per_km2']} "
            f"road_density={row['road_network_density_km_per_km2']} "
            f"station_500m={row['station_area_ratio_500m']}"
        )

    write_json(OUT / "analytics" / "spatial_accessibility.json", rows)
    write_json(OUT / "reports" / "spatial_accessibility_validation_report.json", validation)


if __name__ == "__main__":
    main()
