
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import gdal
import glob
import numpy as np
from gdalconst import *
from utils import write_header

def get_origin_minmax(flist):
    """
    Get the minimum and maximum of the tile origins.

    Parameters
    ----------
    flist : list
        List of tile file names (full path).

    Returns
    -------
    mm : list
        List of minima and maxima of the tile origins.
    """

    # -- loop through tiles
    print("getting tile origin minima and maxima...")
    origins = np.zeros((len(flist), 2), dtype=float)
    for ii, fname in enumerate((sorted(flist))):
        tile = gdal.Open(fname, GA_ReadOnly)
        geo  = tile.GetGeoTransform()
        origins[ii] = geo[0], geo[3]

    # -- pull off and return minima and maxima
    xmin, ymin = origins.min(0)
    xmax, ymax = origins.max(0)

    return xmin, ymin, xmax, ymax


if __name__ == "__main__":

    # -- get the list of tile files
    fpattern = os.path.join(os.environ['REBOUND_DATA'], "data_3d")
    fpath    = "%s/*/*.TIF" % (fpattern)
    flist    = sorted(glob.glob(fpath))
    nfiles   = len(flist)
    
    
    # -- initialize the full raster
    xlo, ylo, xhi, yhi = get_origin_minmax(flist)
    nrow   = int(yhi - ylo) + 2048 + 1
    ncol   = int(xhi - xlo) + 2048 + 1
    print("initializing raster...")
    result = np.zeros((nrow, ncol), dtype=float)
    
    
    # -- go through the tiles and make full raster
    sub = np.zeros((2048, 2048), dtype=float)
    for ii, fname in enumerate(sorted(flist)):
        print("\rtile {0:4} of {1:4}...".format(ii + 1, nfiles)), 
        sys.stdout.flush()
        tile = gdal.Open(fname, GA_ReadOnly)
        geo  = tile.GetGeoTransform()
        tile_origin = geo[0], geo[3]
        raster = tile.ReadAsArray()
    
        rind = result.shape[0] - 2048 - int(tile_origin[1] - ylo)
        cind = int(tile_origin[0] - xlo)
    
        sub[...] = result[rind:rind + 2048, cind:cind + 2048]
    
        result[rind:rind + 2048, cind:cind + 2048] = np.maximum(raster, sub)
    
    
    # -- write output to binary file
    params = {"nrow" : nrow, "ncol" : ncol, "rmin" : ylo, "rmax" : yhi, 
              "cmin" : xlo, "cmax" : xhi}
    oname  = os.path.join(os.environ["REBOUND_WRITE"], "rasters", 
                          "BK_raster.bin")
    result.tofile(oname)
    write_header(oname, params)
