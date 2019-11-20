import rasterio
import urllib
from django.http import HttpResponse
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.mercator import get_zooms
from rio_tiler import main
from rio_tiler.utils import array_to_image, get_colormap, expression, linear_rescale, _chunks, _apply_discrete_colormap
from rio_tiler.profiles import img_profiles

import numpy as np

from .hsvblend import hsv_blend
from .hillshade import LightSource
from .formulas import lookup_formula, get_algorithm_list, get_camera_filters_list
from .tasks import TaskNestedView
from rest_framework import exceptions
from rest_framework.response import Response


def get_tile_url(task, tile_type, query_params):
    url = '/api/projects/{}/tasks/{}/{}/tiles/{{z}}/{{x}}/{{y}}.png'.format(task.project.id, task.id, tile_type)
    params = {}

    for k in ['formula', 'bands', 'rescale', 'color_map', 'hillshade']:
        if query_params.get(k):
            params[k] = query_params.get(k)

    if len(params) > 0:
        url = url + '?' + urllib.parse.urlencode(params)

    return url

def get_extent(task, tile_type):
    extent_map = {
        'orthophoto': task.orthophoto_extent,
        'dsm': task.dsm_extent,
        'dtm': task.dtm_extent,
    }

    if not tile_type in extent_map:
        raise exceptions.ValidationError("Type {} is not a valid tile type".format(tile_type))

    extent = extent_map[tile_type]

    if extent is None:
        raise exceptions.ValidationError(
            "A {} has not been processed for this task. Tiles are not available.".format(tile_type))

    return extent

def get_raster_path(task, tile_type):
    return task.get_asset_download_path(tile_type + ".tif")


def rescale_tile(tile, mask, rescale = None):
    if rescale:
        rescale_arr = list(map(float, rescale.split(",")))
        rescale_arr = list(_chunks(rescale_arr, 2))
        if len(rescale_arr) != tile.shape[0]:
            rescale_arr = ((rescale_arr[0]),) * tile.shape[0]
        for bdx in range(tile.shape[0]):
            tile[bdx] = np.where(
                mask,
                linear_rescale(
                    tile[bdx], in_range=rescale_arr[bdx], out_range=[0, 255]
                ),
                0,
            )
        tile = tile.astype(np.uint8)

    return tile, mask


def apply_colormap(tile, color_map = None):
    if color_map is not None and isinstance(color_map, dict):
        tile = _apply_discrete_colormap(tile, color_map)
    elif color_map is not None:
        tile = np.transpose(color_map[tile][0], [2, 0, 1]).astype(np.uint8)

    return tile

class TileJson(TaskNestedView):
    def get(self, request, pk=None, project_pk=None, tile_type=""):
        """
        Get tile.json for this tasks's asset type
        """
        task = self.get_and_check_task(request, pk)

        raster_path = get_raster_path(task, tile_type)
        with rasterio.open(raster_path) as src_dst:
            minzoom, maxzoom = get_zooms(src_dst)

        return Response({
            'tilejson': '2.1.0',
            'name': task.name,
            'version': '1.0.0',
            'scheme': 'xyz',
            'tiles': [get_tile_url(task, tile_type, self.request.query_params)],
            'minzoom': minzoom,
            'maxzoom': maxzoom,
            'bounds': get_extent(task, tile_type).extent
        })

class Bounds(TaskNestedView):
    def get(self, request, pk=None, project_pk=None, tile_type=""):
        """
        Get the bounds for this tasks's asset type
        """
        task = self.get_and_check_task(request, pk)

        return Response({
            'url': get_tile_url(task, tile_type, self.request.query_params),
            'bounds': get_extent(task, tile_type).extent
        })

class Metadata(TaskNestedView):
    def get(self, request, pk=None, project_pk=None, tile_type=""):
        """
        Get the metadata for this tasks's asset type
        """
        task = self.get_and_check_task(request, pk)

        expr = lookup_formula(self.request.query_params.get('formula'), self.request.query_params.get('bands'))
        color_map = self.request.query_params.get('color_map')

        pmin, pmax = 2.0, 98.0
        raster_path = get_raster_path(task, tile_type)
        info = main.metadata(raster_path, pmin=pmin, pmax=pmax, histogram_bins=64, expr=expr)


        if tile_type == 'plant':
            info['algorithms'] = get_algorithm_list(),
            info['filters'] = get_camera_filters_list()

        del info['address']
        info['name'] = task.name
        info['scheme'] = 'xyz'
        info['tiles'] = [get_tile_url(task, tile_type, self.request.query_params)]

        if color_map:
            try:
                color_map = get_colormap(color_map, format="gdal")
                info['color_map'] = color_map
            except FileNotFoundError:
                raise exceptions.ValidationError("Not a valid color_map value")

        return Response(info)

