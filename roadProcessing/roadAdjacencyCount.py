# * ------------------------------------------------------------------------------
"""
Tasks:

1. for each road i, calculate the number of other roads adjacent to it.
2. visualization. (road with no adjacent roads are red, others blue.)
"""
# * ------------------------------------------------------------------------------
import geopandas as gpd
from tqdm import tqdm
import matplotlib.pyplot as plt
import argparse
import pandas as pd

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--calculate", action="store_true", required=False,
        help="whether to run the calculation of the number of adjacent roads for each road i"
    )

    parser.add_argument(
        "--buffer", action="store_true", required=False,
        help="whether use buffered adjacency matrix for calculation"
    )

    args = parser.parse_args()
    return args

# =============================== Task 1. ===============================
def run_calculation(args):
    
    if args.buffer:
        gdf_adj  = gpd.read_parquet("data/processed/adjacency_demand_buffered.parquet")
    else:
        gdf_adj  = gpd.read_parquet("data/processed/adjacency_demand.parquet")

    gdf_road = gpd.read_parquet("data/processed/road_data.parquet")
    gdf_road["adj_count"] = 0

    print("gdf_adj shape:", gdf_adj.shape)
    # print("Sample roads:", gdf_adj[['road_i', 'road_j']].head())


    """
    These two loops take around 20 minutes.
    """
    all_adj_roads = pd.concat([gdf_adj['road_i'], gdf_adj['road_j']])
    adj_counts = all_adj_roads.value_counts()
    gdf_road['adj_count'] = gdf_road['roadID'].map(adj_counts).fillna(0).astype(int)

    # * Save to road_data_adj_count.parquet
    print(gdf_road)
    print("Writing to:", "road_data_adj_count_buffered.parquet" if args.buffer else "road_data_adj_count.parquet")
    if args.buffer:
        gdf_road.to_parquet("data/processed/road_data_adj_count_buffered.parquet")
    else:
        gdf_road.to_parquet("data/processed/road_data_adj_count.parquet")


# =============================== Task 2. ===============================
if __name__ == "__main__":
    args = parse_args()

    if args.calculate:
        run_calculation(args)

    if args.buffer:
        gdf_road = gpd.read_parquet("data/processed/road_data_adj_count_buffered.parquet")
    else:
        gdf_road = gpd.read_parquet("data/processed/road_data_adj_count.parquet")


    fig, ax = plt.subplots(figsize=(12, 12))

    # Plot roads with intersection normally
    gdf_road[~(gdf_road['adj_count'] == 0)].plot(ax=ax, linewidth=1, color='blue', label='Intersecting Roads')

    # Plot roads with no intersection bold
    gdf_road[(gdf_road['adj_count'] == 0)].plot(ax=ax, linewidth=1, color='red', label='No Intersection (Bold)')

    if args.buffer:
        ax.set_title("Road Map: Red Roads Have No Intersections (Buffered)")
    else:
        ax.set_title("Road Map: Red Roads Have No Intersections")


    ax.grid(True, color='lightgray')

    for spine in ax.spines.values():
        spine.set_color('lightgray')

    ax.legend()
    ax.set_aspect('equal')
    
    if args.buffer:
        plt.savefig("roadProcessing/output/road_map_red_no_intersection_buffered.png", dpi=300, bbox_inches='tight')
    else:
        plt.savefig("roadProcessing/output/road_map_red_no_intersection.png", dpi=300, bbox_inches='tight')

    plt.show()

