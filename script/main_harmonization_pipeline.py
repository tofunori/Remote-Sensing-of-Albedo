"""
Unified Satellite Harmonization Pipeline

Complete end-to-end workflow for harmonizing multi-sensor satellite data
to create long-term albedo time series (1984-present).

This script unifies all harmonization steps in a single Python workflow,
replacing the previous JavaScript + Python hybrid approach while maintaining
100% scientific rigor.

Author: Shunan Feng (shunan.feng@envs.au.dk)
Python unified pipeline: 2025-11-23
References:
  - https://doi.org/10.1017/jog.2023.11
  - https://doi.org/10.1080/01431161.2023.2291000
"""

import ee
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import json

from gee_harmonization_core import (
    initialize_gee,
    calculate_broadband_albedo,
    export_image_to_drive
)

from harmonize_l7_to_l8 import (
    harmonize_l7_to_l8,
    extract_paired_pixels_l7_l8,
    get_western_greenland_aoi
)

from harmonize_s2_to_l8 import (
    harmonize_s2_to_l8,
    extract_paired_pixels_s2_l8
)

from harmonize_l9_to_l8 import (
    harmonize_l9_to_l8,
    extract_paired_pixels_l9_l8
)


# ══════════════════════════════════════════════════════════════════════════
# UNIFIED HARMONIZATION PIPELINE
# ══════════════════════════════════════════════════════════════════════════

