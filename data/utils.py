import numpy as np
import pandas as pd

def expDataGenerator(roadData, adjData):
    Roads = roadData.copy()
    Roads["roadID"] = Roads.index.tolist()
    A = adjData.copy()

    len_avg, len_std = Roads['length'].mean(), Roads['length'].std()
    wid_avg, wid_std = Roads["width"].mean(), Roads["width"].std()

    # * Generate Roads Data
    Roads["roadDemand_m2_norm"] = np.random.gamma(shape = 8, scale= 0.3, size = len(Roads))
    Roads["danger_m2_norm"] = 2 + np.random.gamma(shape = 2, scale= 0.3, size = len(Roads))
    Roads["length"] = srs3 = np.random.gamma(shape = 120, scale= 3, size = len(Roads)) - 300
    Roads["length_norm"] = (Roads["length"] - Roads["length"].mean()) / Roads["length"].std()

    # * Generate Adjacency Data
    A["intersection_demand_norm"] = np.random.gamma(shape = 8, scale= 0.3, size = len(A))

    Roads = Roads[[
        "roadID", "length", "length_norm", "width", "roadDemand_m2_norm", "danger_m2_norm", "has_bike_lane"
    ]]
    A = A[[
        "road_i", "road_j", "intersection_demand_norm"
    ]]
    A["road_i"] = A["road_i"].astype(int).astype(str)
    A["road_j"] = A["road_j"].astype(int).astype(str)


    return Roads, A