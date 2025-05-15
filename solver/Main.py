import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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
        self.model.Params.LogToConsole = 0
        self.verbose = True
        
    @decorator_timer
    def setup(self, Adjacency, Roads):
        Demand = np.array(Roads["roadDemand_m2_norm"])
        
        roadIDs = Roads.index
        print(roadIDs)
        # set of all roads
        S_R = roadIDs
        
        # ========= Decision variables ========================================
        self.print_("Setting up variables...")
        self.x = self.model.addVars(S_R, name="x", vtype=GRB.BINARY)
        self.y = self.model.addVars(S_R, S_R, name="y", vtype=GRB.BINARY)
        
        
        # ========= Objective function ========================================
        self.print_("Setting up objective function...")
        roadUtility = gp.quicksum(
            Roads.loc[i, "roadDemand_m2_norm"] * self.x[i]
            for i in S_R
        )
        
        self.model.setObjective(roadUtility, GRB.MAXIMIZE)
        
        # ========= Constraints ===============================================
        self.print_("Setting up constraints...")
        self.model.addConstr(gp.quicksum(1 * self.x[i] for i in S_R) <= 4, name="totalCost")  # simple contraint for testing: only build 4 roads
        
    
    @decorator_timer  
    def optimize(self):
        # Optimize the model
        print("optimizing model...")
        self.model.optimize()
        print("optimizing complete")

        # Print the solution
        if self.model.status == GRB.OPTIMAL:
            pass
            #print(self.x)
            
    
    def print_(self, message):
        if self.verbose:
            print(message)
    


if __name__ == "__main__":
    # some dummy data for testing
    # 1) the red‐labels in the order you drew them, with the (1–3) edge now labeled "1"
    # edge_ids  = [2, 3, 1, 10, 9, 11, 14, 13, 4, 5, 6, 8, 7, 12]
    

    # # 2) the original endpoints of each red‐labelled edge in that same order
    # edge_ends = [
    #     (1,4),  # id=2
    #     (1,2),  # id=3
    #     (1,3),  # id=1   ← changed from 7 to 1
    #     (2,3),  # id=10
    #     (2,5),  # id=9
    #     (3,7),  # id=11
    #     (3,9),  # id=14
    #     (7,9),  # id=13
    #     (4,5),  # id=4
    #     (4,8),  # id=5
    #     (5,8),  # id=6
    #     (5,6),  # id=8
    #     (6,8),  # id=7
    #     (6,7),  # id=12
    # ]

    # # 3) build an empty DataFrame, indexed by those red‐labels
    # A = pd.DataFrame(0, index=edge_ids, columns=edge_ids)

    # # 4) fill in a 1 whenever two edges share a node
    # for eid1, (u,v) in zip(edge_ids, edge_ends):
    #     for eid2, (x,y) in zip(edge_ids, edge_ends):
    #         if eid1 != eid2 and (u in (x,y) or v in (x,y)):
    #             A.loc[eid1, eid2] = 1

    # #print(A)
    
    # demands = np.random.rand(len(edge_ids))
    
    # Roads = pd.DataFrame({'demand': demands}, index=edge_ids)
    Roads = pd.read_parquet("../data/processed/road_data.parquet")
    
    print(Roads.head())
    
    
    M = Model()
    print(M.setup(None, Roads))
    print(M.optimize())

    
    

