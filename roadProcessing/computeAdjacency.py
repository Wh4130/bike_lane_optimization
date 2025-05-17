from utils import (
    get_demand_intersect,
    get_line_sample_points,
    latlon_to_xy
)
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
import numpy as np
import xarray as xr
from tqdm import tqdm
import argparse

# * arguments parser
def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--buffer", action="store_true", required=False,
        help="whether buffer the border of the POLYGON of each road while calculating the adjacency"
    )
    parser.add_argument(
        "--buffer_scale", type=float, required=False, default=0.00005,
        help="the scale of buffering"
    )
    args = parser.parse_args()
    return args

def main():
    args = parse_args()

    # * Load in data
    gdf_road = gpd.read_parquet("data/processed/road_data.parquet")
    gdf_road = gdf_road.reset_index(drop=True)
    ds_DemandGrid   = xr.open_dataset("demandModel/demandModel_metreGrid.nc")

    # * Initialize container
    results = []

    for i, row_i in tqdm(gdf_road.iterrows(), total=len(gdf_road)):

        geom_i     = row_i['geometry']
        road_idx_i = row_i['roadID']

        # * If buffering required, then select the index based on buffered geometry
        if args.buffer:
            geom_i = geom_i.buffer(args.buffer_scale)

        # Spatial filter using sindex
        candidate_idxs = list(gdf_road.sindex.intersection(geom_i.bounds))

        for j in candidate_idxs:

            if j <= i:
                continue  # avoid duplicates and self

            if j not in candidate_idxs:
                continue  


            geom_j     = gdf_road.loc[j, 'geometry']
            road_idx_j = gdf_road.loc[j, 'roadID']

            # * If buffering required, then buffer the geometry of road j as well
            if args.buffer:
                geom_j = geom_j.buffer(args.buffer_scale)

            if geom_i.intersects(geom_j):
                inter_geom = geom_i.intersection(geom_j)

                # Safety: some intersections may be empty or weird
                if not inter_geom.is_empty:
                    

                    # * If geom type is Point or LineString, use get_demand_intersect() in utils.py
                    if inter_geom.geom_type in ["Point", "LineString"]:
                        n = 0
                        demand = 0
                        total_demand = get_demand_intersect(ds_DemandGrid, inter_geom, inter_geom.geom_type)

                        n += total_demand['n']
                        demand += total_demand['total_demand']
                        demand /= n

                    # * If geom type is MultiPoint, use get_demand_intersect() to iterrate over all points and calculate the average demand
                    elif inter_geom.geom_type == "MultiPoint":
                        n      = 0
                        demand = 0
                        
                        for geom in inter_geom.geoms:
                            total_demand = get_demand_intersect(ds_DemandGrid, geom, "Point")
                            n += total_demand['n']
                            demand += total_demand['total_demand']

                        demand /= n

                    # * If geom type is MultiLineStrings, use get_demand_intersect() to iterrate over all linestrings and calculate the average demand
                    elif inter_geom.geom_type == "MultiLineString":
                        demand = 0
                        n      = 0
                        for geom in inter_geom.geoms:
                            total_demand = get_demand_intersect(ds_DemandGrid, geom, "LineString")
                            demand += total_demand["total_demand"]
                            n      += total_demand["n"]
                        demand /= n

                    # * If geom type is GeometryCollection, use get_demand_intersect() to iterrate over all item inside and calculate the average demand
                    elif inter_geom.geom_type == "GeometryCollection":
                        n      = 0
                        demand = 0
                        for geom in inter_geom.geoms:
                            if geom.geom_type in ["Point", "LineString"]:
                                total_demand = get_demand_intersect(ds_DemandGrid, geom, geom.geom_type)
                                n += total_demand["n"]
                                demand += total_demand['total_demand']
                        demand /= n

                    # * If geom type is Polygon, use the centroid to calculate the demand
                    elif inter_geom.geom_type == "Polygon":
                        geom = inter_geom.centroid
                        total_demand = get_demand_intersect(ds_DemandGrid, geom, geom.geom_type)
                        n = total_demand["n"]
                        demand = total_demand['total_demand']
                        demand /= n

                    # * Otherwise, pass None
                    else:
                        print(inter_geom.geom_type)
                        demand = None

                    # * Append it to results list
                    results.append({
                        "road_i": road_idx_i,
                        "road_j": road_idx_j,
                        "intersection_geom": inter_geom,
                        "intersection_demand": demand
                    })

    # * Transform it to GeoPandas
    df_adj = pd.DataFrame(results)
    gdf_adj = gpd.GeoDataFrame(df_adj, geometry = 'intersection_geom')

    # * Calculate the column for normalized demand
    gdf_adj['intersection_demand_norm'] = 3 + (gdf_adj['intersection_demand'] - gdf_adj['intersection_demand'].mean()) / gdf_adj['intersection_demand'].std()

    # * Save it to parquet
    gdf_adj['intersection_demand'] = gdf_adj['intersection_demand'].apply(
    lambda v: v.item() if hasattr(v, "item") else v
)
    
    if args.buffer:
        gdf_adj.to_parquet("./data/processed/adjacency_demand_buffered.parquet")
    else:
        gdf_adj.to_parquet("./data/processed/adjacency_demand.parquet")


if __name__ == "__main__":
    main()
