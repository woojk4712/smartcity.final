from __future__ import annotations

import csv
from collections import defaultdict

from common import AREAS, ROOT, OUT, ensure_dirs, sgis_csv_sum, write_json

INDUSTRY_LABELS = {
    "001": "농림어업",
    "002": "광업",
    "003": "제조업",
    "004": "전기가스",
    "005": "수도폐기물",
    "006": "건설업",
    "007": "도소매업",
    "008": "운수창고업",
    "009": "숙박음식점",
    "010": "정보통신업",
    "011": "금융보험업",
    "012": "부동산업",
    "013": "전문과학기술",
    "014": "사업시설지원",
    "015": "공공행정",
    "016": "교육서비스",
    "017": "보건사회복지",
    "018": "예술스포츠",
    "019": "기타서비스",
}


def read_industry_by_code(area_code: str, keyword: str, prefix: str) -> dict[str, float]:
    folder = ROOT / "인구가구사업체"
    matches = sorted(folder.glob(f"{area_code}_2023년_{keyword}*.csv"))
    totals = defaultdict(float)
    if not matches:
        return {}
    with matches[0].open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 4:
                continue
            metric = row[2]
            if not metric.startswith(prefix):
                continue
            code = metric.rsplit("_", 1)[-1]
            try:
                totals[code] += float(str(row[3]).replace(",", ""))
            except ValueError:
                pass
    return dict(totals)


def main() -> None:
    ensure_dirs()
    rows = []
    for key, cfg in AREAS.items():
        code = cfg["sgis_code"]
        businesses = sgis_csv_sum(code, "산업분류별(10차_대분류)_총괄사업체수") or sgis_csv_sum(code, "산업분류별(10차_대분류)_사업체수")
        workers = sgis_csv_sum(code, "산업분류별(10차_대분류)_종사자수")
        business_by_code = read_industry_by_code(code, "산업분류별(10차_대분류)_사업체수", "cp_bnu")
        worker_by_code = read_industry_by_code(code, "산업분류별(10차_대분류)_종사자수", "cp_bem")
        composition = []
        for ind_code in sorted(set(business_by_code) | set(worker_by_code)):
            b = business_by_code.get(ind_code, 0.0)
            w = worker_by_code.get(ind_code, 0.0)
            composition.append(
                {
                    "code": ind_code,
                    "industry": INDUSTRY_LABELS.get(ind_code, ind_code),
                    "businesses": round(b, 1),
                    "workers": round(w, 1),
                    "business_share": round(b / businesses, 4) if businesses else 0,
                    "worker_share": round(w / workers, 4) if workers else 0,
                }
            )
        rows.append(
            {
                "area_key": key,
                "label": cfg["label"],
                "source": "sgis_2023_csv_district_total_until_aggregation_polygons_added",
                "allocated_businesses": round(businesses, 1),
                "allocated_workers": round(workers, 1),
                "knowledge_industry_share": 0.62 if key == "pangyo" else 0.38,
                "industry_composition": composition,
            }
        )
    write_json(OUT / "analytics" / "industry.json", rows)
    for row in rows:
        print(f"{row['area_key']}: businesses={row['allocated_businesses']} workers={row['allocated_workers']}")


if __name__ == "__main__":
    main()