class HarmonizationPipeline:
    """
    Complete harmonization pipeline for multi-sensor albedo time series.

    Workflow:
    1. Extract paired pixels (optional - for coefficient calculation)
    2. Harmonize all sensors to L8 baseline
    3. Merge into unified time series
    4. Calculate broadband albedo
    5. Export results
    """

    def __init__(
        self,
        aoi: Optional[ee.Geometry] = None,
        date_start: str = '1984-01-01',
        date_end: str = '2023-12-31',
        cloud_cover_max: int = 50,
        project: Optional[str] = None
    ):
        """
        Initialize harmonization pipeline.

        Args:
            aoi: Area of interest (default: Western Greenland)
            date_start: Start date for time series
            date_end: End date for time series
            cloud_cover_max: Maximum cloud cover percentage
            project: Google Earth Engine project ID
        """
        # Initialize GEE
        initialize_gee(project=project)

        # Set AOI
        self.aoi = aoi if aoi else get_western_greenland_aoi()
        self.date_start = date_start
        self.date_end = date_end
        self.cloud_cover_max = cloud_cover_max

        # Collections (populated during run)
        self.l8_col = None
        self.l7_harmonized = None
        self.l9_harmonized = None
        self.s2_harmonized = None
        self.unified_col = None
        self.albedo_col = None

        print(f"\n{'='*70}")
        print("UNIFIED HARMONIZATION PIPELINE INITIALIZED")
        print(f"{'='*70}")
        print(f"Date range: {date_start} to {date_end}")
        print(f"Cloud cover max: {cloud_cover_max}%")
        print(f"AOI bounds: {self.aoi.bounds().getInfo()['type']}")
        print(f"{'='*70}\n")

    def step1_extract_paired_pixels(
        self,
        sensors: List[str] = ['L7', 'S2', 'L9'],
        export_folder_prefix: str = 'GEE_paired',
        start_exports: bool = False
    ) -> Dict[str, tuple]:
        """
        Step 1: Extract paired pixels for RMA regression analysis.

        This step is only needed if you want to recalculate RMA coefficients.
        By default, we use published coefficients from the peer-reviewed papers.

        Args:
            sensors: List of sensors to pair with L8 ['L7', 'S2', 'L9']
            export_folder_prefix: Prefix for Google Drive folders
            start_exports: If True, start export tasks immediately

        Returns:
            Dictionary of {sensor: (collection, tasks)}
        """
        print(f"\n{'='*70}")
        print("STEP 1: PAIRED PIXEL EXTRACTION (Optional)")
        print(f"{'='*70}")
        print("This step extracts contemporaneous image pairs for RMA regression.")
        print("Required only if recalculating harmonization coefficients.\n")

        results = {}

        if 'L7' in sensors:
            print("\n[1/3] Extracting L7-L8 paired pixels...")
            results['L7'] = extract_paired_pixels_l7_l8(
                self.aoi,
                self.date_start,
                self.date_end,
                self.cloud_cover_max,
                f'{export_folder_prefix}_L7_L8',
                start_exports
            )

        if 'S2' in sensors:
            print("\n[2/3] Extracting S2-L8 paired pixels...")
            results['S2'] = extract_paired_pixels_s2_l8(
                self.aoi,
                self.date_start,
                self.date_end,
                self.cloud_cover_max,
                f'{export_folder_prefix}_S2_L8',
                start_exports
            )

        if 'L9' in sensors:
            print("\n[3/3] Extracting L9-L8 paired pixels...")
            results['L9'] = extract_paired_pixels_l9_l8(
                self.aoi,
                '2021-09-27',  # L9 launch date
                self.date_end,
                self.cloud_cover_max,
                f'{export_folder_prefix}_L9_L8',
                start_exports
            )

        print(f"\n{'='*70}")
        print("✓ STEP 1 COMPLETE: Paired pixels extracted")
        print(f"{'='*70}\n")

        return results

    def step2_harmonize_all_sensors(self) -> ee.ImageCollection:
        """
        Step 2: Apply harmonization to all sensors.

        Uses published RMA coefficients to harmonize L7, S2, and L9 to L8 baseline.

        Returns:
            Unified harmonized image collection
        """
        print(f"\n{'='*70}")
        print("STEP 2: HARMONIZE ALL SENSORS TO L8 BASELINE")
        print(f"{'='*70}\n")

        # Load native L8 (baseline sensor)
        print("[1/4] Loading Landsat 8 (baseline sensor)...")
        from gee_harmonization_core import prep_oli
        self.l8_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .filterBounds(self.aoi) \
            .filterDate(self.date_start, self.date_end) \
            .filter(ee.Filter.lt('CLOUD_COVER', self.cloud_cover_max)) \
            .map(prep_oli)
        print(f"      L8 images: {self.l8_col.size().getInfo()}")

        # Harmonize L7
        print("\n[2/4] Harmonizing Landsat 7...")
        self.l7_harmonized = harmonize_l7_to_l8(
            self.aoi,
            self.date_start,
            self.date_end,
            self.cloud_cover_max
        )

        # Harmonize S2
        print("[3/4] Harmonizing Sentinel-2...")
        # S2 available from 2015-06-23
        s2_start = max(self.date_start, '2015-06-23')
        self.s2_harmonized = harmonize_s2_to_l8(
            self.aoi,
            s2_start,
            self.date_end,
            self.cloud_cover_max
        )

        # Harmonize L9
        print("[4/4] Harmonizing Landsat 9...")
        # L9 available from 2021-09-27
        l9_start = max(self.date_start, '2021-09-27')
        self.l9_harmonized = harmonize_l9_to_l8(
            self.aoi,
            l9_start,
            self.date_end,
            self.cloud_cover_max
        )

        # Merge all collections
        print("\n[5/4] Merging all harmonized collections...")
        self.unified_col = self.l8_col \
            .merge(self.l7_harmonized) \
            .merge(self.s2_harmonized) \
            .merge(self.l9_harmonized) \
            .sort('system:time_start')

        total_images = self.unified_col.size().getInfo()
        print(f"      Total unified images: {total_images}")

        print(f"\n{'='*70}")
        print("✓ STEP 2 COMPLETE: All sensors harmonized")
        print(f"{'='*70}\n")

        return self.unified_col

    def step3_calculate_albedo(
        self,
        albedo_type: str = 'total'
    ) -> ee.ImageCollection:
        """
        Step 3: Convert narrowband reflectance to broadband albedo.

        Uses peer-reviewed conversion formulas (Journal of Glaciology, 2023).

        Args:
            albedo_type: 'total' or 'vis_nir'

        Returns:
            Collection with albedo bands
        """
        print(f"\n{'='*70}")
        print(f"STEP 3: CALCULATE BROADBAND ALBEDO ({albedo_type.upper()})")
        print(f"{'='*70}\n")

        if self.unified_col is None:
            raise RuntimeError("Must run step2_harmonize_all_sensors() first")

        def add_albedo(img):
            return calculate_broadband_albedo(img, '', albedo_type)

        self.albedo_col = self.unified_col.map(add_albedo)

        print(f"✓ Albedo calculated for {self.albedo_col.size().getInfo()} images")
        print(f"\n{'='*70}")
        print("✓ STEP 3 COMPLETE: Albedo calculated")
        print(f"{'='*70}\n")

        return self.albedo_col

    def step4_export_results(
        self,
        export_folder: str = 'GEE_harmonized_albedo',
        export_type: str = 'albedo',
        start_exports: bool = False,
        scale: int = 30,
        max_images: Optional[int] = None
    ) -> List[ee.batch.Task]:
        """
        Step 4: Export results to Google Drive.

        Args:
            export_folder: Google Drive folder name
            export_type: 'albedo' or 'reflectance'
            start_exports: If True, start tasks immediately
            scale: Export resolution in meters
            max_images: Maximum number of images to export (None = all)

        Returns:
            List of export tasks
        """
        print(f"\n{'='*70}")
        print(f"STEP 4: EXPORT RESULTS")
        print(f"{'='*70}\n")

        if export_type == 'albedo' and self.albedo_col is None:
            raise RuntimeError("Must run step3_calculate_albedo() first")

        collection = self.albedo_col if export_type == 'albedo' else self.unified_col

        # Limit number of exports if specified
        if max_images:
            collection = ee.ImageCollection(collection.toList(max_images))

        collection_list = collection.toList(collection.size())
        size = min(collection.size().getInfo(), max_images if max_images else float('inf'))

        print(f"Exporting {int(size)} images to folder: {export_folder}")
        print(f"Resolution: {scale}m")

        tasks = []
        for i in range(int(size)):
            img = ee.Image(collection_list.get(i))
            date = ee.Date(img.get('system:time_start')).format('yyyy-MM-dd').getInfo()

            # Select bands to export
            if export_type == 'albedo':
                export_img = img.select('albedo')
            else:
                export_img = img

            task = export_image_to_drive(
                image=export_img,
                description=f'{export_type}_{date}_{i:04d}',
                folder=export_folder,
                region=self.aoi,
                scale=scale
            )
            tasks.append(task)

            if start_exports:
                task.start()
                if (i + 1) % 10 == 0:
                    print(f"      Started {i+1}/{int(size)} tasks...")

        if start_exports:
            print(f"✓ All {len(tasks)} export tasks started")
        else:
            print(f"✓ {len(tasks)} export tasks prepared (not started)")
            print("  Call task.start() to begin exports")

        print(f"\n{'='*70}")
        print("✓ STEP 4 COMPLETE: Exports prepared")
        print(f"{'='*70}\n")

        return tasks

    def run_complete_pipeline(
        self,
        calculate_albedo: bool = True,
        export_results: bool = False,
        start_exports: bool = False
    ):
        """
        Run the complete end-to-end pipeline.

        Args:
            calculate_albedo: If True, calculate albedo (Step 3)
            export_results: If True, prepare exports (Step 4)
            start_exports: If True, start export tasks immediately
        """
        print(f"\n{'#'*70}")
        print("# RUNNING COMPLETE HARMONIZATION PIPELINE")
        print(f"{'#'*70}\n")

        # Step 2: Harmonize (Step 1 is optional)
        self.step2_harmonize_all_sensors()

        # Step 3: Calculate albedo
        if calculate_albedo:
            self.step3_calculate_albedo()

        # Step 4: Export
        if export_results:
            self.step4_export_results(start_exports=start_exports)

        print(f"\n{'#'*70}")
        print("# PIPELINE COMPLETE")
        print(f"{'#'*70}\n")

        # Print summary
        print("Summary:")
        print(f"  Total harmonized images: {self.unified_col.size().getInfo()}")
        if calculate_albedo:
            print(f"  Albedo calculated: Yes")
        print(f"  Results exported: {export_results}")


