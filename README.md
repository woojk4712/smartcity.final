# 판교 제1테크노밸리 · 청라국제업무지구 비교 GIS

## 프로젝트 개요

이 저장소는 **판교 제1테크노밸리와 청라국제업무지구의 성공·저조 요인을 비교 분석하는 웹 GIS 시스템**입니다.

React + Vite + Leaflet 기반 정적 웹앱으로, 필지·건축물·SGIS 집계구·토지이용계획·철도망·OSM 도로/정류장 데이터를 전처리해 지도, 통계표, 차트, 등시간권, 공간접근성 지표를 한 화면에서 비교합니다.

비교 대상 경계는 두 지역 모두 전체 신도시가 아니라 업무기능을 목적으로 계획·고시된 업무지구입니다. 판교는 성남판교 도시지원시설용지 기준, 청라는 IFEZ 지구단위계획 결정고시 및 토지이용계획상 업무·상업 계획용지 기준을 사용합니다. 청라는 실제 입주·건축이 이미 이루어진 필지만 사후적으로 고르지 않고, 계획상 지정된 용지 전체를 구역계로 사용해 미활성화 정도를 평가할 수 있도록 했습니다.

인구·가구·사업체·종사자 데이터가 2023년 기준이므로, 교통 접근성 분석 역시 **2023년 12월 31일 기준 운영 중인 수도권 철도망**으로 통일했습니다.

## 시스템 URL

- GitHub 저장소: https://github.com/woojk4712/smartcity.final.git
- GitHub Pages: https://woojk4712.github.io/smartcity.final/

## GitHub Pages 배포 방법

Vite `base`는 `/smartcity.final/`로 설정되어 있습니다. GitHub Pages의 흰 화면 문제를 피하기 위해 빌드 결과물인 `index.html`, `assets/`, `data/`를 배포 브랜치에도 포함합니다.

```bash
npm install
npm run build
```

배포 파일 갱신 절차는 다음과 같습니다.

```powershell
Copy-Item -Path dist\app.html -Destination index.html -Force
Copy-Item -Path dist\assets\* -Destination assets -Force
Copy-Item -Path public\data\analytics\* -Destination data\analytics -Force
Copy-Item -Path public\data\reports\* -Destination data\reports -Force
git add index.html assets data
git commit -m "Deploy static build"
git push origin main
```

현재 Pages 공개본은 `gh-pages` 브랜치에도 같은 정적 산출물을 반영해 배포합니다.

```powershell
Copy-Item -Path index.html -Destination pages_deploy\index.html -Force
Copy-Item -Path assets\* -Destination pages_deploy\assets -Force
Copy-Item -Path data\analytics\* -Destination pages_deploy\data\analytics -Force
Copy-Item -Path data\reports\* -Destination pages_deploy\data\reports -Force
Set-Location pages_deploy
git add index.html assets data
git commit -m "Deploy latest static build"
git push origin gh-pages
```

## 데이터 출처 목록

| 데이터 | 출처 | 기준연도/기준월 | 사용 목적 | 전처리 내용 |
|---|---|---|---|---|
| SGIS 인구가구 | SGIS | 2023 | 구역 내 인구가구 산정 | 면적가중 배분 |
| SGIS 종사자사업체 | SGIS | 2023 | 종사자사업체 산정 | 면적가중 배분 |
| 연속지적도 | VWorld | 최신 수집월 | 필지 경계 | 구역계 기준 클립 |
| 토지이용계획 | VWorld | 최신 수집월 | 용도지역 구성비 | 면적 계산 |
| 건축물대장 | 건축HUB | 최신 수집월 | 주용도연면적용적률 | 필지/PNU 기준 조인 |
| 도로망 | OSM | 수집일 기준 | 도로망 밀도 | 구역계 기준 클립 |
| 정류장 | OSM 또는 공공데이터 | 수집일 기준 | 정류장 밀도 | 구역 내부 Point 집계 |
| 지하철 네트워크 | LMS 제공 subway_network.zip | 2023 | 등시간권 분석 | 2023년 운영노선 필터링 |

## 데이터 기준연도/기준월

- 분석 기준일: `2023-12-31`
- SGIS 인구·가구·사업체·종사자 CSV: `2023`
- 철도망: `subway_network/network/nodes.tsv`, `links.tsv`의 `begin`, `effective_begin` 값을 사용해 `2023-12-31` 이전 운영 중인 역·링크만 사용
- 제외 노선: GTX-B, GTX-C, 신안산선, 위례신사선, 2024년 이후 개통·계획·미개통 노선
- 연속지적도: 업로드된 VWorld 연속지적도 SHP 기준. 현재 파일명은 `LSMD_CONT_LDREG_41135_202606.shp`, `LSMD_CONT_LDREG_28260_202606.shp`
- 토지이용계획: VWorld 토지이용계획 CSV/ZIP 최신 수집본
- 건축물대장: 건축HUB 건축물대장/건축물조서 최신 수집본
- 집계구 경계: 현재 저장소에서 확인 가능한 2025년 2분기 집계구 경계 SHP를 사용. SGIS 값 기준연도는 2023년이며, 공간 배분 경계는 사용 가능한 최신 경계를 사용한 한계가 있습니다.
- OSM 도로·정류장·IC: 전처리 실행일 기준 Overpass API 조회 또는 캐시된 `public/data/osm/` 결과 사용

