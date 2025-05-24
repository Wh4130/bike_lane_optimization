import argparse
import os, sys
from datetime import datetime
from tqdm import tqdm
import geopandas as gpd
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sol_heuristic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'solver')))


from heuristic_1 import Naive
from heuristic_2 import Heuristic
from Main_wally import Solver
from utils import *


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log", action = "store_true",
        help = "show log to console"
    )
    parser.add_argument(
        "--exp_mode", action = "store_true",
        help = "turn on the experiment mode"
    )
    parser.add_argument(
        "--road_data", type = str,
        default = "./data/processed/road_data_adj_count_usage.parquet",
        help = "full data path to the road data"
    )
    parser.add_argument(
        "--adj_mat", type = str,
        default = "./data/processed/adjacency_demand_buffered.parquet",
        help = "full data path to the adjacency matrix data"
    )
    parser.add_argument(
        "--scale", type = str, choices = ["small", "medium", "large"],
        default = "medium",
        help = "scale of the model (the number of decision variables)"
    )
    parser.add_argument(
        "--alpha", type = float,
        default = 0.2,
        help = "parameter alpha (importance of road length over road cycling demand)"
    )
    parser.add_argument(
        "--tau", type = float,
        default = 300,
        help = "parameter tau (threshold of MRT station coverage radius)"
    )
    parser.add_argument(
        "--mu", type = float,
        default = 0.2,
        help = "parameter mu (importance of total road utility over adjacency utility)"
    )
    parser.add_argument(
        "--B_length", type = float,
        default = 50000,
        help = "parameter B^L (budget constraint RHS by meter)"
    )
    parser.add_argument(
        "--w", type = float,
        default = 3,
        help = "parameter w (relative cost of type 2 over type 1)"
    )
    parser.add_argument(
        "--exp_name", type = str, 
        default = "default",
        help = "the name of the experiment"
    )
    parser.add_argument(
        "--remove_existing", action = "store_true",
        help = "whether to remove existing bike lanes"
    )
    args = parser.parse_args()
    return args



if __name__ == "__main__":
    args = parse_args()

    Roads = gpd.read_parquet(args.road_data)
    Roads.set_index('roadID', inplace=True)
    A = gpd.read_parquet(args.adj_mat)

    expResults = pd.DataFrame(
        columns = ["scenarioID", 
                   "naiveObjVal", "naiveTime", "naiveX1num", "naiveX2num", "naiveYnum", 
                   "heuObjVal", "heuTime", "heuX1num", "heuX2num", "heuYnum", 
                   "solverObjVal", "solverTime", "solverX1num", "solverX2num", "solverYnum", 
                   "optGapNaive", "optGapHeu"]
    )
    gammaApprox = getGammaApprox(Roads, A)

    for _ in tqdm(range(30)):
        ExpRoads, ExpA = expDataGenerator(Roads, A, gammaApprox)
        ExpRoads.set_index("roadID", inplace = True)
        ExpRoads = ExpRoads[ExpRoads['width'] >= ExpRoads["width"].quantile(0.5)]

        # * filter the data by argument option "remove_existing"
        if args.remove_existing:
            ExpRoads = ExpRoads[ExpRoads["has_bike_lane"] == 0]

        # * filter to only consider adjacency of roads in the Roads set
        ExpA = ExpA[
            ExpA["road_i"].isin(ExpRoads.index) 
            & ExpA["road_j"].isin(ExpRoads.index)
        ]
        
        # * Naive Algorithm
        M_naive = Naive(args = args)
        M_naive.setup(ExpA, ExpRoads)
        M_naive_result = M_naive.optimize()

        # * Heuristic
        M_heu = Heuristic(args = args)
        M_heu.setup(ExpA, ExpRoads)
        M_heu_result = M_heu.optimize()

        # * Solver
        M_solver = Solver(args = args)
        M_solver.setup(ExpA, ExpRoads)
        M_solver_result = M_solver.optimize()

        # Calculate optimality gaps
        naive_gap = (M_solver.result["obj_val"] - M_naive.result["obj_val"]) / M_solver.result["obj_val"]
        heu_gap = (M_solver.result["obj_val"] - M_heu.result["obj_val"]) / M_solver.result["obj_val"]

        expResults.loc[len(expResults), :] = [
            args.exp_name.replace("scenario_", ""),
            M_naive.result["obj_val"],
            M_naive_result[1],
            len(M_naive.result["x1"]),
            len(M_naive.result["x2"]),
            len(M_naive.result["y"]),
            M_heu.result["obj_val"],
            M_heu_result[1],
            len(M_heu.result["x1"]),
            len(M_heu.result["x2"]),
            len(M_heu.result["y"]),
            M_solver.result["obj_val"],
            M_solver_result[1],
            len(M_solver.result["x1"]),
            len(M_solver.result["x2"]),
            len(M_solver.result["y"]),
            naive_gap,
            heu_gap
        ]   

    if args.exp_name != "default":
        name = args.exp_name
    else:
        name = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "_")
    expResults.to_excel(f"./Experiments/outputs/{name}.xlsx")