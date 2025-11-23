"""
Landsat 7 to Landsat 8 Harmonization Script

Python conversion of L7ToL8.js maintaining 100% scientific rigor.

This script pairs Landsat 7 ETM+ and Landsat 8 OLI images, exports them
for regression analysis, and applies RMA harmonization coefficients.

Original JavaScript: L7ToL8.js
Author: Shunan Feng (shunan.feng@envs.au.dk)
Python conversion: 2025-11-23
Reference: https://doi.org/10.1017/jog.2023.11
"""

import ee
import argparse
from datetime import datetime
from typing import Optional, Tuple
from gee_harmonization_core import (
    initialize_gee,
    prep_oli,
    prep_etm,
    create_daily_mosaics,
    create_temporal_filter,
    join_collections,
    apply_harmonization_coefficients,
    RMA_COEFFS_L7_TO_L8,
    export_image_to_drive,
    batch_export_collection
)


# ══════════════════════════════════════════════════════════════════════════
# REGION OF INTEREST DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════

def get_western_greenland_aoi() -> ee.Geometry:
    """
    Get Western Greenland AOI (default study area).

    Equivalent to JavaScript (L7ToL8.js:115-120):
    var aoi = ee.Geometry.Polygon(...)
    """
    return ee.Geometry.Polygon([[
        [-75.35327725640606, 78.15797707936824],
        [-58.137306661848434, 69.59945512283268],
        [-51.82415036596651, 59.897134149764156],
        [-42.233465551083604, 59.260337764670496],
        [-61.95501079278244, 79.65995314962508]
    ]])


def get_greenland_ice_mask() -> ee.Image:
    """
    Get Greenland ice mask.

    Equivalent to JavaScript (L7ToL8.js:93-94):
    var greenlandmask = ee.Image('OSU/GIMP/2000_ICE_OCEAN_MASK')
                          .select('ice_mask').eq(1);
    """
    return ee.Image('OSU/GIMP/2000_ICE_OCEAN_MASK') \
        .select('ice_mask').eq(1)


# ══════════════════════════════════════════════════════════════════════════
# PAIRED PIXEL EXTRACTION WORKFLOW
# ══════════════════════════════════════════════════════════════════════════

