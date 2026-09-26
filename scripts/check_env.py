"""Check that the project environment has every required library and tool.

Run: python scripts/check_env.py
Exits with code 1 if anything is missing.
"""

from __future__ import annotations

import importlib
import shutil
import sys

# import name -> display name
LIBRARIES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "yaml": "pyyaml",
    "pyarrow": "pyarrow",
    "rasterio": "rasterio",
    "rioxarray": "rioxarray",
    "xarray": "xarray",
    "geopandas": "geopandas",
    "shapely": "shapely",
    "pyproj": "pyproj",
    "pyogrio": "pyogrio",
    "pystac_client": "pystac-client",
    "planetary_computer": "planetary-computer",
    "osmnx": "osmnx",
    "requests": "requests",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "mapclassify": "mapclassify",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "contextily": "contextily",
    "matplotlib_scalebar": "matplotlib-scalebar",
    "folium": "folium",
    "pytest": "pytest",
}

CLI_TOOLS = ["black", "ruff", "nbstripout", "pre-commit", "jupyter"]

# import name -> minimum (major, minor)
MIN_VERSIONS = {
    "shapely": (2, 0),
    "sklearn": (1, 3),
}


def _major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    return int(parts[0]), int("".join(ch for ch in parts[1] if ch.isdigit()) or 0)


def main() -> int:
    problems: list[str] = []
    print(f"Python {sys.version.split()[0]} ({sys.executable})\n")

    for module_name, display in LIBRARIES.items():
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - report any import failure
            problems.append(f"{display}: import failed ({exc})")
            print(f"  [FAIL] {display}")
            continue
        version = getattr(module, "__version__", "?")
        minimum = MIN_VERSIONS.get(module_name)
        if minimum and version != "?" and _major_minor(version) < minimum:
            problems.append(f"{display}: {version} < {'.'.join(map(str, minimum))}")
            print(f"  [FAIL] {display} {version}")
            continue
        print(f"  [ok]   {display} {version}")

    try:
        import rasterio

        print(f"  [ok]   GDAL {rasterio.__gdal_version__}")
    except Exception:  # noqa: BLE001
        pass

    print()
    for tool in CLI_TOOLS:
        if shutil.which(tool):
            print(f"  [ok]   {tool} (CLI)")
        else:
            problems.append(f"{tool}: command not found on PATH")
            print(f"  [FAIL] {tool} (CLI)")

    print()
    if problems:
        print("Environment check FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Environment check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
