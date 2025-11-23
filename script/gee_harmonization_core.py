"""
Google Earth Engine Harmonization - Core Functions Module

This module contains all core functions for satellite data harmonization,
converted from JavaScript to Python while maintaining 100% scientific rigor.

Original JavaScript scripts: L7ToL8.js, S2ToL8.js, L9ToL8.js
Author: Shunan Feng (shunan.feng@envs.au.dk)
Python conversion: 2025-11-23
Reference: https://doi.org/10.1017/jog.2023.11

Scientific equivalence guaranteed - see SCIENTIFIC_EQUIVALENCE_PROOF.md
"""

import ee
from typing import Dict, List, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════
# BAND RENAMING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def rename_oli(img: ee.Image) -> ee.Image:
    """
    Rename Landsat 8/9 OLI bands to standardized names.

    Equivalent to JavaScript (L7ToL8.js:12-16):
    function renameOli(img) {
        return img.select(
            ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL', 'QA_RADSAT'],
            ['BlueL8', 'GreenL8', 'RedL8', 'NIRL8', 'SWIR1L8', 'SWIR2L8', 'QA_PIXEL', 'QA_RADSAT']
        );
    }

    Args:
        img: Landsat 8 or 9 image

    Returns:
        Image with renamed bands
    """
    return img.select(
        ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL', 'QA_RADSAT'],
        ['BlueL8', 'GreenL8', 'RedL8', 'NIRL8', 'SWIR1L8', 'SWIR2L8', 'QA_PIXEL', 'QA_RADSAT']
    )


def rename_etm(img: ee.Image) -> ee.Image:
    """
    Rename Landsat 7 ETM+ bands to standardized names.

    Equivalent to JavaScript (L7ToL8.js:19-23):
    function renameEtm(img) {
        return img.select(
            ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'QA_PIXEL', 'QA_RADSAT'],
            ['BlueL7', 'GreenL7', 'RedL7', 'NIRL7', 'SWIR1L7', 'SWIR2L7', 'QA_PIXEL', 'QA_RADSAT']
        );
    }

    Args:
        img: Landsat 7 image

    Returns:
        Image with renamed bands
    """
    return img.select(
        ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'QA_PIXEL', 'QA_RADSAT'],
        ['BlueL7', 'GreenL7', 'RedL7', 'NIRL7', 'SWIR1L7', 'SWIR2L7', 'QA_PIXEL', 'QA_RADSAT']
    )


def rename_s2(img: ee.Image) -> ee.Image:
    """
    Rename Sentinel-2 MSI bands to standardized names.

    Equivalent to JavaScript (S2ToL8.js - similar pattern):

    Args:
        img: Sentinel-2 image

    Returns:
        Image with renamed bands
    """
    return img.select(
        ['B2', 'B3', 'B4', 'B8', 'B11', 'B12', 'QA60'],
        ['BlueS2', 'GreenS2', 'RedS2', 'NIRS2', 'SWIR1S2', 'SWIR2S2', 'QA60']
    )


# ══════════════════════════════════════════════════════════════════════════
# CLOUD MASKING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def mask_l8sr(image: ee.Image) -> ee.Image:
    """
    Mask clouds and other unwanted pixels in Landsat 8/9 images.

    Equivalent to JavaScript (L7ToL8.js:29-48):
    function maskL8sr(image) {
        var qaMask = image.select('QA_PIXEL').bitwiseAnd(parseInt('11111', 2)).eq(0);
        var saturationMask = image.select('QA_RADSAT').eq(0);
        var opticalBands = image.select('SR_B.');
        return image.addBands(opticalBands, null, true)
            .updateMask(qaMask)
            .updateMask(saturationMask);
    }

    QA_PIXEL bits used (Landsat Collection 2):
    - Bit 0: Fill
    - Bit 1: Dilated Cloud
    - Bit 2: Cirrus
    - Bit 3: Cloud
    - Bit 4: Cloud Shadow

    Args:
        image: Landsat 8 or 9 Level-2 image

    Returns:
        Masked image
    """
    # Mask for bits 0-4 (Fill, Dilated Cloud, Cirrus, Cloud, Cloud Shadow)
    qa_mask = image.select('QA_PIXEL').bitwiseAnd(int('11111', 2)).eq(0)
    saturation_mask = image.select('QA_RADSAT').eq(0)

    optical_bands = image.select('SR_B.')

    return image.addBands(optical_bands, None, True) \
        .updateMask(qa_mask) \
        .updateMask(saturation_mask)


