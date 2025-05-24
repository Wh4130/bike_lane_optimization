from time import time
import numpy as np
from scipy.stats import gamma

def decorator_timer(some_function):
    def wrapper(*args, **kwargs):
        t1 = time()
        result = some_function(*args, **kwargs)
        end = time()-t1
        return result, end
    return wrapper

def getGammaApprox(Roads, A):
    # * Fit data by Gamma Distribution
    shape_1, loc_1, scale_1 = gamma.fit(Roads["roadDemand_m2_norm"])
    shape_2, loc_2, scale_2 = gamma.fit(Roads["danger_m2_norm"])
    shape_3, loc_3, scale_3 = gamma.fit(Roads["length"])
    shape_4, loc_4, scale_4 = gamma.fit(A["intersection_demand_norm"])

    return ((shape_1, loc_1, scale_1), (shape_2, loc_2, scale_2), (shape_3, loc_3, scale_3), (shape_4, loc_4, scale_4))

def expDataGenerator(roadData, adjData, gammaApprox):
    # * Copy data to prevent raw data collapse
    Roads = roadData.copy()
    Roads["roadID"] = Roads.index.tolist()
    A = adjData.copy()

    # * Fit data by Gamma Distribution
    (shape_1, loc_1, scale_1), (shape_2, loc_2, scale_2), (shape_3, loc_3, scale_3), (shape_4, loc_4, scale_4) = gammaApprox

    # * Generate Roads Data by Gamma Distribution
    Roads["roadDemand_m2_norm"] = loc_1 + np.random.gamma(shape = shape_1, scale= scale_1, size = len(Roads))
    Roads["danger_m2_norm"] = loc_2 + np.random.gamma(shape = shape_2, scale= scale_2, size = len(Roads))
    Roads["length"] = loc_3 + np.random.gamma(shape = shape_3, scale= scale_3, size = len(Roads))
    Roads["length_norm"] = 3 + (Roads["length"] - Roads["length"].mean()) / Roads["length"].std()

    # * Generate Adjacency Data
    A["intersection_demand_norm"] = loc_4 + np.random.gamma(shape = shape_4, scale= scale_4, size = len(A))

    Roads = Roads[[
        "roadID", "length", "length_norm", "width", "roadDemand_m2_norm", "danger_m2_norm", "has_bike_lane"
    ]]
    A = A[[
        "road_i", "road_j", "intersection_demand_norm"
    ]]
    A["road_i"] = A["road_i"].astype(int)
    A["road_j"] = A["road_j"].astype(int)
    
    Roads["length_norm"] = Roads["length_norm"].apply(lambda x: 3 if x <= 0 else x)
    mean_length_value = Roads['length'].mean()
    Roads["length"] = np.where(Roads["length_norm"] == 3, mean_length_value, Roads["length"])


    return Roads, A