import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from tqdm import tqdm

import xarray as xr
import rioxarray

from localDemand import approxLocalDemand


def spawnDemand(ds, location, demandDistribution, magnitude=1):
    (x_pos, y_pos) = location
    
    # 2. compute planar distances r(x,y) in metres ---------------------
    y2d, x2d = xr.broadcast(ds.y_m, ds.x_m)      # 2-D coordinate grids
    r = np.sqrt((x2d-x_pos)**2 + (y2d-y_pos)**2)                 # Euclidean distance from centre

    # 3. evaluate and store the demand kernel --------------------------
    ds["demand"].loc[:] = ds["demand"].loc[:] + magnitude * demandDistribution(r)
    
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
    useCached = False  # whether to use the previously calcluated demand model from memory or recalculate (somewhat slow)
    
    if useCached == False:
        # 1. build a 2-D Cartesian field in metres (y, x)  -----------------
        half_sz  = 15_000                      # half-width = 10 km
        
        # set for 100 m grid size
        nx, ny   = int(half_sz / 50), int(half_sz / 50)   # grid shape (east-west, north-south)

        x_m = np.linspace(-half_sz,  half_sz, nx)    # metres east of centre
        y_m = np.linspace(-half_sz,  half_sz, ny)    # metres north of centre

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
        # stations = stations.head(200)     # limit number of stations for testing
        
        for stop_id, lat, lon, trips in tqdm(zip(stations.index, stations["lat"], stations["lon"], stations["totalTrips"]), total=len(stations)):
            (x, y) = latlon_to_xy(lat, lon)
            # print(stop_id, lat, lon, x, y, trips)
            ds = spawnDemand(ds, (x, y), approxLocalDemand, magnitude=trips)
        
        
        # 4. (unchanged) save & plot ---------------------------------------
        ds.to_netcdf("demandModel_metreGrid.nc")

    elif useCached == True:
        ds = xr.open_dataset("demandModel_metreGrid.nc")
        
    plt.figure(figsize=(6, 5))
    
    ds.demand.plot(
        cmap="YlOrRd", 
        norm=mcolors.LogNorm(vmin=1e1, vmax=ds.demand.max()),
        cbar_kwargs=dict(label="Demand score [–]")
    )
    
    plt.title("Bike-demand kernel (Cartesian metres, Taipei centre)")
    plt.xlabel("Easting x [m]")
    plt.ylabel("Northing y [m]")
    plt.tight_layout()
    plt.show()