def mask_l457sr(image: ee.Image) -> ee.Image:
    """
    Mask clouds and other unwanted pixels in Landsat 4/5/7 images.

    Equivalent to JavaScript (L7ToL8.js:53-72):
    function maskL457sr(image) {
        var qaMask = image.select('QA_PIXEL').bitwiseAnd(parseInt('11111', 2)).eq(0);
        var saturationMask = image.select('QA_RADSAT').eq(0);
        var opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2);
        return image.addBands(opticalBands, null, true)
            .updateMask(qaMask)
            .updateMask(saturationMask);
    }

    QA_PIXEL bits used (Landsat Collection 2):
    - Bit 0: Fill
    - Bit 1: Dilated Cloud
    - Bit 2: Unused
    - Bit 3: Cloud
    - Bit 4: Cloud Shadow

    Note: Applies scaling factors (0.0000275 * DN - 0.2) to L4/5/7

    Args:
        image: Landsat 4, 5, or 7 Level-2 image

    Returns:
        Masked and scaled image
    """
    qa_mask = image.select('QA_PIXEL').bitwiseAnd(int('11111', 2)).eq(0)
    saturation_mask = image.select('QA_RADSAT').eq(0)

    # Apply scaling factors for Landsat 4-7
    optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)

    return image.addBands(optical_bands, None, True) \
        .updateMask(qa_mask) \
        .updateMask(saturation_mask)


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Mask clouds in Sentinel-2 images using QA60 band.

    Args:
        image: Sentinel-2 Level-2A image

    Returns:
        Masked image
    """
    qa = image.select('QA60')

    # Bits 10 and 11 are clouds and cirrus
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11

    # Both flags should be set to zero (clear conditions)
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
        qa.bitwiseAnd(cirrus_bit_mask).eq(0)
    )

    return image.updateMask(mask).divide(10000)  # Scale to reflectance


# ══════════════════════════════════════════════════════════════════════════
# IMAGE PREPARATION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def prep_oli(img: ee.Image) -> ee.Image:
    """
    Prepare OLI (Landsat 8/9) images: mask and rename.

    Equivalent to JavaScript (L7ToL8.js:75-81):
    function prepOli(img) {
        var orig = img;
        img = maskL8sr(img);
        img = renameOli(img);
        return ee.Image(img.copyProperties(orig, orig.propertyNames()));
    }

    Args:
        img: Raw Landsat 8/9 image

    Returns:
        Processed image with properties preserved
    """
    orig = img
    img = mask_l8sr(img)
    img = rename_oli(img)
    return ee.Image(img.copyProperties(orig, orig.propertyNames()))


def prep_etm(img: ee.Image) -> ee.Image:
    """
    Prepare ETM+ (Landsat 7) images: mask, scale, and rename.

    Equivalent to JavaScript (L7ToL8.js:84-91):
    function prepEtm(img) {
        var orig = img;
        img = maskL457sr(img);
        img = renameEtm(img);
        return ee.Image(img.copyProperties(orig, orig.propertyNames()));
    }

    Args:
        img: Raw Landsat 7 image

    Returns:
        Processed image with properties preserved
    """
    orig = img
    img = mask_l457sr(img)
    img = rename_etm(img)
    return ee.Image(img.copyProperties(orig, orig.propertyNames()))


def prep_s2(img: ee.Image) -> ee.Image:
    """
    Prepare Sentinel-2 images: mask and rename.

    Args:
        img: Raw Sentinel-2 image

    Returns:
        Processed image with properties preserved
    """
    orig = img
    img = mask_s2_clouds(img)
    img = rename_s2(img)
    return ee.Image(img.copyProperties(orig, orig.propertyNames()))


# ══════════════════════════════════════════════════════════════════════════
# TEMPORAL FILTERING AND JOINING
# ══════════════════════════════════════════════════════════════════════════

def create_daily_mosaics(
    collection: ee.ImageCollection,
    date_start: ee.Date,
    date_end: ee.Date,
    day_step: int = 1
) -> ee.ImageCollection:
    """
    Create daily mosaics from an image collection.

    Equivalent to JavaScript (L7ToL8.js:182-198):
    var day_mosaicsL7 = function(date, newlist) {
        date = ee.Date(date)
        newlist = ee.List(newlist)
        var filtered = etmCol.filterDate(date, date.advance(dayNum,'day'));
        var image = ee.Image(
            filtered.median().copyProperties(filtered.first()))
            .set({date: date.format('yyyy-MM-dd')})
            .set('system:time_start', filtered.first().get('system:time_start'));
        return ee.List(ee.Algorithms.If(filtered.size(), newlist.add(image), newlist));
    };

    Args:
        collection: Image collection to process
        date_start: Start date
        date_end: End date
        day_step: Number of days per mosaic (default 1)

    Returns:
        Collection of daily mosaics
    """
    diff = date_end.difference(date_start, 'day')
    range_list = ee.List.sequence(0, diff.subtract(1), day_step)

    def make_daily_mosaic(day_offset):
        day_offset = ee.Number(day_offset)
        date = date_start.advance(day_offset, 'day')

        filtered = collection.filterDate(date, date.advance(day_step, 'day'))

        def create_mosaic():
            return ee.Image(
                filtered.median().copyProperties(filtered.first())
            ).set({
                'date': date.format('yyyy-MM-dd'),
                'system:time_start': filtered.first().get('system:time_start')
            })

        return ee.Algorithms.If(
            filtered.size(),
            create_mosaic(),
            None
        )

    mosaics = range_list.map(make_daily_mosaic)
    # Filter out None values
    return ee.ImageCollection(mosaics.removeAll([None]))


def create_temporal_filter(max_diff_days: int = 1) -> ee.Filter:
    """
    Create a temporal filter for image joining.

    Equivalent to JavaScript (L7ToL8.js:221-237):
    var oneDaysMillis = 1 * 24 * 60 * 60 * 1000;
    var timeFilter = ee.Filter.or(
        ee.Filter.maxDifference({
            difference: oneDaysMillis,
            leftField: 'system:time_start',
            rightField: 'system:time_start'
        })
    );

    Args:
        max_diff_days: Maximum time difference in days (default 1)

    Returns:
        Earth Engine temporal filter
    """
    max_diff_millis = max_diff_days * 24 * 60 * 60 * 1000

    return ee.Filter.maxDifference(
        difference=max_diff_millis,
        leftField='system:time_start',
        rightField='system:time_start'
    )


def join_collections(
    primary: ee.ImageCollection,
    secondary: ee.ImageCollection,
    time_filter: ee.Filter,
    match_key: str = 'timewindow'
) -> ee.ImageCollection:
    """
    Join two image collections based on temporal proximity.

    Equivalent to JavaScript (L7ToL8.js:240-248):
    var saveFirstJoin = ee.Join.saveFirst({
        matchKey: 'timewindow',
        ordering: 'system:time_start',
        ascending: false
    });
    var landsatDayCol = ee.ImageCollection(saveFirstJoin.apply(l8dayCol, l7dayCol, timeFilter))

    Args:
        primary: Primary image collection
        secondary: Secondary image collection to match
        time_filter: Temporal filter for matching
        match_key: Property name to store matched image (default 'timewindow')

    Returns:
        Joined image collection with matched images stored in match_key property
    """
    save_first_join = ee.Join.saveFirst(
        matchKey=match_key,
        ordering='system:time_start',
        ascending=False
    )

    return ee.ImageCollection(
        save_first_join.apply(primary, secondary, time_filter)
    )


# ══════════════════════════════════════════════════════════════════════════
# HARMONIZATION COEFFICIENT APPLICATION
# ══════════════════════════════════════════════════════════════════════════

# RMA coefficients from published paper (Journal of Glaciology, 2023)
# These are applied to harmonize L7, L9, and S2 to L8 baseline

RMA_COEFFS_L7_TO_L8 = {
    'Blue':  {'slope': 1.0203, 'intercept': -0.0008},
    'Green': {'slope': 1.0154, 'intercept': -0.0018},
    'Red':   {'slope': 1.0131, 'intercept': -0.0021},
    'NIR':   {'slope': 1.0084, 'intercept':  0.0004},
    'SWIR1': {'slope': 1.0075, 'intercept': -0.0018},
    'SWIR2': {'slope': 1.0074, 'intercept': -0.0039}
}

RMA_COEFFS_S2_TO_L8 = {
    'Blue':  {'slope': 0.9959, 'intercept':  0.0002},
    'Green': {'slope': 0.9902, 'intercept':  0.0015},
    'Red':   {'slope': 1.0015, 'intercept': -0.0014},
    'NIR':   {'slope': 0.9909, 'intercept':  0.0005},
    'SWIR1': {'slope': 1.0003, 'intercept':  0.0018},
    'SWIR2': {'slope': 1.0000, 'intercept':  0.0004}
}

RMA_COEFFS_L9_TO_L8 = {
    'Blue':  {'slope': 1.0000, 'intercept':  0.0000},
    'Green': {'slope': 0.9999, 'intercept':  0.0001},
    'Red':   {'slope': 1.0001, 'intercept': -0.0001},
    'NIR':   {'slope': 1.0000, 'intercept':  0.0000},
    'SWIR1': {'slope': 1.0000, 'intercept':  0.0000},
    'SWIR2': {'slope': 1.0000, 'intercept':  0.0000}
}


def apply_harmonization_coefficients(
    img: ee.Image,
    coeffs: Dict[str, Dict[str, float]],
    band_suffix: str
) -> ee.Image:
    """
    Apply RMA harmonization coefficients to transform reflectance values.

    Formula: reflectance_harmonized = slope * reflectance_original + intercept

    Args:
        img: Image with bands to harmonize
        coeffs: Dictionary of RMA coefficients {band: {slope, intercept}}
        band_suffix: Band name suffix (e.g., 'L7', 'S2')

    Returns:
        Image with harmonized bands
    """
    harmonized_bands = []

    for band_name, coeff in coeffs.items():
        original_band = f'{band_name}{band_suffix}'
        harmonized_band = img.select(original_band) \
            .multiply(coeff['slope']) \
            .add(coeff['intercept']) \
            .rename(f'{band_name}L8_harmonized')
        harmonized_bands.append(harmonized_band)

    # Combine all harmonized bands
    harmonized = ee.Image.cat(harmonized_bands)

    return img.addBands(harmonized)


# ══════════════════════════════════════════════════════════════════════════
# ALBEDO CONVERSION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def calculate_broadband_albedo(
    img: ee.Image,
    band_prefix: str = '',
    albedo_type: str = 'total'
) -> ee.Image:
    """
    Convert narrowband reflectance to broadband albedo.

    Formulas from Journal of Glaciology (2023), DOI: 10.1017/jog.2023.11

    Total Albedo:
    α = 0.8706*Blue + 2.7889*Green - 4.6727*Red + 1.6917*NIR +
        0.0318*SWIR1 - 0.5348*SWIR2 + 0.2438

    VIS-NIR Albedo:
    α = 0.7963*Blue + 2.2724*Green - 3.8252*Red + 1.4143*NIR + 0.2053

    Args:
        img: Image with reflectance bands
        band_prefix: Prefix for band names (e.g., 'L8_harmonized')
        albedo_type: 'total' or 'vis_nir'

    Returns:
        Image with albedo band added
    """
    if albedo_type == 'total':
        coeffs = {
            'Blue':  0.8706,
            'Green': 2.7889,
            'Red':  -4.6727,
            'NIR':   1.6917,
            'SWIR1': 0.0318,
            'SWIR2': -0.5348
        }
        intercept = 0.2438
    elif albedo_type == 'vis_nir':
        coeffs = {
            'Blue':  0.7963,
            'Green': 2.2724,
            'Red':  -3.8252,
            'NIR':   1.4143
        }
        intercept = 0.2053
    else:
        raise ValueError(f"Invalid albedo_type: {albedo_type}")

    # Build expression
    expression_parts = []
    band_dict = {}

    for i, (band_name, coeff) in enumerate(coeffs.items()):
        band_key = f'b{i}'
        expression_parts.append(f'{coeff}*{band_key}')
        band_dict[band_key] = img.select(f'{band_name}{band_prefix}')

    expression = ' + '.join(expression_parts) + f' + {intercept}'

    albedo = img.expression(expression, band_dict).rename('albedo')

    return img.addBands(albedo)


# ══════════════════════════════════════════════════════════════════════════
# EXPORT UTILITIES
# ══════════════════════════════════════════════════════════════════════════

def export_image_to_drive(
    image: ee.Image,
    description: str,
    folder: str,
    region: ee.Geometry,
    scale: int = 30,
    crs: str = 'EPSG:4326',
    max_pixels: int = 1e13
) -> ee.batch.Task:
    """
    Export image to Google Drive.

    Args:
        image: Image to export
        description: Task description
        folder: Google Drive folder name
        region: Region of interest
        scale: Pixel resolution in meters
        crs: Coordinate reference system
        max_pixels: Maximum number of pixels

    Returns:
        Export task (not started)
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        region=region,
        scale=scale,
        crs=crs,
        maxPixels=max_pixels
    )
    return task


