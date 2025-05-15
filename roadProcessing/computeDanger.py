import geopandas as gpd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import osmnx as ox
import pyproj
from tqdm import tqdm
import os
import pandas as pd
from matplotlib.colors import PowerNorm

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs("roadProcessing/output", exist_ok=True)

    # Load car accident CSV and convert to GeoDataFrame (assumed CRS: EPSG:4326)
    df_carAccident = pd.read_csv("./data/car_accident_raw/113年-臺北市A1及A2類交通事故明細.csv", encoding="big5")
    gdf_accident = gpd.GeoDataFrame(
        df_carAccident,
        geometry=gpd.points_from_xy(df_carAccident['座標-X'], df_carAccident['座標-Y']),
        crs='EPSG:4326'
    )

    # Define local Cartesian grid centered around Taipei city center
    center_lat, center_lon = 25.03750, 121.56444
    half_sz = 10_000     # half width of analysis window (10 km)
    grid_size = 50       # grid cell size: 50 meters
    nx, ny = int(half_sz / grid_size), int(half_sz / grid_size)
    x_m = np.linspace(-half_sz, half_sz, nx)
    y_m = np.linspace(-half_sz, half_sz, ny)

    # Create empty grid using xarray
    ds = xr.Dataset(
        data_vars=dict(
            accident=(["y_m", "x_m"],
                    np.zeros((ny, nx), dtype="int32"),
                    {"units": "count", "long_name": "accident count"})
        ),
        coords=dict(
            y_m=("y_m", y_m, {"units": "m", "long_name": "northing from center"}),
            x_m=("x_m", x_m, {"units": "m", "long_name": "easting from center"})
        ),
        attrs=dict(title="Car accident frequency grid (Taipei, local Cartesian)")
    )

    # Define local projection (Azimuthal Equidistant Projection centered on Taipei)
    proj = pyproj.Proj(proj="aeqd", lat_0=center_lat, lon_0=center_lon, units="m")
    project = lambda lon, lat: proj(lon, lat)

    # Project accident points to local Cartesian coordinates
    x, y = project(gdf_accident.geometry.x.values, gdf_accident.geometry.y.values)

    # Map accident points to grid indices
    ix = np.searchsorted(x_m, x)
    iy = np.searchsorted(y_m, y)
    mask = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)

    # Accumulate accident count into grid using vectorized method
    flat_indices = iy[mask] * nx + ix[mask]
    counts = np.bincount(flat_indices, minlength=nx * ny)
    accident_grid = counts.reshape((ny, nx))
    ds['accident'].values = accident_grid

    # Visualization
    plt.figure(figsize=(8, 7))
    ax = plt.gca()

    # Use square root scaling to enhance contrast in low-density areas
    ds.accident.values[ds.accident.values == 0] = 1  # avoid 0 when using PowerNorm
    ds.accident.plot(
        ax=ax,
        cmap="YlOrRd",
        norm=PowerNorm(gamma=0.5),
        cbar_kwargs=dict(label="Accident Count (√ scale)")
    )

    # Export the accident grid to NetCDF
    ds.to_netcdf("roadProcessing/output/car_accident_grid.nc")

    # Retrieve and overlay road network from OSM
    G = ox.graph_from_point((center_lat, center_lon), dist=half_sz, network_type='drive')
    G = ox.project_graph(G)
    edges = ox.graph_to_gdfs(G, nodes=False)

    # Translate road geometry to local coordinates
    proj_edges = pyproj.Proj(G.graph['crs'])
    cx, cy = proj_edges(center_lon, center_lat)
    edges['geometry'] = edges['geometry'].translate(xoff=-cx, yoff=-cy)

    # Plot road network overlay
    edges.plot(ax=ax, linewidth=0.5, edgecolor='black', alpha=0.5)

    # Finalize and save figure
    plt.title("Car Accident Kernel Map (Taipei, Local Cartesian Coordinates)")
    plt.xlabel("Easting [m]")
    plt.ylabel("Northing [m]")
    plt.axis("equal")
    plt.tight_layout()
    plt.savefig("roadProcessing/output/car_accident_heatmap.png", dpi=300, bbox_inches='tight')
    plt.show()

