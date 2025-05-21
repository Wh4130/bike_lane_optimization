import geopandas as gpd
from pathlib import Path 
import matplotlib.pyplot as plt

from matplotlib.patches import Patch


def plot_bike_lane_solution(bike_lanes, roads):
    """"
    Plot the biking lanes depending on type, based on the solution of the IP.
    """
    bike_lanes["roadID"] = bike_lanes["roadID"].astype("int64")
    
    lanes1 = bike_lanes["roadID"][bike_lanes["roadType"]== 1].tolist()
    lanes2 = bike_lanes["roadID"][bike_lanes["roadType"]== 2].tolist()
    

    def assign_color(road_id):
        if road_id in lanes1:
            return "blue"
        elif road_id in lanes2:
            return "green"
        else:
            return "gray"  # Default color for unmatched roads
        
    roads["color"] = roads["roadID"].apply(assign_color)

    fig, ax = plt.subplots(figsize=(10, 10))

    for color in ["blue", "green", "gray"]:
        subset = roads[roads["color"] == color]
        # Check if we attempt to plot an empty set
        if not subset.empty:
            subset.plot(ax=ax, color=color)

    legend_elements = [
        Patch(facecolor="blue", label="Bike Lane (1)"),
        Patch(facecolor="green", label="Bike Lane (2)"),
        Patch(facecolor="gray", label="Regular Street")
    ]

    ax.legend(handles=legend_elements, title="Road Categories")
    ax.set_title("Roads by Category")
    
    # limit to downtown taipei
    ax.set_xlim((121.503, 121.574))
    ax.set_ylim((25.013, 25.079))
    
    return fig, ax


if __name__ == "__main__":
    project_root = Path().resolve().parent

    # Set this to the path of the experiment you want to evaluate
    experiment_dir = "./solver/output/2025-05-19_11:01:00"
    bike_lanes = gpd.read_parquet(project_root / experiment_dir / "roads_sol.parquet")
    bike_lanes["roadID"] = bike_lanes["roadID"].astype("int64")

    roads = gpd.read_parquet(project_root / "data" / "processed" / "road_data_adj_count_usage.parquet")
    mrt_stations = gpd.read_parquet(project_root / "data" / "processed" / "mrt_stations.parquet")
    youbike_stations = gpd.read_parquet(project_root / "data" / "processed" / "youbike_station_location.parquet")
    
    fig, ax = plot_bike_lane_solution(bike_lanes, roads)
    plt.show()