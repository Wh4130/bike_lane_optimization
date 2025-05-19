# * Import necessary modules
import geopandas as gpd
import re
import matplotlib as mpl
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Point
import json
import pandas as pd
from tqdm import tqdm
from utils import latlon_to_xy
import xarray as xr
import numpy as np

from utils import get_line_sample_points

if __name__ == "__main__":

    # * Load road data
    shapefile_path = "./data/8mroadup/Road.shp"  # Update with your path
    gdf = gpd.read_file(shapefile_path, encoding='utf8')
    gdf = gdf.drop(gdf[gdf['RoadWidth'] == 0].index.tolist())
    gdf = gdf.reset_index(drop = True)
    gdf = gdf.to_crs("EPSG:4326")

    # * Load demand grid data
    ds_DemandGrid   = xr.open_dataset("demandModel/demandModel_metreGrid.nc")
    ds_DangerGrid   = xr.open_dataset("roadProcessing/output/car_accident_grid.nc")


    # * Process each road
    df_Road = pd.DataFrame(columns = ["roadID", "roadID_foreign", "roadName", "geometry", "centroid", "roadDemand", "roadDemand_m2", "width", "length", "danger", "danger_m2"])

    


    for idx, row in tqdm(gdf.iterrows()):
        # * Demand Calculation Method 1: calculate the demand of road by its centroid
        roadCenter  = row["geometry"].centroid
        lon, lat    = roadCenter.x, roadCenter.y
        x, y        = latlon_to_xy(lat, lon)
        roadDemand  = ds_DemandGrid['demand'].sel(x_m = x, y_m = y, method='nearest').values

        

        # * Danger Calculation Method 1: calculate the danger of road by its centroid
        roadDanger  = ds_DangerGrid["accident"].sel(x_m = x, y_m = y, method = 'nearest').values

        # * Danger/Demand Calculation Method 2: calculate several points over the road segment and average it
        road_points = get_line_sample_points(row['geometry'].exterior)
        demand = 0
        danger = []
        for point in road_points:
            x, y   = latlon_to_xy(point.y, point.x)
            demand += ds_DemandGrid['demand'].sel(x_m = x, y_m = y, method='nearest').values
            danger.append(ds_DangerGrid['accident'].sel(x_m = x, y_m = y, method='nearest').values)
        demand /= len(road_points)
        danger =  max(danger)

        df_Road.loc[idx, :] = [
            idx + 1,
            row["Road_ID"],
            row["路名"],
            row["geometry"],
            roadCenter,
            roadDemand,
            demand,
            row["RoadWidth"],
            row["RoadLenght"],
            roadDanger,
            danger
        ]

    # * Normalization
    df_Road['roadDemand_m2_norm'] = 3 + (df_Road['roadDemand_m2'] - df_Road['roadDemand_m2'].mean()) / df_Road['roadDemand_m2'].std()
    df_Road['danger_m2_norm'] = 3 + (df_Road['danger_m2'] - df_Road['danger_m2'].mean()) / df_Road['danger_m2'].std()
    df_Road['length_norm'] = 3 + (df_Road['length'] - df_Road['length'].mean()) / df_Road['length'].std()

    df_Road.dropna(subset=["roadID_foreign"])
    gdf_Road = gpd.GeoDataFrame(df_Road, geometry = 'geometry', crs = 'EPSG:4326')
    gdf_Road['centroid'] = gdf_Road['centroid'].apply(lambda p: p.wkt)
    gdf_Road['roadDemand'] = gdf_Road['roadDemand'].apply(lambda x: x.item() if hasattr(x, "item") else x)
    gdf_Road['danger'] = gdf_Road['danger'].apply(lambda x: x.item() if hasattr(x, "item") else x)
    gdf_Road['danger_m2'] = gdf_Road['danger_m2'].apply(lambda x: x.item() if hasattr(x, "item") else x)


    gdf_Road.to_parquet("./data/processed/road_data.parquet")