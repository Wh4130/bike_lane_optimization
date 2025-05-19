import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import argparse
import matplotlib.pyplot as plt

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
        "--scale", type = str, choices = ["small", "medium", "large"],
        default = "medium",
        help = "scale of the model (the number of decision variables)"
    )
    parser.add_argument(
        "--log", action = "store_true",
        help = "show log to console"
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
    def __init__(self):
        self.model = gp.Model('BikelaneOptimization')
        self.model.setParam('OutputFlag', 0)
        if not args.log:
            self.model.Params.LogToConsole = 0
        self.verbose = True
        
    @decorator_timer
    def setup(self, Intersections, Roads):
        numberRoadsAllowed = 20
        self.mu = 0.7
        
        # set of all roads
        self.roadIDs = Roads.index #pd.unique(Roads.index.values.ravel()).astype(int)
        #print(self.roadIDs)
        # self.intersectingRoadIDs = pd.unique(Intersections[['road_i','road_j']].values.ravel()).astype(int)
        #print(self.intersectingRoadIDs, len(self.intersectingRoadIDs))
        self.Intersections = Intersections
        
        self.roadIDs              = self.roadIDs.tolist()
        # self.intersectingRoadIDs  = self.intersectingRoadIDs.tolist()
        
        
        # ========= Decision variables ========================================
        self.print_("Setting up variables...")
        self.x = self.model.addVars(self.roadIDs, name="x", vtype=GRB.BINARY)
        
        self.y = self.model.addVars(list(Intersections[['road_i','road_j']].itertuples(index=False, name=None)), name="y", vtype=GRB.BINARY)
            
        
        # ========= Objective function ========================================
        self.print_("Setting up objective function...")
        
        roadUtility = gp.quicksum(
            Roads.loc[i, "roadDemand_m2_norm"] * self.x[i]
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
        self.model.addConstr(gp.quicksum(1 * self.x[i] for i in self.roadIDs) <= numberRoadsAllowed, name="totalCost")  # simple contraint for testing: only build 4 roads
        
        # linking of y to x              
        for i, j in Intersections[['road_i','road_j']].itertuples(index=False, name=None):
            self.model.addConstr(self.y[i, j] >= self.x[i] + self.x[j] - 1, name="")
            self.model.addConstr(self.y[i, j] <= self.x[i], name="")
            self.model.addConstr(self.y[i, j] <= self.x[j], name="")
        
    
    @decorator_timer  
    def optimize(self):
        # Optimize the model
        print("optimizing model...")
        self.model.optimize()
        print("optimizing complete")

        # Print the solution
        if self.model.status == GRB.OPTIMAL:
            self.print_("Optimization successfull")

            x_sol = np.array([self.x[i].X for i in self.roadIDs])

            y_sol = np.array([
                [
                    self.y[j, i].X if (j, i) in self.y else 0
                    for i in self.roadIDs
                ]
                for j in self.roadIDs
            ])

            x_sol_idx = []
            y_sol_idx = []

            for i in self.roadIDs:
                if self.x[i].X > 0:
                    x_sol_idx.append(i)
                for j in self.roadIDs:
                    if (i, j) in self.y and self.y[i, j].X > 0:
                        y_sol_idx.append((i, j))

            
            # print(x_sol)
            # print(y_sol)
            
            # print_(np.sum(x_sol), np.sum(y_sol))
            return {"x": x_sol_idx, "y": y_sol_idx, "obj_val": self.model.obj_val}
            
            print("intersections per road = ", np.sum(y_sol) / np.sum(x_sol))
            
    
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
    Roads = pd.read_parquet(args.road_data)
    Roads.set_index('roadID', inplace=True)
    A = pd.read_parquet(args.adj_mat)
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
    
    M = Model()
    M.setup(A, Roads)
    print(M.optimize())

    
    

