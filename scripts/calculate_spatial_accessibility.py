from __future__ import annotations

import json
import time

import geopandas as gpd
import requests
from shapely.geometry import LineString, Point, Polygon

from calculate_accessibility import load_active_network
from common import AREAS, CRS_METRIC, OUT, ensure_dirs, load_boundary, write_json


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_HEADERS = {
    "User-Agent": "smartcity-final-gis/1.0 (https://github.com/woojk4712/smartcity.final)",
    "Accept": "application/json,*/*",
}
OSM_CACHE_DIR = OUT / "osm"
ROAD_HIGHWAY_CLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
}


def bbox_for(boundary: gpd.GeoDataFrame, buffer_m: float = 0) -> tuple[float, float, float, float]:
    geom = boundary.geometry.iloc[0]
    if buffer_m:
        geom = geom.buffer(buffer_m)
    minx, miny, maxx, maxy = gpd.GeoSeries([geom], crs=CRS_METRIC).to_crs("EPSG:4326").total_bounds
    return float(miny), float(minx), float(maxy), float(maxx)


def overpass_query(query: str, cache_name: str) -> dict:
    OSM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = OSM_CACHE_DIR / cache_name
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            response = requests.post(url, data={"data": query}, headers=OVERPASS_HEADERS, timeout=180)
            response.raise_for_status()
            data = response.json()
            data["_overpass_url"] = url
            break
        except Exception as exc:
            last_error = exc
    else:
        raise RuntimeError(f"Overpass API request failed: {last_error}") from last_error
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # Keep the public Overpass endpoint comfortable when both areas are fetched in one run.
    time.sleep(1)
    return data


def query_for(kind: str, bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    box = f"{south},{west},{north},{east}"
    if kind == "bus":
        return f"""
        [out:json][timeout:180];
        (
          node["highway"="bus_stop"]({box});
          node["amenity"="bus_station"]({box});
          way["amenity"="bus_station"]({box});
          relation["amenity"="bus_station"]({box});
        );
        out center geom;
        """
    if kind == "road":
        return f"""
        [out:json][timeout:180];
        (
          way["highway"]({box});
        );
        out geom;
        """
    if kind == "ic":
        return f"""
        [out:json][timeout:180];
        (
          node["highway"="motorway_junction"]({box});
        );
        out body;
        """
    raise ValueError(kind)


def element_point(element: dict):
    if "lat" in element and "lon" in element:
        return Point(float(element["lon"]), float(element["lat"]))
    if "center" in element:
        return Point(float(element["center"]["lon"]), float(element["center"]["lat"]))
    if element.get("geometry"):
        coords = [(pt["lon"], pt["lat"]) for pt in element["geometry"] if "lon" in pt and "lat" in pt]
        if len(coords) >= 3:
            return Polygon(coords).representative_point()
        if coords:
            return Point(coords[0])
    return None


def osm_points(data: dict, tag_filter=None) -> gpd.GeoDataFrame:
    rows = []
    seen = set()
    for element in data.get("elements", []):
        tags = element.get("tags") or {}
        if tag_filter and not tag_filter(tags):
            continue
        geom = element_point(element)
        if geom is None:
            continue
        osm_id = f"{element.get('type')}/{element.get('id')}"
        if osm_id in seen:
            continue
        seen.add(osm_id)
        rows.append({"osm_id": osm_id, "name": tags.get("name"), "tags": tags, "geometry": geom})
    if not rows:
        return gpd.GeoDataFrame(columns=["osm_id", "name", "tags"], geometry=[], crs=CRS_METRIC)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(CRS_METRIC)


def osm_lines(data: dict) -> gpd.GeoDataFrame:
    rows = []
    for element in data.get("elements", []):
        tags = element.get("tags") or {}
        highway = tags.get("highway")
        if highway not in ROAD_HIGHWAY_CLASSES:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in element.get("geometry", []) if "lon" in pt and "lat" in pt]
        if len(coords) < 2:
            continue
        rows.append(
            {
                "osm_id": f"{element.get('type')}/{element.get('id')}",
                "name": tags.get("name"),
                "highway": highway,
                "geometry": LineString(coords),
            }
        )
    if not rows:
        return gpd.GeoDataFrame(columns=["osm_id", "name", "highway"], geometry=[], crs=CRS_METRIC)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(CRS_METRIC)


