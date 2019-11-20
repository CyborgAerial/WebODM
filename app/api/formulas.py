# Algos from https://github.com/dirceup/tiled-vegetation-indices/blob/master/app/lib/vegetation_index.rb
# Functions can use all of the supported functions and operators from
# https://numexpr.readthedocs.io/en/latest/user_guide.html#supported-operators

import re
from functools import lru_cache

algos = {
    'VARI': {
        'expr': '(G - R) / (G + R - B)',
        'help': 'Visual Atmospheric Resistance Index shows the areas of vegetation.'
    },
    'NDVI': {
        'expr': '(N - R) / (N + R)',
        'help': 'Normalized Difference Vegetation Index shows the amount of green vegetation.'
    },
    'BAI': {
        'expr': '1.0 / (((0.1 - R) ** 2) + ((0.06 - N) ** 2))',
        'help': 'Burn Area Index hightlights burned land in the red to near-infrared spectrum.'
    },
    'GLI': {
        'expr': '((G * 2) - R - B) / ((G * 2) + R + B)',
        'help': 'Green Leaf Index shows greens leaves and stems.'
    },
    'GNDVI':{
        'expr': '(N - G) / (N + G)',
        'help': 'Green Normalized Difference Vegetation Index is similar to NDVI, but measures the green spectrum instead of red.'
    },
    'GRVI':{
        'expr': 'N / G',
        'help': 'Green Ratio Vegetation Index is sensitive to photosynthetic rates in forests.'
    },
    'SAVI':{
        'expr': '(1.5 * (N - R)) / (N + R + 0.5)',
        'help': 'Soil Adjusted Vegetation Index is similar to NDVI but attempts to remove the effects of soil areas using an adjustment factor (0.5).'
    },
    'MNLI':{
        'expr': '((N ** 2 - R) * 1.5) / (N ** 2 + R + 0.5)',
        'help': 'Modified Non-Linear Index improves the Non-Linear Index algorithm to account for soil areas.'
    },
    'MSR': {
        'expr': '((N / R) - 1) / (sqrt(N / R) + 1)',
        'help': 'Modified Simple Ratio is an improvement of the Simple Ratio (SR) index to be more sensitive to vegetation.'
    },
    'RDVI': {
        'expr': '(N - R) / sqrt(N + R)',
        'help': 'Renormalized Difference Vegetation Index uses the difference between near-IR and red, plus NDVI to show areas of healthy vegetation.'
    },
    'TDVI': {
        'expr': '1.5 * ((N - R) / sqrt(N ** 2 + R + 0.5))',
        'help': 'Transformed Difference Vegetation Index highlights vegetation cover in urban environments.'
    },
    'OSAVI': {
        'expr': '(N - R) / (N + R + 0.16)',
        'help': 'Optimized Soil Adjusted Vegetation Index is based on SAVI, but tends to work better in areas with little vegetation where soil is visible.'
    },
    'LAI': {
        'expr': '3.618 * (2.5 * (N - R) / (N + 6*R - 7.5*B + 1)) * 0.118',
        'help': 'Leaf Area Index estimates foliage areas and predicts crop yields.'
    },
    'EVI': {
        'expr': '2.5 * (N - R) / (N + 6*R - 7.5*B + 1)',
        'help': 'Enhanced Vegetation Index is useful in areas where NDVI might saturate, by using blue wavelengths to correct soil signals.'
    },

    # more?

    '_TESTRB': {
        'expr': 'R + B'
    },

    '_TESTFUNC': {
        'expr': 'R + (sqrt(B) )'
    }
}

camera_filters = [
    'RGB',
    'NRG',
    'NGB',
    'RGN',
    # more?
]

@lru_cache(maxsize=20)
def lookup_formula(algo, band_order = 'RGB'):
    if algo is None:
        return None
    if band_order is None:
        band_order = 'RGB'

    if algo not in algos:
        raise ValueError("Cannot find algorithm " + algo)

    input_bands = tuple(band_order)

    def repl(matches):
        b = matches.group(1)
        try:
            return 'b' + str(input_bands.index(b) + 1)
        except ValueError:
            raise ValueError("Cannot find band \"" + b + "\" from \"" + band_order + "\". Choose a proper band order.")

    return re.sub("([A-Z]+?[a-z]*)", repl, re.sub("\s+", "", algos[algo]['expr']))

def get_algorithm_list():
    return [{'id': k, **algos[k]} for k in algos if not k.startswith("_")]

def get_camera_filters_list():
    return camera_filters
