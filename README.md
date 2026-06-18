# 판교 1테크노밸리 · 청라국제도시 비교 GIS

React + Vite + Leaflet 기반 정적 GIS입니다. 업로드된 소재지 엑셀과 연속지적도를 PNU로 매칭해 판교와 청라의 분석 경계를 생성하고, SGIS 2023 CSV와 2023년 말 기준 수도권 철도망을 사용해 비교 화면을 구성합니다.

인구가구사업체종사자 데이터가 2023년 기준이므로, 교통 접근성 분석 역시 2023년 말 기준 운영 중인 수도권 철도망으로 통일하였다.

## 실행

```bash
npm install
npm run preprocess
npm run dev
npm run build
```

## 데이터 구조

- `public/data/boundaries/*_boundary.geojson`: 소재지 PNU와 연속지적도 매칭 후 병합한 구역계
- `public/data/parcels/*_matched_parcels.geojson`: 구역계 생성에 사용된 필지
- `public/data/transport/*_rail_2023.geojson`: 2023-12-31 기준 운영 중인 철도역
- `public/data/analytics/*.json`: 차트와 통계 패널이 참조하는 단일 집계값
- `public/data/reports/*_boundary_match_report.json`: 누락 필지, 중복 필지, 매칭률 로그

## 구현 지표

- 인구 지표: 구역 내 집계구 면적비례배분 총인구·가구수, 종사자수·사업체수, 60분 통근권 총인구·가구수·종사자수
- 산업 지표: SGIS 2023 산업분류 대분류별 사업체수·종사자수 구성
- 토지이용: 토지이용계획 CSV의 `고유번호(PNU)`와 구역 내 매칭 필지를 조인해 용도지역지구별 면적 비율 산출
- 교통망: 2023-12-31 기준 운영 중인 철도역과 15·30·45·60분 동일 시간대 등시간권 누적 접근성 비교
- 지도 팝업: 필지 클릭 시 PNU·지번 등 속성, 건축물 클릭 시 주용도·건축면적·연면적·대지면적·건폐율·용적률 후보 속성 표출

## 현재 데이터 한계

SGIS 값은 2023년 CSV이고 현재 발견된 집계구 경계는 2025년 2분기 파일입니다. 따라서 값의 기준연도는 2023년, 공간 배분 경계는 사용 가능한 최신 집계구 경계를 활용했습니다. OSM 도로망과 공식 입주기업 매출·임직원 지표는 아직 없어 가점 지표 일부는 `null`로 둡니다.

대용량 원자료(`서울/서울_토지이용계획/*.csv`, `청라/인천_토지이용계획/*.csv`, `판교/판교_토지이용계획.zip`)는 GitHub 100MB 제한 때문에 `.gitignore`에서 제외합니다. 전처리 결과인 `public/data/analytics/*.json`과 지도용 GeoJSON은 저장소에 포함됩니다.

## 배포

GitHub Pages 대상 저장소는 `https://github.com/woojk4712/smartcity.final.git`이며 Vite `base`는 `/smartcity.final/`로 설정되어 있습니다.

배포 후 공개 URL은 다음 주소입니다.

```text
https://woojk4712.github.io/smartcity.final/
```

현재 저장소의 GitHub Pages는 `main` 브랜치 루트에서 정적 파일을 직접 서비스하도록 맞췄습니다. 흰 화면을 피하기 위해 빌드된 `index.html`, `assets/`, `data/`도 루트에 포함되어 있습니다.
