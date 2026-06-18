from __future__ import annotations

from shapely.geometry import box

from calculate_accessibility import active_by_2023
from preprocess_spatial_units import allocate_by_area, centroid_inside, include_parcel_by_overlap


def test_parcel_overlap_threshold() -> None:
    boundary = box(0, 0, 50, 10)
    parcel_49 = box(0, 0, 100, 10)
    keep, _area, ratio = include_parcel_by_overlap(parcel_49, box(0, 0, 49, 10))
    assert keep is False
    assert round(ratio, 2) == 0.49

    keep, _area, ratio = include_parcel_by_overlap(parcel_49, boundary)
    assert keep is True
    assert round(ratio, 2) == 0.50


def test_building_centroid_rule() -> None:
    boundary = box(0, 0, 10, 10)
    assert centroid_inside(box(1, 1, 2, 2), boundary) is True
    assert centroid_inside(box(11, 11, 12, 12), boundary) is False


def test_area_allocation() -> None:
    assert allocate_by_area(1000, 100_000, 40_000) == 400


def test_rail_date_filter() -> None:
    assert active_by_2023("2023-12-31") is True
    assert active_by_2023("2024-01-01") is False


if __name__ == "__main__":
    test_parcel_overlap_threshold()
    test_building_centroid_rule()
    test_area_allocation()
    test_rail_date_filter()
    print("spatial rule tests passed")
