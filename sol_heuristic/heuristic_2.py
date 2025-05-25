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
from plot_utils import plot_map
from utils import expDataGenerator


"""
This is another heuristic algorithm. This algorithm does not consider the second constrant: MRT coverage. 
This algorithm is a modified version of the very naive algorithm, which focuses on the adjacency

For each iteration, it does:
1. Check the intersection with the highest demand (utility)
2. Check for the intersection (i, j) (with the highest demand) whether both road i and road j are in the candidate
    If not, then build.
"""

def parse_args():
    parser = argparse.ArgumentParser()
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
        "--d", type = int,
        default = 3,
        help = "parameter d (maximum degree constr)"
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

def decorator_timer(some_function):
    from time import time

    def wrapper(*args, **kwargs):
        t1 = time()
        result = some_function(*args, **kwargs)
        end = time()-t1
        return result, end
    return wrapper


class Heuristic:
    def __init__(self, args):
        self.args = args
        self.verbose = True
        self.result = {}
        
    @decorator_timer
    def setup(self, Intersections, Roads):
        self.Roads = Roads
        self.mu    = self.args.mu
        self.alpha = self.args.alpha
        self.B_L   = self.args.B_length
        self.w     = self.args.w
        self.d     = self.args.d

        self.status = "pending"
        
        # set of all roads and intersections
        self.roadIDs = Roads.index 
        self.Intersections = Intersections
        
        self.roadIDs              = self.roadIDs.tolist()
        # self.intersectingRoadIDs  = self.intersectingRoadIDs.tolist()
  
        self.x1_sol_idx = []
        self.x2_sol_idx = []
        self.y_sol_idx  = []
        self.road_utility  = 0
        self.int_utility   = 0
        self.total_utility = 0


        # * Generate a column: road utility (balanced with alpha)
        self.Roads["Util"] = (self.Roads["length_norm"] ** self.alpha) * (self.Roads["roadDemand_m2_norm"] ** (1 - self.alpha))
        self.Roads.fillna({"Util": self.Roads["Util"].mean()}, inplace = True)

    @decorator_timer
    def optimize(self):
        self.Intersections["idx_pair"] = "(" + self.Intersections["road_i"].astype(str) + ", " + self.Intersections["road_j"].astype(str)  + ")"
        self.Intersections.set_index("idx_pair", inplace = True)

        candidates_roads         = self.Roads.index.tolist()
        selected_roads           = []
        binding_set              = pd.Series([0] * len(candidates_roads), index = candidates_roads)
        self.B_L_use = self.B_L

        

        while self.B_L_use > 0:

            for _ in (binding_set[binding_set >= self.d]).index.tolist():
                try:
                    candidates_roads.remove(_)
                except:
                    pass

            # max_adj_y_constr = pd.Series(selected_roads_paird).value_counts()
            # max_adj_y_constr = max_adj_y_constr[max_adj_y_constr >= self.d].index.tolist()

            if not candidates_roads:
                break

            
            built = False
            # * If the selected_roads is empty, initialize it by the road with highest utility
            if selected_roads == []:
                max_idx = self.Roads.loc[candidates_roads, "Util"].idxmax()

                if max_idx in (binding_set[binding_set > self.d]).index.tolist():
                    candidates_roads.remove(max_idx)
                    continue

                XOR0 = (self.Intersections["road_i"] == max_idx) ^ (self.Intersections["road_j"] == max_idx)
                int_subset = self.Intersections.loc[XOR0, :]

                partners = []
                for _, row in int_subset.iterrows():
                    if row["road_i"] == max_idx:
                        partners.append(row["road_j"])
                    elif row["road_j"] == max_idx:
                        partners.append(row["road_i"])
                partners = list(set(partners))

                # * Check if the degree constraint is violated:
                count = 0
                stop_status = False
                binding_d = False
                for partner in partners:
                    if partner in list(set(self.x1_sol_idx + self.x2_sol_idx)):
                        count += 1
                        if partner in (binding_set[binding_set >= self.d]).index.tolist():
                            stop_status = True
                            break
                    if count == self.d:
                        binding_d = True
                    if count > self.d:
                        stop_status = True       # * If more than two paired roads are built, then break
                        break
                if stop_status:
                    candidates_roads.remove(max_idx)
                    continue
            
                # * First check the degree of danger (check if it's good to buiuld level 2)
                if self.Roads.loc[max_idx, "danger_m2_norm"] > self.w * 2.5:

                    # * If larger than self.w, check whether the budget constraint is enough
                    if self.B_L_use - self.Roads.loc[max_idx, "length"] * self.w >= 0:

                        # * If enough, subtract B_L_use by length i * self.w, and add i to self.x2_sol
                        self.B_L_use -= self.Roads.loc[max_idx, "length"] * self.w
                        self.x2_sol_idx.append(max_idx)
                        self.road_utility += float(self.Roads.loc[max_idx, "Util"] * self.Roads.loc[max_idx, "danger_m2_norm"])
                        candidates_roads.remove(max_idx)
                        selected_roads.append(max_idx)
                        built = True

                        continue # * Go to the next iteration

                    

                # * If does not pass the first check, then use level 1 bike lane
                if self.Roads.loc[max_idx, "danger_m2_norm"] <= self.w * 2.5:

                    # * also check availability
                    if self.B_L_use - self.Roads.loc[max_idx, "length"] >= 0:

                        self.B_L_use -= self.Roads.loc[max_idx, "length"]
                        self.x1_sol_idx.append(max_idx)
                        self.road_utility += float(self.Roads.loc[max_idx, "Util"])
                        candidates_roads.remove(max_idx)
                        selected_roads.append(max_idx)
                        built = True

                    else:
                        candidates_roads.remove(max_idx)
                        break
                
                else:
                    candidates_roads.remove(max_idx)
                    continue
                if built:
                    for _, road in self.Intersections.loc[(self.Intersections["road_i"] == max_idx), :].iterrows():
                        binding_set[road["road_j"]] += 1
                    for _, road in self.Intersections.loc[(self.Intersections["road_j"] == max_idx), :].iterrows():
                        binding_set[road["road_i"]] += 1
                    for partner in partners:
                        if partner in list(set(self.x1_sol_idx + self.x2_sol_idx)):
                            pair = "(" + ", ".join([str(int(_)) for _ in sorted([partner, max_idx], reverse = False)]) + ")"
                            self.int_utility += self.Intersections.loc[ pair, "intersection_demand_norm"]
                            self.y_sol_idx.append(pair)
                    if binding_d:
                        to_remove = []
                        for _, road in self.Intersections.loc[(self.Intersections["road_i"] == max_idx), :].iterrows():
                            to_remove.append(road["road_j"])
                        for _, road in self.Intersections.loc[(self.Intersections["road_j"] == max_idx), :].iterrows():
                            to_remove.append(road["road_i"])
                        for _ in to_remove:
                            try:
                                candidates_roads.remove(_)
                            except:
                                pass



            # * If selected_roads is not empty, search among intersections where one road is selected, find the pair with the highest utility, and then select the other road in that pair.
            else:
                
                for _ in (binding_set[binding_set >= self.d]).index.tolist():
                    try:
                        candidates_roads.remove(_)
                    except:
                        pass
                XOR = ((self.Intersections["road_i"].isin(selected_roads) ^ self.Intersections["road_j"].isin(selected_roads)) 
                       & 
                       (self.Intersections["road_i"].isin(candidates_roads) ^ self.Intersections["road_j"].isin(candidates_roads))
                       &
                        ~(self.Intersections["road_i"].isin((binding_set[binding_set >= self.d]).index.tolist()) | self.Intersections["road_j"].isin((binding_set[binding_set >= self.d]).index.tolist()))
                       )

                int_subset = self.Intersections.loc[XOR, :]
                

                if len(int_subset) == 0:
                    selected_roads = []
                    continue 
                    # * if all selected roads have no adjacent roads, reset selected_roads = [] and find next road with the highest utility.
                
                # print(candidates_intersections)
                int_subset_idxmax = int_subset["intersection_demand_norm"].idxmax()

                if int_subset.loc[int_subset_idxmax, "road_i"].astype(int) in selected_roads:
                    road_selected = int_subset.loc[int_subset_idxmax, "road_j"]
                else:
                    road_selected = int_subset.loc[int_subset_idxmax, "road_i"]

                partners = []
                for _, row in int_subset.iterrows():
                    if row["road_i"] == road_selected:
                        partners.append(row["road_j"])
                    elif row["road_j"] == road_selected:
                        partners.append(row["road_i"])
                partners = list(set(partners))

                # * Check if the degree constraint is violated:
                count = 0
                stop_status = False
                binding_d = False
                for partner in partners:
                    if partner in list(set(self.x1_sol_idx + self.x2_sol_idx)):
                        count += 1
                        if partner in (binding_set[binding_set >= self.d]).index.tolist():
                            stop_status = True
                            break
                    if count == self.d:
                        binding_d = True
                    if count > self.d:
                        stop_status = True       # * If more than two paired roads are built, then break
                        break
                if stop_status:
                
                    candidates_roads.remove(road_selected)
                    continue
                    


                built = False
                # * First check the degree of danger (check if it's good to buiuld level 2)
                if self.Roads.loc[road_selected, "danger_m2_norm"] > self.w * 2.5:

                    # * If larger than self.w, check whether the budget constraint is enough
                    if self.B_L_use - self.Roads.loc[road_selected, "length"] * self.w >= 0:

                        # * If enough, subtract B_L_use by length i * self.w, and add i to self.x2_sol
                        self.B_L_use -= self.Roads.loc[road_selected, "length"] * self.w
                        self.x2_sol_idx.append(road_selected)
                        self.road_utility += float(self.Roads.loc[road_selected, "Util"] * self.Roads.loc[road_selected, "danger_m2_norm"])
                        # self.int_utility += self.Intersections.loc[int_subset_idxmax, "intersection_demand_norm"]
                        candidates_roads.remove(road_selected)
                        selected_roads.append(road_selected)
                        built = True

                        continue # * Go to the next iteration

                    

                # * If does not pass the first check, then use level 1 bike lane
                if self.Roads.loc[road_selected, "danger_m2_norm"] <= self.w * 2.5:

                    # * also check availability
                    if self.B_L_use - self.Roads.loc[road_selected, "length"] >= 0:

                        self.B_L_use -= self.Roads.loc[road_selected, "length"]
                        self.x1_sol_idx.append(road_selected)
                        self.road_utility += float(self.Roads.loc[road_selected, "Util"])
                        # self.int_utility += self.Intersections.loc[int_subset_idxmax, "intersection_demand_norm"]
                        candidates_roads.remove(road_selected)
                        selected_roads.append(road_selected)
                        built = True

                    else:
                        candidates_roads.remove(road_selected)
                        break
                
                else:
                    candidates_roads.remove(road_selected)
                    continue

                if built:
                    for _, road in self.Intersections.loc[(self.Intersections["road_i"] == road_selected), :].iterrows():
                        binding_set[road['road_j']] += 1
                    for _, road in self.Intersections.loc[(self.Intersections["road_j"] == road_selected), :].iterrows():
                        binding_set[road['road_i']] += 1
                    for partner in partners:
                        if partner in list(set(self.x1_sol_idx + self.x2_sol_idx)):
                            pair = "(" + ", ".join([str(int(_)) for _ in sorted([partner, road_selected], reverse = False)]) + ")"
                            self.int_utility += self.Intersections.loc[ pair, "intersection_demand_norm"]
                            self.y_sol_idx.append(pair)
                    if binding_d:
                        to_remove = []
                        for _, road in self.Intersections.loc[(self.Intersections["road_i"] == road_selected), :].iterrows():
                            to_remove.append(road["road_j"])
                        for _, road in self.Intersections.loc[(self.Intersections["road_j"] == road_selected), :].iterrows():
                            to_remove.append(road["road_i"])
                        for _ in to_remove:
                            try:
                                candidates_roads.remove(_)
                            except:
                                pass
   
        # # * Calculate the adjacency
        # self.x_idx = list(set(self.x1_sol_idx + self.x2_sol_idx))
        # for i in self.x_idx:
        #     for j in self.x_idx:
        #         pair = f"({i}, {j})"
        #         if pair in self.Intersections.index.tolist():
        #             self.y_sol_idx.append(pair)
        #             U_yij = float(self.Intersections.loc[pair, "intersection_demand_norm"])
        #             self.int_utility += U_yij

        self.total_utility = self.road_utility * self.mu + self.int_utility *  (1 - self.mu)

        if not self.args.exp_mode:
            print("======================== Heuristic Result =========================")

            params = ["mu", "alpha", "B_L", "w", "d", "scale"]
            values = [self.mu, self.alpha, self.B_L, self.w, self.d, self.args.scale]
            print(f"---------------------- parameters --------------------------------")
            print("    ".join("{:>6}".format(val) for val in params))
            print("    ".join("{:>6}".format(val) for val in values))
            print(f"number of type 1 bike lanes (x_i1 = 1): {len(self.x1_sol_idx)}")
            print(f"number of type 2 bike lanes (x_i2 = 1): {len(self.x2_sol_idx)}")
            print(f"number of served intersections (y_ij = 1): {len(self.y_sol_idx)}")
            print(f"---------------------- Objective Value ---------------------------")
            print(f"Obj val:              {'{:>25.3f}'.format(self.total_utility)}")
            print(f"Road Utility:         {'{:>25.3f}'.format(self.road_utility)}")
            print(f"Intersection Utility: {'{:>25.3f}'.format(self.int_utility)}")
                    
        self.result = {"x1": self.x1_sol_idx,"x2": self.x2_sol_idx, "y": self.y_sol_idx, "obj_val": self.total_utility}
        # ls = []
        # for pair in self.y_sol_idx:
        #     ls += pair.replace("(", "").replace(")", "").replace(" ", "").split(",")

    def save_result(self, time_spent):
        # * making directory
        if self.args.exp_name != "default":
            name = self.args.exp_name
        else:
            name = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "_")
        os.makedirs(f"sol_heuristic/output_h2/{name}", exist_ok = True)

        assert self.result != {}, "please run optimization first so there would be result to save."

        # * saving solution of roads
        x1_df = pd.DataFrame({"roadID": self.result["x1"], "roadType": 1})
        x2_df = pd.DataFrame({"roadID": self.result["x2"], "roadType": 2})

        x1_df_merged = pd.merge(x1_df, Roads, how = 'left', on = 'roadID')
        x2_df_merged = pd.merge(x2_df, Roads, how = 'left', on = 'roadID')

        result_gdf = pd.concat([x1_df_merged, x2_df_merged])
        result_gdf = gpd.GeoDataFrame(result_gdf, geometry = "geometry")
        result_gdf.to_parquet(f"sol_heuristic/output_h2/{name}/roads_sol.parquet")
        self.sol_gdf = result_gdf

        # * saving hyperparameter, objective value, and time cost
        meta = {
            "hyperparams": {
                "mu": self.mu,
                "alpha": self.alpha,
                "B_L": self.B_L,
                "w": self.w,
                "d": self.d,
                "scale": self.args.scale
            },
            "obj_val": {
                "total_utility": self.total_utility,
                "road_utility": self.road_utility,
                "int_utility": self.int_utility,
                "road_util_prop": self.road_utility / self.total_utility,
                "int_util_prop": self.int_utility / self.total_utility
            },
            "cal_time_sec": time_spent,
            "result_description": {
                "num_x1": len(x1_df),
                "num_x2": len(x2_df),
                "num_y": len(self.result['y'])
            },
            "policy_similarity": result_gdf[result_gdf["has_bike_lane"] == 1]['length'].sum() / result_gdf['length'].sum() if not self.args.remove_existing else None
        }

        with open(f"sol_heuristic/output_h2/{name}/meta_data.json", "w") as file:
            json.dump(meta, file, ensure_ascii = False, indent = True)

        print(f"solutions and metadata saved to output_h2/{name} folder")

    # def print_(self, message):
    #     if self.verbose:
    #         print(message)
            
    def visualizeSolution(self):
        Roads = gpd.read_parquet(self.args.road_data)

        plot_map(
            "heuristic",
            self.args.exp_name,
            Roads, self.sol_gdf,
            self.mu, self.alpha, self.B_L, self.w, self.d, self.args.scale
        )
        print("Visualization done!")
    


