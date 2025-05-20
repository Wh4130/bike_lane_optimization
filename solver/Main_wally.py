import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import argparse
import matplotlib.pyplot as plt
from tqdm import tqdm
import geopandas as gpd
import os
import json
from datetime import datetime
from utils import *

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'visualizations')))
from visualizeSolution import plot_bike_lane_solution


"""
What's different from Main.py?
1. Newest objective function and constraints on overleaf
2. Added arguments parser
3. Defined the structure of output folder already (one parquet file with road solution details, and another json file for meta data and objective value)
4. Customizable parameters

What's missing still?
1. The second constraint (minimum coverage)
"""

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--road_data", type = str,
        default = "../data/processed/road_data_adj_count_usage.parquet",
        help = "full data path to the road data"
    )
    parser.add_argument(
        "--adj_mat", type = str,
        default = "../data/processed/adjacency_demand_buffered.parquet",
        help = "full data path to the adjacency matrix data"
    )
    parser.add_argument(
        "--mrt", type = str,
        default = "../data/processed/mrt_stations.parquet",
        help = "full data path to the mrt station data"
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
        default = 100,
        help = "parameter tau (threshold of MRT station coverage radius)"
    )
    parser.add_argument(
        "--mu", type = float,
        default = 0.2,
        help = "parameter mu (importance of total road utility over adjacency utility)"
    )
    parser.add_argument(
        "--B_length", type = float,
        default = 1000,
        help = "parameter B^L (budget constraint RHS by meter)"
    )
    parser.add_argument(
        "--w", type = float,
        default = 2.5,
        help = "parameter w (relative cost of type 2 over type 1)"
    )
    parser.add_argument(
        "--log", action = "store_true",
        help = "show log to console"
    )
    parser.add_argument(
        "--exp_name", type = str, 
        default = "default",
        help = "the name of the experiment"
    )
    args = parser.parse_args()
    return args

def decorator_timer(some_function):
    from time import time

    def wrapper(*args, **kwargs):
        t1 = time()
        result = some_function(*args, **kwargs)
        end = time()-t1
        return result, end
    return wrapper


