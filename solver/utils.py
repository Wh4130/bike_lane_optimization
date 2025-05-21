import numpy as np
import pyproj

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches # Import for Patch
import geopandas as gpd
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "sans-serif",
    "font.sans-serif": "Helvetica",
})


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


def plot_map(name, road_gdf, sol, mu, alpha, B_L, w, tau, scale):


    path = f"solver/output/{name}/{name}_result.png"
    title = f'{name.capitalize().replace("_", " ")}; Solver'
        
        
    plt.rcParams['hatch.color'] = 'gray'


    fig, ax = plt.subplots(1, 1, figsize = (15, 15))
    road_gdf.plot(color = "lightgray", ax = ax, alpha = 0.4)

    road_gdf[road_gdf["has_bike_lane"] == 1].plot(color = "lightgray", ax = ax, alpha = 0.8, label = "existing lanes")

    try:
        sol[(sol["has_bike_lane"] == 1) & (sol["roadType"] == 1)].plot(color = "#66BFF6", ax = ax, edgecolor=None, hatch = "///")
    except:
        pass
    try:
        sol[(sol["has_bike_lane"] == 1) & (sol["roadType"] == 2)].plot(color = "orange", ax = ax, edgecolor=None, hatch = "///")
    except:
        pass
    try:
        sol[(sol["has_bike_lane"] == 0) & (sol["roadType"] == 1)].plot(color = "#66BFF6", ax = ax, edgecolor=None)
    except:
        pass
    try:
        sol[(sol["has_bike_lane"] == 0) & (sol["roadType"] == 2)].plot(color = "orange", ax = ax, edgecolor=None)
    except:
        pass

    ax.set_xlim([121.5, 121.59])
    ax.set_ylim([25, 25.085])

    ax.set_title(title, fontsize = 20)
    ax.grid(True, color='lightgray')


    # Create proxy artists for the legend
    bike_lane_patch_1 = mpatches.Patch(color='#66BFF6', edgecolor=None, label='Type 1')
    bike_lane_patch_2 = mpatches.Patch(color='orange', edgecolor=None, label='Type 2')


    # Add the legend using the proxy artists
    ax.legend(handles=[bike_lane_patch_1, bike_lane_patch_2], loc='upper left')

    for spine in ax.spines.values():
        spine.set_color('lightgray')
    ax.set_aspect('equal')


    text = f"Road Segments filled with Gray Slash / refer to already existing bike lanes" 
    params = rf"$$\mu = {mu};   \alpha = {alpha};   B^L = {B_L};   w = {w};   \tau = {tau};   scale = {scale}$$"
    ax.text(0.5, 0.98, text,
            horizontalalignment='center', 
            verticalalignment='top',      
            transform=ax.transAxes,       
            fontsize=12,
            color='#423D3D')
    ax.text(0.5, 0.96, params,
            horizontalalignment='center', 
            verticalalignment='top',      
            transform=ax.transAxes,       
            fontsize=15,
            color='black')

    fig.savefig(path, dpi=300, bbox_inches='tight')