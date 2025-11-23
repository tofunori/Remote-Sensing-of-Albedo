"""
Example Usage Scripts for Unified Python Harmonization Pipeline

This file contains practical examples showing how to use the new Python-only
workflow for satellite harmonization and albedo calculation.

Author: Shunan Feng (shunan.feng@envs.au.dk)
Date: 2025-11-23
"""

import ee
from main_harmonization_pipeline import HarmonizationPipeline, get_western_greenland_aoi
from gee_harmonization_core import initialize_gee


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 1: Simple Harmonization for One Year
# ══════════════════════════════════════════════════════════════════════════

def example_1_simple_harmonization():
    """
    Example 1: Harmonize all sensors for a single year (2020).

    This is the most common use case: create a harmonized time series
    for a specific time period.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple Harmonization for 2020")
    print("="*70 + "\n")

    # Initialize pipeline
    pipeline = HarmonizationPipeline(
        date_start='2020-01-01',
        date_end='2020-12-31',
        cloud_cover_max=30  # Stricter cloud filtering
    )

    # Harmonize all sensors
    unified_collection = pipeline.step2_harmonize_all_sensors()

    # Print summary
    print(f"\n✓ Created unified collection with {unified_collection.size().getInfo()} images")
    print("  Sensors: L4, L5, L7, L8, L9, S2 (all harmonized to L8 baseline)")


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 2: Complete Workflow with Albedo Calculation
# ══════════════════════════════════════════════════════════════════════════

def example_2_with_albedo():
    """
    Example 2: Full workflow including albedo calculation.

    This shows how to create harmonized reflectance AND calculate
    broadband albedo using peer-reviewed formulas.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Complete Workflow with Albedo (Summer 2020)")
    print("="*70 + "\n")

    pipeline = HarmonizationPipeline(
        date_start='2020-06-01',
        date_end='2020-08-31',  # Summer season only
        cloud_cover_max=20
    )

    # Run complete workflow
    pipeline.run_complete_pipeline(
        calculate_albedo=True,
        export_results=False  # Don't export yet
    )

    # Access results
    print(f"\n✓ Harmonized images: {pipeline.unified_col.size().getInfo()}")
    print(f"✓ Albedo images: {pipeline.albedo_col.size().getInfo()}")


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 3: Extract Time Series at Specific Point
# ══════════════════════════════════════════════════════════════════════════

def example_3_point_time_series():
    """
    Example 3: Extract albedo time series at a specific AWS location.

    This demonstrates how to extract time series data at a point,
    useful for validation against ground measurements.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Extract Point Time Series")
    print("="*70 + "\n")

    # Initialize
    initialize_gee()

    # Define point of interest (e.g., PROMICE AWS location)
    # KAN_M station: lon=-50.13, lat=67.07
    point = ee.Geometry.Point([-50.13, 67.07])

    # Create pipeline with point buffer as AOI
    pipeline = HarmonizationPipeline(
        aoi=point.buffer(500),  # 500m buffer
        date_start='2015-01-01',
        date_end='2023-12-31',
        cloud_cover_max=50
    )

    # Harmonize and calculate albedo
    pipeline.step2_harmonize_all_sensors()
    pipeline.step3_calculate_albedo()

    # Extract time series
    def extract_albedo(img):
        """Extract albedo value at point."""
        date = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd')
        albedo = img.select('albedo').reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=30
        ).get('albedo')

        return ee.Feature(None, {
            'date': date,
            'albedo': albedo,
            'sensor': img.get('SPACECRAFT_ID')
        })

    time_series = pipeline.albedo_col.map(extract_albedo)

    # Get first 10 values as example
    values = time_series.limit(10).getInfo()

    print(f"\n✓ Extracted {pipeline.albedo_col.size().getInfo()} albedo values")
    print("\nFirst 10 values:")
    for i, feat in enumerate(values['features']):
        props = feat['properties']
        print(f"  {i+1}. {props.get('date')}: albedo={props.get('albedo', 'N/A'):.3f} ({props.get('sensor', 'unknown')})")


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 4: Custom Region of Interest
# ══════════════════════════════════════════════════════════════════════════

def example_4_custom_aoi():
    """
    Example 4: Use custom area of interest (Dark Zone).

    This shows how to define a custom study area instead of using
    the default Western Greenland AOI.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Custom AOI (Dark Zone)")
    print("="*70 + "\n")

    # Define dark zone area (example coordinates)
    dark_zone_aoi = ee.Geometry.Polygon([[
        [-50.5, 67.0],
        [-49.5, 67.0],
        [-49.5, 67.5],
        [-50.5, 67.5],
        [-50.5, 67.0]
    ]])

    pipeline = HarmonizationPipeline(
        aoi=dark_zone_aoi,
        date_start='2018-06-01',
        date_end='2018-08-31',
        cloud_cover_max=30
    )

    pipeline.run_complete_pipeline(calculate_albedo=True)

    print(f"\n✓ Dark zone analysis complete")
    print(f"  Images: {pipeline.albedo_col.size().getInfo()}")


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 5: Long Time Series (Full Mission Record)
# ══════════════════════════════════════════════════════════════════════════