def extract_paired_pixels_l7_l8(
    aoi: ee.Geometry,
    date_start: str,
    date_end: str,
    cloud_cover_max: int = 50,
    export_folder: str = 'GEE_L7_L8_paired',
    start_exports: bool = False
) -> Tuple[ee.ImageCollection, list]:
    """
    Extract paired Landsat 7 and Landsat 8 pixels for regression analysis.

    This is Step 1 of the harmonization workflow: extract contemporaneous
    images from both sensors to calculate RMA regression coefficients.

    Equivalent to JavaScript L7ToL8.js full workflow (lines 129-249)

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
    print("LANDSAT 7 TO LANDSAT 8 - PAIRED PIXEL EXTRACTION")
    print(f"{'='*70}")
    print(f"Date range: {date_start} to {date_end}")
    print(f"Cloud cover max: {cloud_cover_max}%")
    print(f"AOI: {aoi.bounds().getInfo()['coordinates'][0][:2]}")

    # Parse dates
    date_start_ee = ee.Date(date_start)
    date_end_ee = ee.Date(date_end)

    # Create collection filters
    col_filter = ee.Filter.And(
        ee.Filter.bounds(aoi),
        ee.Filter.date(date_start_ee, date_end_ee),
        ee.Filter.lt('CLOUD_COVER', cloud_cover_max)
    )

    # Load and process Landsat 8 (OLI)
    print("\n[1/6] Loading Landsat 8 OLI collection...")
    oli_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
        .filter(col_filter) \
        .map(prep_oli)
    print(f"      L8 images found: {oli_col.size().getInfo()}")

    # Load and process Landsat 7 (ETM+)
    print("[2/6] Loading Landsat 7 ETM+ collection...")
    etm_col = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2") \
        .filter(col_filter) \
        .map(prep_etm)
    print(f"      L7 images found: {etm_col.size().getInfo()}")

    # Create daily mosaics
    print("[3/6] Creating daily mosaics...")
    l8_daily = create_daily_mosaics(oli_col, date_start_ee, date_end_ee, day_step=1)
    l7_daily = create_daily_mosaics(etm_col, date_start_ee, date_end_ee, day_step=1)
    print(f"      L8 daily mosaics: {l8_daily.size().getInfo()}")
    print(f"      L7 daily mosaics: {l7_daily.size().getInfo()}")

    # Create temporal filter (1 day window)
    print("[4/6] Creating temporal join...")
    time_filter = create_temporal_filter(max_diff_days=1)

    # Join collections
    paired_col = join_collections(l8_daily, l7_daily, time_filter, match_key='timewindow')

    # Create paired images with both L7 and L8 bands
    def combine_paired_images(img):
        l7_img = ee.Image(img.get('timewindow'))
        # Combine L8 and L7 bands into single image
        return img.addBands(l7_img)

    paired_col = paired_col.map(combine_paired_images)
    print(f"      Paired images: {paired_col.size().getInfo()}")

    # Export to Google Drive
    print(f"[5/6] Preparing exports to Drive folder: {export_folder}")
    tasks = batch_export_collection(
        collection=paired_col,
        folder=export_folder,
        region=aoi,
        scale=30,
        prefix='L7_L8_paired'
    )
    print(f"      Export tasks created: {len(tasks)}")

    if start_exports:
        print("[6/6] Starting export tasks...")
        for i, task in enumerate(tasks):
            task.start()
            print(f"      Started task {i+1}/{len(tasks)}: {task.config['description']}")
    else:
        print("[6/6] Exports prepared but not started")
        print("      Call task.start() on each task to begin exports")

    print(f"\n{'='*70}")
    print("✓ Paired pixel extraction complete")
    print(f"{'='*70}\n")

    return paired_col, tasks


# ══════════════════════════════════════════════════════════════════════════
# HARMONIZATION APPLICATION WORKFLOW
# ══════════════════════════════════════════════════════════════════════════

def harmonize_l7_to_l8(
    aoi: ee.Geometry,
    date_start: str,
    date_end: str,
    cloud_cover_max: int = 50,
    use_custom_coeffs: Optional[dict] = None
) -> ee.ImageCollection:
    """
    Apply RMA harmonization to Landsat 7 imagery.

    This is Step 2 of the workflow: apply pre-calculated RMA coefficients
    to harmonize all L7 images to L8 baseline.

    Args:
        aoi: Area of interest
        date_start: Start date (YYYY-MM-DD)
        date_end: End date (YYYY-MM-DD)
        cloud_cover_max: Maximum cloud cover percentage
        use_custom_coeffs: Optional custom RMA coefficients (default: published values)

    Returns:
        Harmonized Landsat 7 collection
    """
    print(f"\n{'='*70}")
    print("LANDSAT 7 TO LANDSAT 8 - APPLYING HARMONIZATION")
    print(f"{'='*70}")

    coeffs = use_custom_coeffs if use_custom_coeffs else RMA_COEFFS_L7_TO_L8

    # Load Landsat 7 collection
    col_filter = ee.Filter.And(
        ee.Filter.bounds(aoi),
        ee.Filter.date(date_start, date_end),
        ee.Filter.lt('CLOUD_COVER', cloud_cover_max)
    )

    etm_col = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2") \
        .filter(col_filter) \
        .map(prep_etm)

    print(f"L7 images to harmonize: {etm_col.size().getInfo()}")
    print("\nApplying RMA coefficients:")
    for band, coeff in coeffs.items():
        print(f"  {band:6s}: slope={coeff['slope']:.4f}, intercept={coeff['intercept']:+.4f}")

    # Apply harmonization
    def apply_harmonization(img):
        return apply_harmonization_coefficients(img, coeffs, 'L7')

    harmonized_col = etm_col.map(apply_harmonization)

    print(f"\n✓ Harmonization complete")
    print(f"{'='*70}\n")

    return harmonized_col


# ══════════════════════════════════════════════════════════════════════════
# COMMAND LINE INTERFACE
# ══════════════════════════════════════════════════════════════════════════

def main():
    """Command line interface for L7 to L8 harmonization."""
    parser = argparse.ArgumentParser(
        description='Landsat 7 to Landsat 8 Harmonization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract paired pixels for May 2013
  python harmonize_l7_to_l8.py --mode extract --start 2013-05-01 --end 2013-06-01

  # Apply harmonization to full time series
  python harmonize_l7_to_l8.py --mode harmonize --start 2000-01-01 --end 2023-12-31

  # Extract and start exports
  python harmonize_l7_to_l8.py --mode extract --start 2013-05-01 --end 2013-06-01 --run
        """
    )

    parser.add_argument(
        '--mode',
        choices=['extract', 'harmonize'],
        required=True,
        help='Operation mode: extract paired pixels or apply harmonization'
    )
    parser.add_argument(
        '--start',
        required=True,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        required=True,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--cloud',
        type=int,
        default=50,
        help='Maximum cloud cover percentage (default: 50)'
    )
    parser.add_argument(
        '--folder',
        default='GEE_L7_L8_paired',
        help='Google Drive folder for exports (default: GEE_L7_L8_paired)'
    )
    parser.add_argument(
        '--run',
        action='store_true',
        help='Start export tasks immediately'
    )
    parser.add_argument(
        '--project',
        help='Google Earth Engine project ID'
    )

    args = parser.parse_args()

    # Initialize GEE
    initialize_gee(project=args.project)

    # Get AOI
    aoi = get_western_greenland_aoi()

    # Run requested mode
    if args.mode == 'extract':
        paired_col, tasks = extract_paired_pixels_l7_l8(
            aoi=aoi,
            date_start=args.start,
            date_end=args.end,
            cloud_cover_max=args.cloud,
            export_folder=args.folder,
            start_exports=args.run
        )
        print(f"\nPaired collection ready. Total images: {paired_col.size().getInfo()}")
        if not args.run:
            print("\nTo start exports, run with --run flag")

    elif args.mode == 'harmonize':
        harmonized_col = harmonize_l7_to_l8(
            aoi=aoi,
            date_start=args.start,
            date_end=args.end,
            cloud_cover_max=args.cloud
        )
        print(f"\nHarmonized collection ready. Total images: {harmonized_col.size().getInfo()}")
        print("Use export functions to save results.")


if __name__ == '__main__':
    main()