class Model:
    def __init__(self, args):
        self.model = gp.Model('BikelaneOptimization')
        self.model.setParam('OutputFlag', 0)
        self.args = args
        if not self.args.log:
            self.model.Params.LogToConsole = 0
        self.verbose = True
        self.result = {}
        
    @decorator_timer
    def setup(self, Intersections, Roads, MRTs, args):
        self.Roads = Roads
        self.mu    = args.mu
        self.alpha = args.alpha
        self.B_L   = args.B_length
        self.w     = args.w
        self.tau   = args.tau
        
        # set of all roads and intersections
        self.roadIDs = Roads.index 
        self.Intersections = Intersections
        
        self.roadIDs              = self.roadIDs.tolist()
        # self.intersectingRoadIDs  = self.intersectingRoadIDs.tolist()
        
        
        # ========= Decision variables ========================================
        self.print_("Setting up variables...")
        self.x1 = self.model.addVars(self.roadIDs, name="x1", vtype=GRB.BINARY)
        self.x2 = self.model.addVars(self.roadIDs, name="x2", vtype=GRB.BINARY)
        
        self.y = self.model.addVars(list(Intersections[['road_i','road_j']].itertuples(index=False, name=None)), name="y", vtype=GRB.BINARY)
            
        
        # ========= Objective function ========================================
        self.print_("Setting up objective function...")
        
        roadUtility = gp.quicksum(
            (Roads.loc[i, "length_norm"] ** (self.alpha)) * (Roads.loc[i, "roadDemand_m2_norm"] ** (1 - self.alpha)) * (self.x1[i] + 3 * self.x2[i])
            for i in self.roadIDs
        )
        
        intersectionUtility = gp.quicksum(
            demandNorm * self.y[r_i, r_j]
            for r_i, r_j, demandNorm in Intersections[
                ['road_i','road_j','intersection_demand_norm']
            ].itertuples(index=False, name=None)
        )
        
        self.model.setObjective(self.mu * roadUtility + (1-self.mu) * intersectionUtility, GRB.MAXIMIZE)
        
        
        # ========= Constraints ===============================================
        self.print_("Setting up constraints...")
        
        # Construction cost constraint
        self.model.addConstr(gp.quicksum(((1 * self.x1[i] + self.w * self.x2[i]) * Roads.loc[i, "length"]) for i in self.roadIDs) <= self.B_L, name="totalCost")  # simple contraint for testing: only build 4 roads
        
        print(Intersections[['road_i','road_j']].itertuples(index=False, name=None))
        
        # linking of y to x              
        for i, j in Intersections[['road_i','road_j']].itertuples(index=False, name=None):
            # self.model.addConstr(self.y[i, j] >= self.x[i] + self.x[j] - 1, name="")
            self.model.addConstr(self.y[i, j] <= self.x1[i] + self.x2[i], name="")
            self.model.addConstr(self.y[i, j] <= self.x1[j] + self.x2[j], name="")

        # at most one level to be built
        for i in self.roadIDs:
            self.model.addConstr(self.x1[i] + self.x2[i] <= 1, name="")
            
        # experimental constraints to control "connectedness"
        # gamma = 1.1
        # control upper limit of sum(y) / sum(x):
        #self.model.addConstr(gp.quicksum(self.y[i, j] for i, j in Intersections[['road_i','road_j']].itertuples(index=False, name=None)) <= gamma * gp.quicksum((self.x1[i] + self.x2[i]) for i in self.roadIDs))
        
        # enforce sum(y) + 1 = sum(x):
        #self.model.addConstr(gp.quicksum(self.y[i, j] for i, j in Intersections[['road_i','road_j']].itertuples(index=False, name=None)) + 1 == gp.quicksum((self.x1[i] + self.x2[i]) for i in self.roadIDs))
        
        # # at most two reads connected to each intersection:
        # for i in Intersections['road_i'].unique():
        #     # find all road_j’s paired with this i
        #     self.model.addConstr(gp.quicksum(self.y[i, j] for j in Intersections.loc[Intersections['road_i'] == i, 'road_j']) <= 2)


        # area coverage constraint
        Roads_trs = proj_to_xy(Roads, "road")
        MRT_trs   = proj_to_xy(MRTs, "other")
        qs = []
        # print("Adding area coverage constraint...")
        # for _, q in tqdm(MRT_trs.iterrows(), total = len(MRT_trs)):
        #     potential_xi_for_q = []
        #     for roadID in self.roadIDs:
        #         dist = euclidean_n2((q['x'], q['y']), (Roads_trs.loc[roadID, "x"], Roads_trs.loc[roadID, "y"]))
        #         if  dist < self.tau ** 2:
        #             potential_xi_for_q.append(self.x1[roadID])
        #             potential_xi_for_q.append(self.x2[roadID])
        #     qs.append(potential_xi_for_q)
        # self.model.addConstr(sum(sum(potential_xi_for_q) for potential_xi_for_q in qs) >= 0.5 * len(qs))

        # print(MRTs)

        
    
    @decorator_timer  
    def optimize(self):
        # Optimize the model
        print("optimizing model...")
        self.model.optimize()
        print("optimizing complete")

        # Print the solution
        if self.model.status == GRB.OPTIMAL:
            self.print_("Optimization successfull")

            x1_sol = np.array([self.x1[i].X for i in self.roadIDs])
            x2_sol = np.array([self.x2[i].X for i in self.roadIDs])

            y_sol = np.array([
                [
                    self.y[j, i].X if (j, i) in self.y else 0
                    for i in self.roadIDs
                ]
                for j in self.roadIDs
            ])

            x1_sol_idx = []
            x2_sol_idx = []
            y_sol_idx = []

            for i in self.roadIDs:
                if self.x1[i].X > 0:
                    x1_sol_idx.append(i)
                if self.x2[i].X > 0:
                    x2_sol_idx.append(i)
                for j in self.roadIDs:
                    if (i, j) in self.y and self.y[i, j].X > 0:
                        y_sol_idx.append((i, j))

            print("======================= Optimization Result =======================")
            params = ["mu", "alpha", "B_L", "w", "tau", "scale"]
            values = [self.mu, self.alpha, self.B_L, self.w, self.tau, self.args.scale]
            print(f"---------------------- parameters --------------------------------")
            print("    ".join("{:>6}".format(val) for val in params))
            print("    ".join("{:>6}".format(val) for val in values))
            print(f"number of type 1 bike lanes (x_i1 = 1): {len(x1_sol_idx)}")
            print(f"number of type 2 bike lanes (x_i2 = 1): {len(x2_sol_idx)}")
            print(f"number of served intersections (y_ij = 1): {np.sum(y_sol)}")
            print(f"number of served intersections per road [sum(y_ij) / sum(x_i)]: {np.sum(y_sol) / (np.sum(x1_sol)+np.sum(x2_sol)):6f}")
            print(f"---------------------- Objective Value ---------------------------")
            print(f"Obj val: {self.model.obj_val}")
            self.result = {"x1": x1_sol_idx,"x2": x2_sol_idx, "y": y_sol_idx, "obj_val": self.model.obj_val}
            
            
    def save_result(self, time_spent):
        # * making directory
        if self.args.exp_name != "default":
            os.makedirs(f"solver/output/{self.args.exp_name}", exist_ok = True)
        else:
            os.makedirs(f'solver/output/{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', exist_ok = True)

        assert self.result != {}, "please run optimization first so there would be result to save."

        # * saving solution of roads
        x1_df = pd.DataFrame({"roadID": self.result["x1"], "roadType": 1})
        x2_df = pd.DataFrame({"roadID": self.result["x2"], "roadType": 2})

        x1_df_merged = pd.merge(x1_df, Roads, how = 'left', on = 'roadID')
        x2_df_merged = pd.merge(x2_df, Roads, how = 'left', on = 'roadID')

        result_gdf = pd.concat([x1_df_merged, x2_df_merged])
        result_gdf = gpd.GeoDataFrame(result_gdf, geometry = "geometry")
        result_gdf.to_parquet(f"solver/output/{self.args.exp_name}/roads_sol.parquet")
        

        # * saving hyperparameter, objective value, and time cost
        meta = {
            "hyperparams": {
                "mu": self.mu,
                "alpha": self.alpha,
                "B_L": self.B_L,
                "w": self.w,
                "scale": self.args.scale
            },
            "obj_val": self.result['obj_val'],
            "cal_time_sec": time_spent,
            "result_description": {
                "num_x1": len(x1_df),
                "num_x2": len(x2_df)
            }
        }

        with open(f"solver/output/{self.args.exp_name}/meta_data.json", "w") as file:
            json.dump(meta, file, ensure_ascii = False, indent = True)

        print(f"solutions and metadata saved to output/{name} folder")

    def print_(self, message):
        if self.verbose:
            print(message)
            
    def visualizeSolution(self):
        if self.model.status == GRB.OPTIMAL:    
            # call function from Nick
            assert self.result != {}, "please run optimization first so there would be result to save."

            # * saving solution of roads
            x1_df = pd.DataFrame({"roadID": self.result["x1"], "roadType": 1})
            x2_df = pd.DataFrame({"roadID": self.result["x2"], "roadType": 2})

            x1_df_merged = pd.merge(x1_df, self.Roads, how = 'left', on = 'roadID')
            x2_df_merged = pd.merge(x2_df, self.Roads, how = 'left', on = 'roadID')

            result_gdf = pd.concat([x1_df_merged, x2_df_merged])
            
            roads = gpd.read_parquet("../data/processed/road_data_adj_count_usage.parquet")
            
            fig, ax = plot_bike_lane_solution(result_gdf, roads)
            plt.show()
    


if __name__ == "__main__":
    args = parse_args()

    # Roads = pd.read_parquet("../data/processed/road_data.parquet").iloc[20:30]
    try:
        Roads = gpd.read_parquet(args.road_data)
        A = gpd.read_parquet(args.adj_mat)
        MRTs = gpd.read_parquet(args.mrt)
    except:
        # if data cannot be loaded from tha above path, try without the first . in the path string
        Roads = gpd.read_parquet(args.road_data[1:])
        A = gpd.read_parquet(args.adj_mat[1:])
        MRTs = gpd.read_parquet(args.mrt[1:])
    
    Roads.set_index('roadID', inplace=True)

    # * filter the data by argument option "scale"
    if args.scale == "small":
        Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.75)]
    elif args.scale == "medium":
        Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.5)]
    elif args.scale == "large":
        Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.25)]

    #print(A.head())
    
    # filter to only consider adjacency of roads in the Roads set
    A = A[
        A["road_i"].isin(Roads.index) 
        & A["road_j"].isin(Roads.index)
    ]
    
    M = Model(args = args)
    
    M.setup(A, Roads, MRTs, args)
    
    result = M.optimize()
    
    M.visualizeSolution()
    
    
    # M.save_result(time_spent = result[1])