def example_5_long_time_series():
    """
    Example 5: Create full multi-decade time series (1984-2023).

    This demonstrates the power of harmonization: combining 40 years
    of data from multiple sensors into a single consistent time series.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Full Multi-Decade Time Series (1984-2023)")
    print("="*70 + "\n")

    pipeline = HarmonizationPipeline(
        date_start='1984-01-01',  # Landsat 5 start
        date_end='2023-12-31',
        cloud_cover_max=50
    )

    # Note: This will process A LOT of images
    # Consider using date ranges or exporting incrementally

    print("⚠ Warning: This will process ~40 years of data")
    print("  Consider breaking into smaller time periods for initial testing\n")

    pipeline.step2_harmonize_all_sensors()

    print(f"\n✓ Long time series created")
    print(f"  Total images: {pipeline.unified_col.size().getInfo()}")
    print(f"  Temporal span: 1984-2023 (40 years)")


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 6: Export Results to Google Drive
# ══════════════════════════════════════════════════════════════════════════

def example_6_export():
    """
    Example 6: Export harmonized albedo to Google Drive.

    This shows how to export results for offline analysis.
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: Export to Google Drive")
    print("="*70 + "\n")

    pipeline = HarmonizationPipeline(
        date_start='2020-07-01',
        date_end='2020-07-31',  # Just July 2020
        cloud_cover_max=20
    )

    # Run pipeline
    pipeline.step2_harmonize_all_sensors()
    pipeline.step3_calculate_albedo()

    # Export albedo (limit to 10 images for example)
    tasks = pipeline.step4_export_results(
        export_folder='HSA_July2020_Example',
        export_type='albedo',
        start_exports=False,  # Set to True to actually start
        max_images=10
    )

    print(f"\n✓ Export tasks prepared: {len(tasks)}")
    print("  To start exports, set start_exports=True")
    print("\nManually start exports:")
    print("  for task in tasks:")
    print("      task.start()")


# ══════════════════════════════════════════════════════════════════════════
# EXAMPLE 7: Validation Against AWS Data
# ══════════════════════════════════════════════════════════════════════════

def example_7_aws_validation():
    """
    Example 7: Extract satellite albedo for validation against AWS measurements.

    This replicates the validation workflow from the paper.
    """
    print("\n" + "="*70)
    print("EXAMPLE 7: Validation Against AWS")
    print("="*70 + "\n")

    initialize_gee()

    # Example AWS locations (from PROMICE network)
    aws_locations = {
        'KAN_M': {'lon': -50.13, 'lat': 67.07},
        'KAN_U': {'lon': -47.03, 'lat': 67.00},
        'QAS_L': {'lon': -46.85, 'lat': 61.03}
    }

    results = {}

    for aws_name, coords in aws_locations.items():
        print(f"\nProcessing {aws_name}...")

        point = ee.Geometry.Point([coords['lon'], coords['lat']])

        pipeline = HarmonizationPipeline(
            aoi=point.buffer(90),  # 90m window (3x3 pixels at 30m)
            date_start='2020-06-01',
            date_end='2020-08-31',
            cloud_cover_max=30
        )

        pipeline.step2_harmonize_all_sensors()
        pipeline.step3_calculate_albedo()

        # Extract mean albedo values
        def get_albedo(img):
            albedo = img.select('albedo').reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point.buffer(90),
                scale=30
            ).get('albedo')

            return img.set('extracted_albedo', albedo)

        albedo_col = pipeline.albedo_col.map(get_albedo)
        results[aws_name] = albedo_col.size().getInfo()

        print(f"  ✓ Extracted {results[aws_name]} albedo values")

    print(f"\n✓ Validation data extracted for {len(aws_locations)} AWS sites")


# ══════════════════════════════════════════════════════════════════════════
# MAIN: Run All Examples
# ══════════════════════════════════════════════════════════════════════════

def main():
    """
    Run examples interactively.

    Uncomment the examples you want to run.
    """
    print("\n" + "#"*70)
    print("# UNIFIED PYTHON HARMONIZATION PIPELINE - USAGE EXAMPLES")
    print("#"*70)

    # Uncomment examples to run:

    # example_1_simple_harmonization()
    # example_2_with_albedo()
    # example_3_point_time_series()
    # example_4_custom_aoi()
    # example_5_long_time_series()  # WARNING: Processes 40 years of data!
    # example_6_export()
    # example_7_aws_validation()

    print("\n" + "#"*70)
    print("# Examples complete!")
    print("# Uncomment the examples you want to run in main()")
    print("#"*70 + "\n")


if __name__ == '__main__':
    # Run a specific example
    import sys

    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        examples = {
            '1': example_1_simple_harmonization,
            '2': example_2_with_albedo,
            '3': example_3_point_time_series,
            '4': example_4_custom_aoi,
            '5': example_5_long_time_series,
            '6': example_6_export,
            '7': example_7_aws_validation
        }

        if example_num in examples:
            examples[example_num]()
        else:
            print(f"Unknown example: {example_num}")
            print(f"Available examples: {', '.join(examples.keys())}")
    else:
        print("\nUsage: python example_usage.py <example_number>")
        print("\nAvailable examples:")
        print("  1 - Simple harmonization for one year")
        print("  2 - Complete workflow with albedo")
        print("  3 - Extract point time series")
        print("  4 - Custom area of interest")
        print("  5 - Long time series (1984-2023)")
        print("  6 - Export to Google Drive")
        print("  7 - AWS validation")
        print("\nExample: python example_usage.py 1\n")
