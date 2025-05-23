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
        "--log", action = "store_true",
        help = "show log to console"
    )
    parser.add_argument(
        "--remove_existing", action = "store_true",
        help = "whether to remove existing bike lanes"
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


def read_parquet_(filename):
    try:
        return gpd.read_parquet(filename)
    except:
        return gpd.read_parquet(filename)[1:]


class Model:
    def __init__(self, args):
        self.model = gp.Model('BikelaneOptimization')
        self.model.setParam('OutputFlag', 0)
        self.args = args
        
        # read parameters from args
        try:
            
            if not self.args.log:
                self.model.Params.LogToConsole = 0
            
            self.mu    = args.mu
            self.alpha = args.alpha
            self.B_L   = args.B_length
            self.w     = args.w
            self.tau   = args.tau
            
        except:
            # parameters need to be set manually elsewhere in this case!!
            self.model.Params.LogToConsole = 0
        
        self.verbose = True
        self.result = {}
        
    @decorator_timer
    def setup(self, Intersections, Roads, MRTs):
        self.Roads = Roads
        
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

        self.roadUtility = self.mu * roadUtility
        self.intersectionUtility = (1 - self.mu) * intersectionUtility
        
        
        # ========= Constraints ===============================================
        self.print_("Setting up constraints...")
        
        # Construction cost constraint
        self.model.addConstr(gp.quicksum(((1 * self.x1[i] + self.w * self.x2[i]) * Roads.loc[i, "length"]) for i in self.roadIDs) <= self.B_L, name="totalCost")  # simple contraint for testing: only build 4 roads
        
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
        
        # at most two reads connected to each intersection:
        for i in tqdm(Intersections['road_i'].unique()):
            # find all road_j’s paired with this i
            self.model.addConstr(gp.quicksum(self.y[i, j] for j in Intersections.loc[Intersections['road_i'] == i, 'road_j']) <= 1)


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
            try:
                values = [self.mu, self.alpha, self.B_L, self.w, self.tau, self.args.scale]
            except:
                values = [self.mu, self.alpha, self.B_L, self.w, self.tau, "custom"]
            print(f"---------------------- parameters --------------------------------")
            print("    ".join("{:>6}".format(val) for val in params))
            print("    ".join("{:>6}".format(val) for val in values))
            print(f"number of type 1 bike lanes (x_i1 = 1): {len(x1_sol_idx)}")
            print(f"number of type 2 bike lanes (x_i2 = 1): {len(x2_sol_idx)}")
            print(f"number of served intersections (y_ij = 1): {np.sum(y_sol)}")
            print(f"number of served intersections per road [sum(y_ij) / sum(x_i)]: {np.sum(y_sol) / (np.sum(x1_sol)+np.sum(x2_sol)):6f}")
            print(f"---------------------- Objective Value ---------------------------")
            print(f"Obj val:         {'{:>15}'.format(self.model.obj_val)}")
            print(f"Road Utility:    {'{:>15}'.format(self.roadUtility.getValue())}")
            print(f"Intersection Utility:    {'{:>15}'.format(self.intersectionUtility.getValue())}")

            


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
        self.sol_gdf = result_gdf


        # * saving hyperparameter, objective value, and time cost
        meta = {
            "hyperparams": {
                "mu": self.mu,
                "alpha": self.alpha,
                "B_L": self.B_L,
                "w": self.w,
                "scale": self.args.scale
            },
            "obj_val": {
                "total_utility": self.result['obj_val'],
                "road_utility": self.roadUtility.getValue(),
                "int_utility": self.intersectionUtility.getValue(),
                "road_util_prop": self.roadUtility.getValue() / self.result["obj_val"],
                "int_util_prop": self.intersectionUtility.getValue() / self.result["obj_val"]
            },
            "cal_time_sec": time_spent,
            "result_description": {
                "num_x1": len(x1_df),
                "num_x2": len(x2_df),
                "num_y" : len(self.result["y"])
            },
            "policy_similarity": result_gdf[result_gdf["has_bike_lane"] == 1]['length'].sum() / result_gdf['length'].sum() if not self.args.remove_existing else None
        }

        with open(f"solver/output/{self.args.exp_name}/meta_data.json", "w") as file:
            json.dump(meta, file, ensure_ascii = False, indent = True)

        print(f"solutions and metadata saved to output/{name} folder")

    def print_(self, message):
        if self.verbose:
            print(message)
            
    def visualizeSolution(self):
        if self.model.status == GRB.OPTIMAL:    
            try:
                Roads = read_parquet_(self.args.road_data)
                plot_map(
                    self.args.exp_name,
                    Roads, self.sol_gdf,
                    self.mu, self.alpha, self.B_L, self.w, self.tau, self.args.scale
                )
            except:
                Roads = read_parquet_("../../data/processed/road_data_adj_count_usage.parquet")
                # * saving solution of roads
                x1_df = pd.DataFrame({"roadID": self.result["x1"], "roadType": 1})
                x2_df = pd.DataFrame({"roadID": self.result["x2"], "roadType": 2})

                x1_df_merged = pd.merge(x1_df, Roads, how = 'left', on = 'roadID')
                x2_df_merged = pd.merge(x2_df, Roads, how = 'left', on = 'roadID')

                result_gdf = pd.concat([x1_df_merged, x2_df_merged])
                result_gdf = gpd.GeoDataFrame(result_gdf, geometry = "geometry")

                self.sol_gdf = result_gdf
                
                plot_map(
                    "custom",
                    Roads, self.sol_gdf,
                    self.mu, self.alpha, self.B_L, self.w, self.tau, "custom"
                )
            

            # # call function from Nick
            # assert self.result != {}, "please run optimization first so there would be result to save."

            # # * saving solution of roads
            # x1_df = pd.DataFrame({"roadID": self.result["x1"], "roadType": 1})
            # x2_df = pd.DataFrame({"roadID": self.result["x2"], "roadType": 2})

            # x1_df_merged = pd.merge(x1_df, self.Roads, how = 'left', on = 'roadID')
            # x2_df_merged = pd.merge(x2_df, self.Roads, how = 'left', on = 'roadID')

            # result_gdf = pd.concat([x1_df_merged, x2_df_merged])
            
            # roads = gpd.read_parquet("../data/processed/road_data_adj_count_usage.parquet")
            
            # fig, ax = plot_bike_lane_solution(result_gdf, roads)
            # plt.show()
            
            print("Visualization done!")
            

    


if __name__ == "__main__":
    args = parse_args()
    print(args)

    # Roads = pd.read_parquet("../data/processed/road_data.parquet").iloc[20:30]
    Roads = read_parquet_(args.road_data)
    Roads.set_index('roadID', inplace=True)
    A = read_parquet_(args.adj_mat)
    MRTs = read_parquet_('../data/processed/mrt_stations.parquet')

    if not args.exp_name:
        # * filter the data by argument option "scale"
        if args.scale == "small":
            Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.75)]
        elif args.scale == "medium":
            Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.5)]
        elif args.scale == "large":
            Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.25)]

        # * filter the data by argument option "remove_existing"
        if args.remove_existing:
            Roads = Roads[Roads["has_bike_lane"] == 0]

        #print(A.head())
        
        # filter to only consider adjacency of roads in the Roads set
        A = A[
            A["road_i"].isin(Roads.index) 
            & A["road_j"].isin(Roads.index)
        ]
        
        M = Model(args = args)
        M.setup(A, Roads, MRTs)
        result = M.optimize()
        M.save_result(time_spent = result[1])
        M.visualizeSolution()

    else:
        # TODO Initialize dataframe for storing the results (30 times)
        for _ in range(30):
            pass
            # TODO Link the data generation function.
            """
            Generate the data with normal size (don't scale it)
            and then scale it to 'medium'!
            
            - A (gdf):
                1. intersetion_demand_norm (N(3, 1) ?)
            
            - Roads (gdf):
                1. demand_norm (N(3, 1) ?)
                2. width       (N(15, 10) ?)
                3. danger_norm (N(3, 1) ?)
                4. length (to calculate the actual cost)
                5. length_norm (normalized by length) 
        

            len(A) = 36590, len(Roads) = 7666. Maybe we should generate data with length like this. Not sure if the index of them should be the same.
            """
            #! Roads, A = generateInstance()
            #! Roads = Roads[Roads['width'] >= Roads["width"].quantile(0.5)]
        

            # * filter the data by argument option "remove_existing"
            if args.remove_existing:
                Roads = Roads[Roads["has_bike_lane"] == 0]

            #print(A.head())
            
            # filter to only consider adjacency of roads in the Roads set
            A = A[
                A["road_i"].isin(Roads.index) 
                & A["road_j"].isin(Roads.index)
            ]
            
            M = Model(args = args)
            M.setup(A, Roads, MRTs)
            result = M.optimize()
            # TODO save the result to the container
            # M.save_result(time_spent = result[1])
            # M.visualizeSolution()