## 전처리 과정

전체 전처리는 다음 명령으로 실행합니다.

```bash
pip install -r requirements.txt
npm install
npm run preprocess
```

`npm run preprocess`는 `python scripts/build_all.py`를 실행하며, 내부 순서는 다음과 같습니다.

1. `scripts/preprocess_boundaries.py`
   - 소재지 엑셀의 PNU/지번 목록과 VWorld 연속지적도를 매칭합니다.
   - 판교는 성남판교 도시지원시설용지 기준, 청라는 IFEZ 고시·토지이용계획상 업무·상업 계획용지 기준 필지를 확정합니다.
   - 필지를 병합해 `public/data/boundaries/*_boundary.geojson`을 생성합니다.
   - 매칭률, 누락 필지, 제외 필지는 `public/data/reports/boundary_match_reports.json`에 기록합니다.

2. `scripts/preprocess_spatial_units.py`
   - 구역계와 필지, 건축물대장을 PNU 또는 지번 기준으로 연결합니다.
   - 분석 필지 GeoJSON과 건축물 대표 Geometry를 생성합니다.
   - 실제 건축물 Polygon이 없으면 필지 Polygon을 건축물 대표 Geometry로 사용합니다.

3. `scripts/calculate_accessibility.py`
   - 2023년 말 운영 중인 철도역·링크만 필터링합니다.
   - 최근접 역에서 다익스트라 탐색을 수행해 15·30·45·60분 도달역을 산출합니다.
   - 도달역 800m 버퍼와 집계구를 면적가중 배분해 통근권 인구·종사자를 계산합니다.

4. `scripts/calculate_landuse_mix.py`
   - 토지이용계획과 분석 필지를 PNU 기준으로 조인합니다.
   - 용도지역 면적 구성비와 건축물 주용도 연면적 구성비를 산출합니다.
   - LUM은 용도지역 기준과 건축물 주용도 기준을 구분해 기록합니다.

5. `scripts/calculate_industry.py`
   - SGIS 산업분류별 사업체·종사자 CSV를 읽어 구역별 업종 구성을 산출합니다.

6. `scripts/calculate_bonus_indicators.py`
   - 보조 지표와 형태 지표를 계산합니다.

7. `scripts/calculate_spatial_accessibility.py`
   - OSM Overpass API에서 정류장, 도로망, 고속도로 IC를 조회합니다.
   - 정류장 밀도, 도로망 밀도, 최근접 IC 거리, 500m·1km 역세권 면적 비율을 계산합니다.

8. `scripts/calculate_summary.py`
   - 지도와 차트가 참조하는 최종 수치 파일을 생성합니다.
   - `public/data/analytics/summary.json`, `landuse_mix.json`, `accessibility.json`, `industry.json`, `spatial_accessibility.json`을 통합합니다.
   - `public/data/reports/validation_report.json`에 경계 면적, 필지 수, 건축물 수, 집계구 수, 인구, 가구, 사업체, 종사자, OSM 검증, 등시간권 검증을 기록합니다.

## 공간단위 통합 방법

원자료의 공간 단위가 서로 다르므로 모든 계산은 EPSG:5186 또는 국내 투영좌표계에서 수행하고, 웹 지도용 GeoJSON은 EPSG:4326으로 저장합니다.