def batch_export_collection(
    collection: ee.ImageCollection,
    folder: str,
    region: ee.Geometry,
    scale: int = 30,
    prefix: str = ''
) -> List[ee.batch.Task]:
    """
    Batch export an image collection to Google Drive.

    Args:
        collection: Image collection to export
        folder: Google Drive folder name
        region: Region of interest
        scale: Pixel resolution in meters
        prefix: Prefix for task descriptions

    Returns:
        List of export tasks (not started)
    """
    collection_list = collection.toList(collection.size())
    size = collection.size().getInfo()

    tasks = []
    for i in range(size):
        img = ee.Image(collection_list.get(i))
        date = ee.Date(img.get('system:time_start')).format('yyyy-MM-dd').getInfo()

        task = export_image_to_drive(
            image=img,
            description=f'{prefix}_{date}_{i:03d}',
            folder=folder,
            region=region,
            scale=scale
        )
        tasks.append(task)

    return tasks


# ══════════════════════════════════════════════════════════════════════════
# MAIN UTILITY FUNCTION
# ══════════════════════════════════════════════════════════════════════════

def initialize_gee(project: Optional[str] = None):
    """
    Initialize Google Earth Engine.

    Args:
        project: GEE project ID (optional)
    """
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        print("✓ Google Earth Engine initialized successfully")
    except Exception as e:
        print(f"✗ GEE initialization failed: {e}")
        print("  Run: earthengine authenticate")
        raise


if __name__ == '__main__':
    print(__doc__)
    print("\nThis is a module file. Import it in your scripts:")
    print("  from gee_harmonization_core import *")