# ══════════════════════════════════════════════════════════════════════════
# COMMAND LINE INTERFACE
# ══════════════════════════════════════════════════════════════════════════

def main():
    """Command line interface for unified pipeline."""
    parser = argparse.ArgumentParser(
        description='Unified Satellite Harmonization Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline for 2020
  python main_harmonization_pipeline.py --start 2020-01-01 --end 2020-12-31 --full

  # Harmonize only (no albedo, no export)
  python main_harmonization_pipeline.py --start 2015-01-01 --end 2023-12-31

  # Full pipeline with exports
  python main_harmonization_pipeline.py --start 2020-01-01 --end 2020-12-31 --full --export --run

  # Extract paired pixels only
  python main_harmonization_pipeline.py --extract-only --start 2013-05-01 --end 2013-06-01
        """
    )

    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--cloud', type=int, default=50, help='Max cloud cover %%')
    parser.add_argument('--project', help='GEE project ID')

    parser.add_argument('--full', action='store_true', help='Run complete pipeline')
    parser.add_argument('--albedo', action='store_true', help='Calculate albedo')
    parser.add_argument('--export', action='store_true', help='Prepare exports')
    parser.add_argument('--run', action='store_true', help='Start export tasks immediately')

    parser.add_argument('--extract-only', action='store_true', help='Only extract paired pixels')
    parser.add_argument('--sensors', nargs='+', choices=['L7', 'S2', 'L9'],
                       default=['L7', 'S2', 'L9'], help='Sensors for paired pixel extraction')

    args = parser.parse_args()

    # Create pipeline
    pipeline = HarmonizationPipeline(
        date_start=args.start,
        date_end=args.end,
        cloud_cover_max=args.cloud,
        project=args.project
    )

    # Run requested workflow
    if args.extract_only:
        # Extract paired pixels only
        pipeline.step1_extract_paired_pixels(
            sensors=args.sensors,
            start_exports=args.run
        )
    elif args.full:
        # Run complete pipeline
        pipeline.run_complete_pipeline(
            calculate_albedo=True,
            export_results=args.export,
            start_exports=args.run
        )
    else:
        # Custom workflow
        pipeline.step2_harmonize_all_sensors()
        if args.albedo:
            pipeline.step3_calculate_albedo()
        if args.export:
            pipeline.step4_export_results(start_exports=args.run)


if __name__ == '__main__':
    main()