- 구역계: 소재지 엑셀의 PNU/지번 목록과 연속지적도 필지를 매칭한 뒤 병합합니다. 면적은 경계 GeoJSON을 EPSG:5179 또는 EPSG:5186으로 변환한 뒤 계산합니다.
- 필지: 분석 경계와 중첩되는 필지 중 중첩 면적 비율이 기준 이상인 필지를 분석 필지로 사용합니다.
- 건축물: 건축물대장 PNU 또는 지번을 분석 필지와 조인합니다. 건축물 Polygon이 없으므로 필지 Polygon을 대표 Geometry로 사용합니다.
- 집계구: SGIS 값은 집계구 단위이므로 구역 Polygon 또는 등시간권 Polygon과 집계구 Polygon의 교차 면적 비율을 이용해 면적가중 배분합니다. 단순 집계구 원값 합산은 사용하지 않습니다.
- 토지이용계획: 토지이용계획 PNU와 필지 PNU를 조인하고, 필지 면적을 기준으로 용도지역 구성비를 산출합니다.
- 철도 접근성: 2023년 말 운영 중인 역·링크만 남긴 네트워크에서 다익스트라 탐색을 수행합니다. 도달역 주변 800m 버퍼를 등시간권 영향권으로 보고 집계구 값을 면적가중 배분합니다.
- OSM 정류장: Overpass 조회는 구역 외곽 500m bbox로 후보를 넓게 가져오지만, 최종 카운트는 EPSG:5186에서 구역 Polygon 내부에 있는 점만 사용합니다.
- OSM 도로망: OSM highway LineString을 구역 Polygon으로 clip한 뒤, 고유 OSM way 기준으로 중복을 제거하고 길이를 합산합니다.

## 주요 지표 산출식

- 구역 면적(km²): 구역 Polygon 면적 / 1,000,000
- 총인구·가구수: Σ(SGIS 집계구 값 × 구역과 집계구 교차면적 / 집계구 원면적)
- 사업체수·종사자수: Σ(SGIS 산업 집계구 값 × 구역과 집계구 교차면적 / 집계구 원면적)
- 직주비: 구역 내 종사자수 / 구역 내 인구
- 업종 구성비: 산업분류별 종사자수 또는 사업체수 / 전체 종사자수 또는 사업체수
- 용도지역 구성비: 용도지역별 필지 면적 / 전체 분석 필지 면적
- 건축물 주용도 구성비: 주용도별 건축물 연면적 / 전체 건축물 연면적
- LUM: `-Σ(p_i × ln(p_i)) / ln(n)`, 여기서 `p_i`는 용도 또는 주용도 비율, `n`은 유효 용도 개수
- 평균 용적률: 건축물대장 용적률 값의 유효값 평균
- 건축 점유율(필지): 건축물대장 매칭 건축물이 존재하는 개발가능 필지 면적 / 개발가능 필지 면적
- 미건축 필지 면적비: 건축물이 없는 개발가능 필지 면적 / 개발가능 필지 면적
- 실제 건축면적 비율: 건축면적 합계 / 개발가능 필지 면적
- 30분·60분 통근권 인구/종사자: 도달역 800m 버퍼와 집계구 교차면적 기준 면적가중 배분값
- 정류장 밀도(개/km²): 구역 내 OSM `highway=bus_stop`, `amenity=bus_station` 개수 / 구역 면적
- 도로망 밀도(km/km²): 구역 내 OSM highway 총연장(km) / 구역 면적(km²)
- 고속도로 IC 접근성(km): 구역 중심점에서 최근접 OSM `highway=motorway_junction`까지의 거리
- 500m·1km 역세권 면적 비율(%): 역 버퍼와 구역 경계 교차면적 / 구역면적 × 100

## 시스템용 산출 파일

보고서와 화면 수치는 아래 파일에서 읽습니다.

- `public/data/analytics/summary.json`: KPI 카드, 비교 통계표, 직주비, 평균 용적률, 개발 실현 지표
- `public/data/analytics/landuse_mix.json`: 용도지역 구성, 건축물 주용도 구성, LUM
- `public/data/analytics/accessibility.json`: 15·30·45·60분 누적 접근성 곡선과 통근권 값
- `public/data/analytics/industry.json`: 업종별 사업체·종사자 구성
- `public/data/analytics/spatial_accessibility.json`: 정류장 밀도, 도로망 밀도, IC 접근성, 역세권 비율
- `public/data/reports/validation_report.json`: 경계 면적, 필지 수, 건축물 수, 집계구 수, 총인구, 총가구, 총사업체, 총종사자, OSM/철도 검증
- `public/data/reports/accessibility_validation_report.json`: 철도망 필터링과 접근성 계산 검증
- `public/data/boundaries/*_boundary.geojson`: 지도 경계 레이어
- `public/data/parcels/*_matched_parcels.geojson`: 필지 클릭 및 용도지역 컬러맵 레이어
- `public/data/buildings/*_buildings.geojson`: 건축물 클릭 및 주용도 컬러맵 레이어
- `public/data/transport/*_rail_2023.geojson`: 2023년 말 기준 도달역/철도역 레이어

## 폴더 구조

