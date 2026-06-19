from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "preprocess_boundaries.py",
    "preprocess_spatial_units.py",
    "calculate_accessibility.py",
    "calculate_landuse_mix.py",
    "calculate_industry.py",
    "calculate_bonus_indicators.py",
    "calculate_spatial_accessibility.py",
    "calculate_summary.py",
]


def main() -> None:
    root = Path(__file__).resolve().parent
    for script in SCRIPTS:
        print(f"\n== {script} ==")
        subprocess.run([sys.executable, str(root / script)], check=True)


if __name__ == "__main__":
    main()
