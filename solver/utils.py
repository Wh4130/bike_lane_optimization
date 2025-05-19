import numpy as np
import pyproj

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

def proj_to_xy(gdf, type):
    GDF = gdf.copy()
    center_lat = 25.03750
    center_lon = 121.56444
    proj = pyproj.Proj(proj="aeqd", lat_0=center_lat, lon_0=center_lon, units="m")  # 方位等距投影
    project = lambda lon, lat: proj(lon, lat)

    if type == "road":
        centroids = GDF.geometry.centroid
        x, y = project(centroids.x.values, centroids.y.values)
    else:
        x, y = project(GDF.geometry.x.values, GDF.geometry.y.values)

    GDF["x"] = x
    GDF["y"] = y
    return GDF




def euclidean_n2(q: tuple, road: tuple):
    
    dist =  (q[0] - road[0]) ** 2 + (q[1] - road[1]) ** 2
    
    return dist