```text
smartcity_final/
├─ app.html                         # Vite 개발 진입 HTML
├─ index.html                       # GitHub Pages 배포용 HTML
├─ package.json                     # npm scripts와 프론트엔드 의존성
├─ requirements.txt                 # Python 전처리 의존성
├─ vite.config.js                   # Vite base=/smartcity.final/
├─ scripts/                         # 재현 가능한 Python 전처리/계산 스크립트
│  ├─ build_all.py
│  ├─ common.py
│  ├─ preprocess_boundaries.py
│  ├─ preprocess_spatial_units.py
│  ├─ calculate_accessibility.py
│  ├─ calculate_landuse_mix.py
│  ├─ calculate_industry.py
│  ├─ calculate_bonus_indicators.py
│  ├─ calculate_spatial_accessibility.py
│  ├─ calculate_summary.py
│  └─ test_spatial_rules.py
├─ src/                             # React 지도, 통계 패널, 차트, 데이터 로더
├─ public/data/                     # 전처리 결과 및 웹앱 데이터
│  ├─ analytics/
│  ├─ boundaries/
│  ├─ buildings/
│  ├─ parcels/
│  ├─ reports/
│  ├─ spatial/
│  └─ transport/
├─ data/                            # GitHub Pages 루트 배포용 JSON 복사본
├─ assets/                          # GitHub Pages 루트 배포용 번들
├─ pages_deploy/                    # gh-pages 브랜치 배포 작업 폴더
├─ 판교/, 청라/                     # 소재지 엑셀, 연속지적도, 토지이용계획 원자료
├─ 인구가구사업체/                  # SGIS 2023 CSV
├─ 집계구 경계*/                    # 집계구 경계 SHP
├─ GIS건물통합정보/                 # 건축물대장/건축물조서 원자료
└─ subway_network/                  # LMS 제공 철도 네트워크
```

## 실행 방법

개발 서버 실행:

```bash
npm install
npm run dev
```

전처리부터 다시 생성:

```bash
pip install -r requirements.txt
npm run preprocess
```

프로덕션 빌드:

```bash
npm run build
```

빌드 결과 확인:

```bash
npm run preview
```

공간 규칙 테스트:

```bash
python scripts/test_spatial_rules.py
```

## 구역계 정의

| 지역 | 비교 대상 정의 | 경계 기준 | 출처 | 면적 산출 |
|---|---|---|---|---|
| 제1판교테크노밸리 | 성남판교 택지개발지구 내 도시지원시설용지 및 업무연구시설이 집중된 제1판교 구역 | 성남판교 도시지원시설용지 기준 | 성남시 지구단위계획 자료 또는 성남판교 도시지원시설용지 고시 자료 | 경계 GeoJSON을 EPSG:5179/EPSG:5186으로 변환 후 산출 |
| 청라국제업무지구 | IFEZ 지구단위계획 결정고시 및 토지이용계획에서 업무·상업 기능을 위해 지정된 중심상업지역·일반상업지역 계획용지 | IFEZ 지구단위계획 결정고시의 업무·상업 계획용지 기준 | 인천경제자유구역청 청라국제도시 지구단위계획 결정고시 및 토지이용계획 | 경계 GeoJSON을 EPSG:5179/EPSG:5186으로 변환 후 산출 |

두 지역은 모두 전체 신도시가 아니라, 업무기능을 목적으로 계획·조성된 업무지구 경계를 기준으로 비교했습니다. 이를 통해 주거지 전체와 업무지구를 비교하는 오류를 방지했습니다.

## 한계 및 주의사항

- SGIS 값은 2023년 CSV이나, 현재 저장소에서 확인 가능한 집계구 경계는 2025년 2분기 파일입니다. 값의 기준연도와 공간 경계 기준시점이 완전히 동일하지 않습니다.
- 청라 구역계는 실제 활성 필지 클러스터가 아니라 고시·계획 기준 업무·상업 계획용지입니다. 따라서 미건축 필지 면적비와 건축 점유율은 계획 대비 개발 실현 정도를 보여주는 지표로 해석해야 합니다.
- 건축물 Polygon 원자료가 없어 건축물 레이어는 필지 Polygon을 대표 Geometry로 사용합니다. 추후 건축물 Polygon이 확보되면 교체 가능합니다.
- OSM 정류장·도로망·IC는 전처리 실행일 또는 캐시 파일 기준입니다. 공식 버스정류장/도로망 자료와 일부 차이가 날 수 있습니다.
- 도로망 밀도는 OSM 도로 중심선 기준입니다. 왕복 분리 차로나 경계선 위 도로는 OSM geometry 특성에 따라 길이 산정 방식이 달라질 수 있습니다.
- 서울·경기·인천 전체 집계구 값이 모두 확보되지 않은 경우, 등시간권 인구·종사자 값은 현재 보유 집계구 경계와 CSV 범위 안에서 배분됩니다.
- 대용량 원자료 일부는 GitHub 100MB 제한 때문에 저장소에서 제외될 수 있습니다. 웹앱 실행에 필요한 전처리 결과 GeoJSON/JSON은 `public/data/`와 배포용 `data/`에 포함합니다.