def bus_stops_for_area(area_key: str, boundary: gpd.GeoDataFrame) -> dict:
    data = overpass_query(query_for("bus", bbox_for(boundary, 500)), f"{area_key}_osm_v2_bus.json")
    stops = osm_points(data)
    within = stops[stops.geometry.within(boundary.geometry.iloc[0])]
    area_km2 = float(boundary.geometry.area.iloc[0]) / 1_000_000
    count = int(len(within))
    duplicate_ids = int(len(stops) - stops["osm_id"].nunique()) if not stops.empty else 0
    return {
        "count": count,
        "density": round(count / area_km2, 2) if area_km2 else None,
        "source": "OpenStreetMap Overpass API: highway=bus_stop, amenity=bus_station",
        "note": "OSM bus_stop/bus_station point 또는 대표점을 구역 경계와 공간조인",
        "validation": {
            "query_bbox_buffer_m": 500,
            "source_crs": "EPSG:4326",
            "calculation_crs": CRS_METRIC,
            "raw_osm_element_count": int(len(data.get("elements", []))),
            "unique_point_count": int(len(stops)),
            "duplicate_osm_id_count": duplicate_ids,
            "within_boundary_count": count,
            "method": "OSM point/representative point transformed to metric CRS, counted only when within analysis polygon",
        },
    }


def road_metrics(area_key: str, boundary: gpd.GeoDataFrame) -> dict:
    data = overpass_query(query_for("road", bbox_for(boundary, 500)), f"{area_key}_osm_v2_roads.json")
    roads = osm_lines(data)
    area_km2 = float(boundary.geometry.area.iloc[0]) / 1_000_000
    geom = boundary.geometry.iloc[0]
    duplicate_ids = int(len(roads) - roads["osm_id"].nunique()) if not roads.empty else 0
    clipped = roads.geometry.intersection(geom) if not roads.empty else []
    clipped_lengths = [float(line.length) for line in clipped if not line.is_empty] if not roads.empty else []
    total_m = sum(clipped_lengths)
    length_km = total_m / 1000
    return {
        "length_km": round(length_km, 3),
        "density": round(length_km / area_km2, 3) if area_km2 else None,
        "source": "OpenStreetMap Overpass API: highway=*",
        "note": f"OSM highway 중 {', '.join(sorted(ROAD_HIGHWAY_CLASSES))}를 구역 경계로 clip 후 길이 합산",
        "validation": {
            "query_bbox_buffer_m": 500,
            "source_crs": "EPSG:4326",
            "calculation_crs": CRS_METRIC,
            "raw_osm_element_count": int(len(data.get("elements", []))),
            "unique_road_way_count": int(len(roads)),
            "duplicate_osm_id_count": duplicate_ids,
            "clipped_segment_count": int(sum(1 for length in clipped_lengths if length > 0)),
            "method": "OSM highway LineString transformed to metric CRS, clipped by polygon, summed once per unique OSM way id",
            "boundary_overlap_note": "도로 중심선이 경계선 위에 놓인 경우 intersection 길이에 포함된다. 동일 OSM way id 중복은 제거되어 있으며, 왕복 분리 차로는 별도 centerline으로 집계된다.",
        },
    }


def nearest_ic(area_key: str, boundary: gpd.GeoDataFrame) -> dict:
    data = overpass_query(query_for("ic", bbox_for(boundary, 30_000)), f"{area_key}_osm_v2_motorway_junctions.json")
    junctions = osm_points(data, lambda tags: tags.get("highway") == "motorway_junction")
    centroid = boundary.geometry.iloc[0].centroid
    best = None
    for _, row in junctions.iterrows():
        distance_km = float(row.geometry.distance(centroid)) / 1000
        candidate = (distance_km, row.get("name"))
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:
        return {
            "distance_km": None,
            "name": None,
            "source": "OpenStreetMap Overpass API: highway=motorway_junction",
            "note": "구역 중심점 30km 범위에서 motorway_junction을 찾지 못함",
        }
    return {
        "distance_km": round(best[0], 2),
        "name": best[1] or "이름 없음",
        "source": "OpenStreetMap Overpass API: highway=motorway_junction",
        "note": "구역 중심점과 최근접 OSM motorway_junction 노드 간 거리",
    }


