import pandas as pd
import shapely
import geopandas as gpd
import pyproj
from shapely.geometry import Point
import numpy as np
# ==========================================================================
# * Preprocess the MRT geographical data

def project_row(row):
    if isinstance(row.geometry, Point):
        x, y = row.geometry.x, row.geometry.y
        return pd.Series(proj(x, y))
    else:
        return pd.Series([np.nan, np.nan])
    

if __name__ == "__main__":
    data = pd.read_csv("./data/facilities/mrt_station.csv")
    data['geometry'] = data['wkt_geom'].apply(lambda s: shapely.wkt.loads(s))  # if WKT
    gdf  = gpd.GeoDataFrame(data, geometry = 'geometry', crs='EPSG:3826')
    gdf = gdf.to_crs("EPSG:4326")


    proj = pyproj.Proj(proj="aeqd", lat_0=25.0375, lon_0=121.56444, units="m")
    project = lambda lon, lat: proj(lon, lat)

    gdf[['x_m', 'y_m']] = gdf.apply(project_row, axis=1)

    gdf = gdf.drop(gdf[~gdf['MARKNAME1'].str.contains("臺北")].index.tolist())
    gdf.to_parquet("data/processed/mrt_stations.parquet")

    print("mrt stations data processed and saved in data/processed folder.")