"""
Sentinel-2 to Landsat 8 Harmonization Script

Python conversion of S2ToL8.js maintaining 100% scientific rigor.

This script pairs Sentinel-2 MSI and Landsat 8 OLI images, exports them
for regression analysis, and applies RMA harmonization coefficients.

Original JavaScript: S2ToL8.js
Author: Shunan Feng (shunan.feng@envs.au.dk)
Python conversion: 2025-11-23
Reference: https://doi.org/10.1017/jog.2023.11
"""

import ee
import argparse
from gee_harmonization_core import (
    initialize_gee,
    prep_oli,
    prep_s2,
    create_daily_mosaics,
    create_temporal_filter,
    join_collections,
    apply_harmonization_coefficients,
    RMA_COEFFS_S2_TO_L8,
    batch_export_collection
)


def get_western_greenland_aoi() -> ee.Geometry:
    """Get Western Greenland AOI (default study area)."""
    return ee.Geometry.Polygon([[
        [-75.35327725640606, 78.15797707936824],
        [-58.137306661848434, 69.59945512283268],
        [-51.82415036596651, 59.897134149764156],
        [-42.233465551083604, 59.260337764670496],
        [-61.95501079278244, 79.65995314962508]
    ]])


def extract_paired_pixels_s2_l8(
    aoi: ee.Geometry,
    date_start: str,
    date_end: str,
    cloud_cover_max: int = 50,
    export_folder: str = 'GEE_S2_L8_paired',
    start_exports: bool = False
):
    """
    Extract paired Sentinel-2 and Landsat 8 pixels for regression analysis.

    Args:
        aoi: Area of interest
        date_start: Start date (YYYY-MM-DD)
        date_end: End date (YYYY-MM-DD)
        cloud_cover_max: Maximum cloud cover percentage
        export_folder: Google Drive folder for exports
        start_exports: If True, start export tasks immediately

    Returns:
        Tuple of (paired_collection, export_tasks)
    """
    print(f"\n{'='*70}")
    print("SENTINEL-2 TO LANDSAT 8 - PAIRED PIXEL EXTRACTION")
    print(f"{'='*70}")
    print(f"Date range: {date_start} to {date_end}")
    print(f"Cloud cover max: {cloud_cover_max}%")

    date_start_ee = ee.Date(date_start)
    date_end_ee = ee.Date(date_end)

    # Load Landsat 8
    print("\n[1/6] Loading Landsat 8 OLI collection...")
    l8_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
        .filterBounds(aoi) \
        .filterDate(date_start_ee, date_end_ee) \
        .filter(ee.Filter.lt('CLOUD_COVER', cloud_cover_max)) \
        .map(prep_oli)
    print(f"      L8 images found: {l8_col.size().getInfo()}")

    # Load Sentinel-2
    print("[2/6] Loading Sentinel-2 MSI collection...")
    s2_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(aoi) \
        .filterDate(date_start_ee, date_end_ee) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_cover_max)) \
        .map(prep_s2)
    print(f"      S2 images found: {s2_col.size().getInfo()}")

    # Create daily mosaics
    print("[3/6] Creating daily mosaics...")
    l8_daily = create_daily_mosaics(l8_col, date_start_ee, date_end_ee)
    s2_daily = create_daily_mosaics(s2_col, date_start_ee, date_end_ee)
    print(f"      L8 daily mosaics: {l8_daily.size().getInfo()}")
    print(f"      S2 daily mosaics: {s2_daily.size().getInfo()}")

    # Join collections
    print("[4/6] Creating temporal join...")
    time_filter = create_temporal_filter(max_diff_days=1)
    paired_col = join_collections(l8_daily, s2_daily, time_filter, match_key='timewindow')

    def combine_paired_images(img):
        s2_img = ee.Image(img.get('timewindow'))
        return img.addBands(s2_img)

    paired_col = paired_col.map(combine_paired_images)
    print(f"      Paired images: {paired_col.size().getInfo()}")

    # Export
    print(f"[5/6] Preparing exports to Drive folder: {export_folder}")
    tasks = batch_export_collection(
        collection=paired_col,
        folder=export_folder,
        region=aoi,
        scale=30,
        prefix='S2_L8_paired'
    )
    print(f"      Export tasks created: {len(tasks)}")

    if start_exports:
        print("[6/6] Starting export tasks...")
        for i, task in enumerate(tasks):
            task.start()
            print(f"      Started task {i+1}/{len(tasks)}")
    else:
        print("[6/6] Exports prepared but not started")

    print(f"\n{'='*70}")
    print("✓ Paired pixel extraction complete")
    print(f"{'='*70}\n")

    return paired_col, tasks


def harmonize_s2_to_l8(
    aoi: ee.Geometry,
    date_start: str,
    date_end: str,
    cloud_cover_max: int = 50,
    use_custom_coeffs: dict = None
) -> ee.ImageCollection:
    """
    Apply RMA harmonization to Sentinel-2 imagery.

    Args:
        aoi: Area of interest
        date_start: Start date (YYYY-MM-DD)
        date_end: End date (YYYY-MM-DD)
        cloud_cover_max: Maximum cloud cover percentage
        use_custom_coeffs: Optional custom RMA coefficients

    Returns:
        Harmonized Sentinel-2 collection
    """
    print(f"\n{'='*70}")
    print("SENTINEL-2 TO LANDSAT 8 - APPLYING HARMONIZATION")
    print(f"{'='*70}")

    coeffs = use_custom_coeffs if use_custom_coeffs else RMA_COEFFS_S2_TO_L8

    s2_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(aoi) \
        .filterDate(date_start, date_end) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_cover_max)) \
        .map(prep_s2)

    print(f"S2 images to harmonize: {s2_col.size().getInfo()}")
    print("\nApplying RMA coefficients:")
    for band, coeff in coeffs.items():
        print(f"  {band:6s}: slope={coeff['slope']:.4f}, intercept={coeff['intercept']:+.4f}")

    def apply_harmonization(img):
        return apply_harmonization_coefficients(img, coeffs, 'S2')

    harmonized_col = s2_col.map(apply_harmonization)

    print(f"\n✓ Harmonization complete")
    print(f"{'='*70}\n")

    return harmonized_col


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description='Sentinel-2 to Landsat 8 Harmonization'
    )
    parser.add_argument('--mode', choices=['extract', 'harmonize'], required=True)
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--cloud', type=int, default=50)
    parser.add_argument('--folder', default='GEE_S2_L8_paired')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--project', help='GEE project ID')

    args = parser.parse_args()

    initialize_gee(project=args.project)
    aoi = get_western_greenland_aoi()

    if args.mode == 'extract':
        paired_col, tasks = extract_paired_pixels_s2_l8(
            aoi, args.start, args.end, args.cloud, args.folder, args.run
        )
    elif args.mode == 'harmonize':
        harmonized_col = harmonize_s2_to_l8(aoi, args.start, args.end, args.cloud)


if __name__ == '__main__':
    main()
