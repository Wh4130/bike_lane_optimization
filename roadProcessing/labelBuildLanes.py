import geopandas as gpd
import re
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import os
import pandas as pd
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tolerance", type = float, default = 0.0001
    )
    parser.add_argument(
        "--thres", type = float, default = 0.8
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    tolerance = args.tolerance
    thres = args.thres

    built_lanes_gdf = pd.read_csv("./data/processed/built_bike_lane.csv").rename(columns = {"路徑（Y）": "y_coords", '路徑（X）': 'x_coords'})
    road_adj_gdf_buffered = gpd.read_parquet("./data/processed/road_data_adj_count_buffered.parquet")

    # * Preprocess the built bike lane data (create geometry column and transform crs to 4326, latlon)
    built_lanes_gdf['x_coords'] = built_lanes_gdf['x_coords'].apply(lambda x: re.split(",|\#", x))
    built_lanes_gdf['y_coords'] = built_lanes_gdf['y_coords'].apply(lambda y: re.split(",|\#", y))
    built_lanes_gdf['geometry'] = built_lanes_gdf.apply(lambda row: LineString(list(zip(row['x_coords'], row['y_coords']))), axis=1)
    built_lanes_gdf = gpd.GeoDataFrame(built_lanes_gdf, geometry = 'geometry').set_crs("EPSG:3826").to_crs("EPSG:4326")

    road_adj_gdf_usage = road_adj_gdf_buffered.copy()
    road_adj_gdf_usage["has_bike_lane"] = 0

    

    # * create bike lane's spatial index
    built_lanes_gdf['geometry'] = built_lanes_gdf['geometry'].buffer(tolerance)
    bike_sindex = built_lanes_gdf.sindex

    for idx, road in road_adj_gdf_usage.iterrows():
        # * buffer road geometry
        buffered_road = road.geometry.buffer(tolerance)

        # * find candidates of overlapping bikelanes
        candidate_idx = list(bike_sindex.intersection(buffered_road.bounds))
        candidates = built_lanes_gdf.iloc[candidate_idx]

        total_overlap = 0.0
        for bike_geom in candidates.geometry:
            if buffered_road.intersects(bike_geom):
                inter = buffered_road.intersection(bike_geom)
                total_overlap += inter.length

        # * calculate the proportion of overlap
        if total_overlap / road.geometry.length > thres:
            road_adj_gdf_usage.at[idx, 'has_bike_lane'] = 1

    road_adj_gdf_usage.to_parquet("./data/processed/road_data_adj_count_usage.parquet")