import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import argparse
import matplotlib.pyplot as plt
import geopandas as gpd
import os
import json
from datetime import datetime

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
    def setup(self, Intersections, Roads, args):
        self.Roads = Roads
        self.mu    = args.mu
        self.alpha = args.alpha
        self.B_L   = args.B_length
        
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
            (Roads.loc[i, "length_norm"] ** (self.alpha)) * (Roads.loc[i, "roadDemand_m2_norm"] ** (1 - self.alpha)) * (self.x1[i] + Roads.loc[i, "danger_m2_norm"] * self.x2[i])
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
        self.model.addConstr(gp.quicksum(((1 * self.x1[i] + 3 * self.x2[i]) * Roads.loc[i, "length_norm"]) for i in self.roadIDs) <= self.B_L, name="totalCost")  # simple contraint for testing: only build 4 roads
        
        # linking of y to x              
        for i, j in Intersections[['road_i','road_j']].itertuples(index=False, name=None):
            # self.model.addConstr(self.y[i, j] >= self.x[i] + self.x[j] - 1, name="")
            self.model.addConstr(self.y[i, j] <= self.x1[i] + self.x2[i], name="")
            self.model.addConstr(self.y[i, j] <= self.x1[j] + self.x2[j], name="")
        
    
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

            
            print(len(x1_sol_idx))
            print(len(x2_sol_idx))
            
            print(np.sum(x1_sol), np.sum(y_sol))
            self.result = {"x1": x1_sol_idx,"x2": x2_sol_idx, "y": y_sol_idx, "obj_val": self.model.obj_val}
            
            
    def save_result(self, time_spent):
        # * making directory
        if self.args.exp_name != "default":
            name = self.args.exp_name
        else:
            name = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "_")
        os.makedirs(f"solver/output/{name}", exist_ok = True)

        assert self.result != {}, "please run optimization first so there would be result to save."

        # * saving solution of roads
        x1_df = pd.DataFrame({"roadID": self.result["x1"], "roadType": 1})
        x2_df = pd.DataFrame({"roadID": self.result["x2"], "roadType": 2})

        x1_df_merged = pd.merge(x1_df, Roads, how = 'left', on = 'roadID')
        x2_df_merged = pd.merge(x2_df, Roads, how = 'left', on = 'roadID')

        result_gdf = pd.concat([x1_df_merged, x2_df_merged])
        result_gdf = gpd.GeoDataFrame(result_gdf, geometry = "geometry")
        result_gdf.to_parquet(f"solver/output/{name}/roads_sol.parquet")

        # * saving hyperparameter, objective value, and time cost
        meta = {
            "hyperparams": {
                "mu": self.mu,
                "alpha": self.alpha,
                "B_L": self.B_L,
                "scale": self.args.scale
            },
            "obj_val": self.result['obj_val'],
            "cal_time_sec": time_spent
        }

        with open(f"solver/output/{name}/meta_data.json", "w") as file:
            json.dump(meta, file, ensure_ascii = False, indent = True)


    def print_(self, message):
        if self.verbose:
            print(message)
            
    def visualizeSolution(self):
        if self.model.status == GRB.OPTIMAL:    
            pass
            # call function from Nick
    


if __name__ == "__main__":
    args = parse_args()

    # Roads = pd.read_parquet("../data/processed/road_data.parquet").iloc[20:30]
    Roads = gpd.read_parquet(args.road_data)
    Roads.set_index('roadID', inplace=True)
    A = gpd.read_parquet(args.adj_mat)
    print(len(A))

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
    M.setup(A, Roads, args)
    result = M.optimize()
    M.save_result(time_spent = result[1])

    
    

