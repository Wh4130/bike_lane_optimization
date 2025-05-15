import numpy as np
import geopandas as gpd
import pandas as pd
import xarray as xr

def latlon_to_xy(lat, lon, ref_lat=25.03752, ref_lon=121.56368, radius=6371000.0):
    """
    Convert geographic coordinates (deg) to local Cartesian offsets (m)
    relative to (ref_lat, ref_lon).

    Returns
    -------
    dx, dy   Easting (m), northing (m); positive dx=east, dy=north.
    """
    # cast to ndarray for broadcasting
    lat  = np.asanyarray(lat, dtype=float)
    lon  = np.asanyarray(lon, dtype=float)

    # --- 1. degrees → radians
    lat_rad  = np.deg2rad(lat)
    lon_rad  = np.deg2rad(lon)
    ref_lat_rad = np.deg2rad(ref_lat)
    ref_lon_rad = np.deg2rad(ref_lon)

    # --- 2. small-angle planar approximation
    dlat  = lat_rad - ref_lat_rad
    dlon  = lon_rad - ref_lon_rad

    # scale longitude by cos(average latitude)
    mean_lat = (lat_rad + ref_lat_rad) * 0.5
    dy = radius * dlat                        # north-south
    dx = radius * dlon * np.cos(mean_lat)     # east-west

    return dx, dy


def getDemandGrid():
    '''
    Description: Load "Demand Grid" data for query
    '''
    ds_DangerGrid   = xr.open_dataset("roadProcessing/output/car_accident_grid.nc")
    return ds_DangerGrid

def get_line_sample_points(line, spacing=10):
    '''
    Description: Split shapely.geometry.LineString object into a list of Point objects

    args: 
        - line:     shapely.geometry.LineString
        - spacing:  the spacing that you want to cut the string

    return:
        - [shapely.geometry.Point]
    '''

    length = line.length
    num_points = int(length // spacing) + 1
    return [line.interpolate(dist) for dist in np.linspace(0, length, num_points)]
    
    
def get_demand_intersect(demand_grid, inter_geom, geotype):
    '''
    Description: Get demand for intersection of roads

    args: 
        - demand_grid: Demand Grid dataset for demand querying
        - inter_geom:  the shapely.geometry object 
        - geotype:     string. should be either "Point" or "LineString"

    return:
        {
            "n": <the number of points for which the demand is calculated>,
            "total_demand": <sum of the demand calculated for the n points>
        }

        (if the geotype is "Point", then n = 1)
    '''
    assert geotype in ["Point", "LineString"], "Can only process 'Point' or 'LineString'"

    if geotype == "Point":
        lon, lat    = inter_geom.x, inter_geom.y
        x, y        = latlon_to_xy(lat, lon)
        demand = demand_grid['demand'].sel(x_m = x, y_m = y, method='nearest').values
        result = {"n": 1, "total_demand": demand}

    elif geotype == "LineString":
        demand = 0
        points = get_line_sample_points(inter_geom)
        for p in points:
            x, y   = latlon_to_xy(p.y, p.x)
            demand += demand_grid['demand'].sel(x_m = x, y_m = y, method='nearest').values
        result = {"n": len(points), "total_demand": demand}


    return result