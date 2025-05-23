import geopandas as gpd
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'visualizations')))
from visualizeSolution import plot_bike_lane_solution

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'solver')))
from Main_wally import Model


def read_parquet_(filename):
    try:
        return gpd.read_parquet(filename)
    except:
        return gpd.read_parquet(filename)[1:]
    

if __name__ == "__main__":
    Roads = read_parquet_("../../data/processed/road_data_adj_count_usage.parquet")
    Roads.set_index('roadID', inplace=True)
    A = read_parquet_("../../data/processed/adjacency_demand_buffered.parquet")
    MRTs = read_parquet_('../../data/processed/mrt_stations.parquet')
    
    Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.75)]
    # filter to only consider adjacency of roads in the Roads set
    A = A[
        A["road_i"].isin(Roads.index) 
        & A["road_j"].isin(Roads.index)
    ]
    
    for id in range(101):
        mu = id / 100
        print(id, mu)
    
        M = Model(None)
        
        M.mu    = mu
        M.alpha = 0.2
        M.B_L   = 10000
        M.w     = 3
        M.tau   = 300
        
        M.setup(A, Roads, MRTs)
        result = M.optimize()
        M.visualizeSolution(path="raw/"+str(id)+"_mu_"+str(M.mu)+".png")
    