if __name__ == "__main__":
    args = parse_args()

    # Roads = pd.read_parquet("../data/processed/road_data.parquet").iloc[20:30]
    Roads = gpd.read_parquet(args.road_data)
    Roads.set_index('roadID', inplace=True)
    A = gpd.read_parquet(args.adj_mat)

    if not args.exp_mode:
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
        
        M = Heuristic(args = args)
        M.setup(A, Roads)
        result = M.optimize()
        M.save_result(time_spent = result[1])
        M.visualizeSolution()

    else:
        expResults = pd.DataFrame(
            columns = ["scenarioID", "solverObjVal", "solverTime", "solverX1num", "solverX2num", "solverYnum"]
        )
        for _ in tqdm(range(30)):
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
            ExpRoads, ExpA = expDataGenerator(Roads, A)
            ExpRoads.set_index("roadID", inplace = True)
            ExpRoads = ExpRoads[ExpRoads['width'] >= ExpRoads["width"].quantile(0.5)]

            #! Roads, A = generateInstance()
        

            # * filter the data by argument option "remove_existing"
            if args.remove_existing:
                ExpRoads = ExpRoads[ExpRoads["has_bike_lane"] == 0]

            #print(A.head())
            
            # filter to only consider adjacency of roads in the Roads set
            ExpA = ExpA[
                ExpA["road_i"].isin(ExpRoads.index) 
                & ExpA["road_j"].isin(ExpRoads.index)
            ]
            
            M = Heuristic(args = args)
            M.setup(ExpA, ExpRoads)
            result = M.optimize()
            # TODO save the result to the container
            expResults.loc[len(expResults), :] = [
                args.exp_name.replace("scenario_", ""),
                M.result["obj_val"],
                result[1],
                len(M.result["x1"]),
                len(M.result["x2"]),
                len(M.result["y"])
            ]

        if args.exp_name != "default":
            name = args.exp_name
        else:
            name = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ", "_")
        expResults.to_excel(f"./sol_heuristic/experiments_h2/{name}.xlsx")

    
    