def station_area_ratios(boundary: gpd.GeoDataFrame, stations: gpd.GeoDataFrame) -> dict:
    geom = boundary.geometry.iloc[0]
    area_m2 = float(geom.area)
    stations_metric = stations.copy()
    stations_metric["distance_to_boundary_m"] = stations_metric.geometry.distance(geom)
    stations_wgs = stations_metric.to_crs("EPSG:4326")
    ratios = {}
    counts = {}
    used = {}
    for radius in [500, 1000]:
        selected = stations_metric[stations_metric["distance_to_boundary_m"] <= radius].copy()
        buffers = selected.geometry.buffer(radius).union_all() if not selected.empty else None
        inter_area = float(buffers.intersection(geom).area) if buffers is not None else 0.0
        selected_wgs = stations_wgs.loc[selected.index]
        used[f"used_stations_{radius}m"] = [
            {
                "station_id": str(row.get("id")),
                "station_name": row.get("statnm"),
                "line_name": row.get("linenm"),
                "lon": round(float(row.geometry.x), 6),
                "lat": round(float(row.geometry.y), 6),
                "distance_to_boundary_m": round(float(row.get("distance_to_boundary_m")), 1),
            }
            for _, row in selected_wgs.sort_values("distance_to_boundary_m").iterrows()
        ]
        ratios[f"ratio_{radius}m"] = round((inter_area / area_m2) * 100, 2) if area_m2 else None
        ratios[f"intersection_area_{radius}m_m2"] = round(inter_area, 1)
        counts[f"station_count_{radius}m"] = int(len(selected))

    nearest_wgs = stations_wgs.sort_values("distance_to_boundary_m").head(5)
    nearest = [
        {
            "station_id": str(row.get("id")),
            "station_name": row.get("statnm"),
            "line_name": row.get("linenm"),
            "lon": round(float(row.geometry.x), 6),
            "lat": round(float(row.geometry.y), 6),
            "distance_to_boundary_m": round(float(row.get("distance_to_boundary_m")), 1),
        }
        for _, row in nearest_wgs.iterrows()
    ]
    zero_check = {
        "crs_metric": CRS_METRIC,
        "station_source_crs": "subway_network nodes.tsv geometry_wkt EPSG:5179 -> metric CRS",
        "buffer_method": "station point buffer in metric CRS, intersect with business district polygon, divide by polygon area",
        "boundary_area_m2": round(area_m2, 1),
        "nearest_station_distance_m": nearest[0]["distance_to_boundary_m"] if nearest else None,
        "result": "0% is expected because no active station point buffer intersects the polygon within 1km"
        if counts["station_count_1000m"] == 0
        else "station buffers intersect polygon",
    }
    return {**ratios, **counts, **used, "nearest_stations": nearest, "station_zero_result_validation": zero_check}


def main() -> None:
    ensure_dirs()
    stations, _ = load_active_network()
    rows = []
    validation = {}
    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        area_km2 = float(boundary.geometry.area.iloc[0]) / 1_000_000
        bus = bus_stops_for_area(key, boundary)
        road = road_metrics(key, boundary)
        ic = nearest_ic(key, boundary)
        station = station_area_ratios(boundary, stations)

        row = {
            "area_key": key,
            "label": cfg["label"],
            "area_km2": round(area_km2, 4),
            "bus_stop_count": bus["count"],
            "bus_stop_density_per_km2": bus["density"],
            "bus_stop_source": bus["source"],
            "bus_stop_note": bus["note"],
            "bus_stop_validation": bus["validation"],
            "road_length_km": road["length_km"],
            "road_network_density_km_per_km2": road["density"],
            "road_source": road["source"],
            "road_note": road["note"],
            "road_validation": road["validation"],
            "nearest_highway_ic_km": ic["distance_km"],
            "nearest_highway_ic_name": ic["name"],
            "ic_source": ic["source"],
            "ic_note": ic["note"],
            "station_area_ratio_500m": station["ratio_500m"],
            "station_area_ratio_1km": station["ratio_1000m"],
            "station_intersection_area_500m_m2": station["intersection_area_500m_m2"],
            "station_intersection_area_1km_m2": station["intersection_area_1000m_m2"],
            "station_count_500m": station["station_count_500m"],
            "station_count_1km": station["station_count_1000m"],
            "station_used_list_500m": station["used_stations_500m"],
            "station_used_list_1km": station["used_stations_1000m"],
            "station_nearest_list": station["nearest_stations"],
            "station_zero_result_validation": station["station_zero_result_validation"],
            "station_catchment_source": "subway_network/network/nodes.tsv; 2023-12-31 기준 운영 중 역",
            "method": "구역 경계는 EPSG:5186에서 면적·거리 계산 후 결과 GeoJSON/JSON 저장",
            "osm_calculation": {
                "bus_stop_density": "OSM highway=bus_stop, amenity=bus_station 개수 / 구역면적(km²)",
                "road_network_density": "OSM highway 도로 중심선의 구역 내부 총연장(km) / 구역면적(km²)",
                "nearest_ic": "구역 중심점에서 최근접 OSM highway=motorway_junction까지 거리(km)",
            },
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
