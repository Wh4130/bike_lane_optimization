import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from tqdm import tqdm

import xarray as xr
import rioxarray

from localDemand import approxLocalDemand

# --- new imports for road‐network overlay
import osmnx as ox
import pyproj


def spawnDemand(ds, location, demandDistribution, magnitude=1):
    (x_pos, y_pos) = location
    
    # 2. compute planar distances r(x,y) in metres ---------------------
    y2d, x2d = xr.broadcast(ds.y_m, ds.x_m)      # 2-D coordinate grids
    r = np.sqrt((x2d-x_pos)**2 + (y2d-y_pos)**2)                 # Euclidean distance from centre

    # 3. evaluate and store the demand kernel --------------------------
    ds["demand"].loc[:] = ds["demand"].loc[:] + magnitude * demandDistribution(r, alpha=0.5)
    
    return ds
    

def stationData():
    # Load the pivot tables
    df_tripOrigin_X = pd.read_parquet("../data/processed/travelMatrix_originX.parquet")  
    df_tripOrigin_Y = pd.read_parquet("../data/processed/travelMatrix_originY.parquet")  
    df_tripNumber = pd.read_parquet("../data/processed/travelMatrix_sum.parquet")  

    # 2.  keep only the (now filled) first column
    stations = pd.DataFrame()
    stations["lon"] = df_tripOrigin_X.bfill(axis=1).iloc[:, [0]]
    stations["lat"] = df_tripOrigin_Y.bfill(axis=1).iloc[:, [0]]
    stations["totalTrips"] = df_tripNumber.sum(axis=1).to_numpy()
    
    print(stations["totalTrips"].sum(), stations.info())
    
    return stations


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

if __name__ == "__main__":
    useCached = False  # whether to use previously cached grid or recalculate

    if not useCached:
        # 1. build a 2-D Cartesian field in metres (y, x)  -----------------
        half_sz  = 10_000                      # half-width = 10 km
        
        # set for 100 m grid size
        nx, ny   = int(half_sz / 50), int(half_sz / 50)   # grid shape
        x_m = np.linspace(-half_sz,  half_sz, nx)
        y_m = np.linspace(-half_sz,  half_sz, ny)
        
        ds = xr.Dataset(
            data_vars=dict(
                demand=(["y_m", "x_m"],
                        np.zeros((ny, nx), dtype="float32"),
                        {"units": "1", "long_name": "demand"})
            ),
            coords=dict(
                y_m=("y_m", y_m, {"units": "m", "long_name": "northing rel. centre"}),
                x_m=("x_m", x_m, {"units": "m", "long_name": "easting  rel. centre"})
            ),
            attrs=dict(title="Bike-demand model, local Cartesian frame (Taipei)")
        )

        stations = stationData()
        for stop_id, lat, lon, trips in tqdm(zip(stations.index,
                                                stations["lat"],
                                                stations["lon"],
                                                stations["totalTrips"]),
                                            total=len(stations)):
            (x, y) = latlon_to_xy(lat, lon)
            ds = spawnDemand(ds, (x, y), approxLocalDemand, magnitude=trips)
    else:
        ds = xr.open_dataset("demandModel_metreGrid.nc")
        
    # --- plot the demand grid + overlay road network
    plt.figure(figsize=(6, 5))
    ax = plt.gca()

    # base heatmap
    ds.demand.plot(
        cmap="YlOrRd", 
        cbar_kwargs=dict(label="Demand score [–]")
    )

    # overlay Taipei road network
    # determine search radius from grid extents
    half_sz = max(abs(ds['x_m'].values).max(), abs(ds['y_m'].values).max())
    
    # compute geographic centre from station data
    #from globalDemand import stationData
    #stations = stationData()
    #center_lat = stations['lat'].mean()
    #center_lon = stations['lon'].mean()
    center_lat = 25.03750
    center_lon = 121.56444
    
    # grab and project the graph
    G = ox.graph_from_point((center_lat, center_lon), dist=half_sz, network_type='drive')
    G = ox.project_graph(G)
    # convert to GeoDataFrame of edges
    edges = ox.graph_to_gdfs(G, nodes=False)
    # map centre lon/lat into graph CRS and shift to grid-relative coords
    proj = pyproj.Proj(G.graph['crs'])
    center_x, center_y = proj(center_lon, center_lat)
    edges['geometry'] = edges['geometry'].translate(xoff=-center_x, yoff=-center_y)
    # draw network on top
    edges.plot(ax=ax, linewidth=0.5, edgecolor='black', alpha=0.5)

    plt.title("Bike-demand kernel (Cartesian metres, Taipei centre)")
    plt.xlabel("Easting x [m]")
    plt.ylabel("Northing y [m]")
    plt.tight_layout()
    plt.show()