def get_elevation_tiles(elevation, url, x, y, z, tilesize, nodata):
    tile = np.full((tilesize * 3, tilesize * 3), nodata, dtype=elevation.dtype)

    try:
        left, _ = main.tile(url, x - 1, y, z, indexes=1, tilesize=tilesize, nodata=nodata)
        tile[tilesize:tilesize*2,0:tilesize] = left
    except TileOutsideBounds:
        pass

    try:
        right, _ = main.tile(url, x + 1, y, z, indexes=1, tilesize=tilesize, nodata=nodata)
        tile[tilesize:tilesize*2,tilesize*2:tilesize*3] = right
    except TileOutsideBounds:
        pass

    try:
        bottom, _ = main.tile(url, x, y + 1, z, indexes=1, tilesize=tilesize, nodata=nodata)
        tile[tilesize*2:tilesize*3,tilesize:tilesize*2] = bottom
    except TileOutsideBounds:
        pass

    try:
        top, _ = main.tile(url, x, y - 1, z, indexes=1, tilesize=tilesize, nodata=nodata)
        tile[0:tilesize,tilesize:tilesize*2] = top
    except TileOutsideBounds:
        pass

    tile[tilesize:tilesize*2,tilesize:tilesize*2] = elevation

    return tile


class Tiles(TaskNestedView):
    def get(self, request, pk=None, project_pk=None, tile_type="", z="", x="", y="", scale=1):
        """
        Get a tile image
        """
        task = self.get_and_check_task(request, pk)

        z = int(z)
        x = int(x)
        y = int(y)
        scale = int(scale)
        ext = "png"
        driver = "jpeg" if ext == "jpg" else ext

        indexes = None
        nodata = None

        expr = lookup_formula(self.request.query_params.get('formula'), self.request.query_params.get('bands'))
        rescale = self.request.query_params.get('rescale')
        color_map = self.request.query_params.get('color_map')
        hillshade = self.request.query_params.get('hillshade')

        # TODO: server-side expressions

        if tile_type in ['dsm', 'dtm'] and rescale is None:
            raise exceptions.ValidationError("Cannot get tiles without rescale parameter. Add ?rescale=min,max to the URL.")

        if tile_type in ['dsm', 'dtm'] and color_map is None:
            color_map = "gray"

        if nodata is not None:
            nodata = np.nan if nodata == "nan" else float(nodata)
        tilesize = scale * 256

        url = get_raster_path(task, tile_type)

        try:
            if expr is not None:
                tile, mask = expression(
                    url, x, y, z, expr=expr, tilesize=tilesize, nodata=nodata
                )
            else:
                tile, mask = main.tile(
                    url, x, y, z, indexes=indexes, tilesize=tilesize, nodata=nodata
                )
        except TileOutsideBounds:
            raise exceptions.NotFound("Outside of bounds")

        # Use alpha channel for transparency, don't use the mask if one is provided (redundant)
        if tile.shape[0] == 4:
            mask = None

        if color_map:
            try:
                color_map = get_colormap(color_map, format="gdal")
            except FileNotFoundError:
                raise exceptions.ValidationError("Not a valid color_map value")

        intensity = None

        if hillshade is not None:
            try:
                hillshade = float(hillshade)
                if hillshade <= 0:
                    hillshade = 1.0
            except ValueError:
                hillshade = 1.0

            if tile.shape[0] != 1:
                raise exceptions.ValidationError("Cannot compute hillshade of non-elevation raster (multiple bands found)")

            with rasterio.open(url) as src:
                minzoom, maxzoom = get_zooms(src)
                z_value = min(maxzoom, max(z, minzoom))
                delta_scale = (maxzoom + 1 - z_value) * 4
                dx = src.meta["transform"][0] * delta_scale
                dy = -src.meta["transform"][4] * delta_scale

            ls = LightSource(azdeg=315, altdeg=45)

            # Hillshading is not a local tile operation and
            # requires neighbor tiles to be rendered seamlessly
            elevation = get_elevation_tiles(tile[0], url, x, y, z, tilesize, nodata)
            intensity = ls.hillshade(elevation, dx=dx, dy=dy, vert_exag=hillshade)
            intensity = intensity[tilesize:tilesize*2,tilesize:tilesize*2]


        rgb, rmask = rescale_tile(tile, mask, rescale=rescale)
        rgb = apply_colormap(rgb, color_map)

        if intensity is not None:
            # Quick check
            if rgb.shape[0] != 3:
                raise exceptions.ValidationError("Cannot process tile: intensity image provided, but no RGB data was computed.")

            intensity = intensity * 255.0
            rgb = hsv_blend(rgb, intensity)

        options = img_profiles.get(driver, {})
        return HttpResponse(
            array_to_image(rgb, rmask, img_format=driver, **options),
            content_type="image/{}".format(ext)
        )