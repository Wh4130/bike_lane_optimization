import matplotlib.pyplot as plt
import matplotlib.patches as mpatches # Import for Patch
import geopandas as gpd
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "sans-serif",
    "font.sans-serif": "Helvetica",
})

def plot_map(alg, name, road_gdf, sol, mu, alpha, B_L, w, tau, scale):

    assert alg in ["naive", "heuristic"], "'alg' should be either naive or heuristic"

    if alg == "naive":
        path = f"sol_heuristic/output_h1/{name}/{name}_result.png"
        title = f'{name.capitalize().replace("_", " ")}; Naive Algorithm'
    elif alg == "heuristic":
        path = f"sol_heuristic/output_h2/{name}/{name}_result.png"
        title = f'{name.capitalize().replace("_", " ")}; Heuristic Algorithm'
        
        
    plt.rcParams['hatch.color'] = 'gray'


    fig, ax = plt.subplots(1, 1, figsize = (15, 15))
    road_gdf.plot(color = "lightgray", ax = ax, alpha = 0.4)
    road_gdf[road_gdf["has_bike_lane"] == 1].plot(color = "lightgray", ax = ax, alpha = 0.8, label = "existing lanes")

    try:
        sol[(sol["has_bike_lane"] == 1) & (sol["roadType"] == 1)].plot(color = "#66BFF6", ax = ax, edgecolor=None, hatch = "///")
    except:
        pass
    try:
        sol[(sol["has_bike_lane"] == 1) & (sol["roadType"] == 2)].plot(color = "orange", ax = ax, edgecolor=None, hatch = "///")
    except:
        pass

    sol[(sol["has_bike_lane"] == 0) & (sol["roadType"] == 1)].plot(color = "#66BFF6", ax = ax, edgecolor=None)
    sol[(sol["has_bike_lane"] == 0) & (sol["roadType"] == 2)].plot(color = "orange", ax = ax, edgecolor=None)

    ax.set_xlim([121.5, 121.59])
    ax.set_ylim([25, 25.085])

    ax.set_title(title, fontsize = 20)
    ax.grid(True, color='lightgray')


    # Create proxy artists for the legend
    bike_lane_patch_1 = mpatches.Patch(color='#66BFF6', edgecolor=None, label='Type 1')
    bike_lane_patch_2 = mpatches.Patch(color='orange', edgecolor=None, label='Type 2')


    # Add the legend using the proxy artists
    ax.legend(handles=[bike_lane_patch_1, bike_lane_patch_2], loc='upper left')

    for spine in ax.spines.values():
        spine.set_color('lightgray')
    ax.set_aspect('equal')


    text = f"Road Segments filled with Gray Slash / refer to already existing bike lanes" 
    params = rf"$$\mu = {mu};   \alpha = {alpha};   B^L = {B_L};   w = {w};   \tau = {tau};   scale = {scale}$$"
    ax.text(0.5, 0.98, text,
            horizontalalignment='center', 
            verticalalignment='top',      
            transform=ax.transAxes,       
            fontsize=12,
            color='#423D3D')
    ax.text(0.5, 0.96, params,
            horizontalalignment='center', 
            verticalalignment='top',      
            transform=ax.transAxes,       
            fontsize=15,
            color='black')

    fig.savefig(path, dpi=300, bbox_inches='tight')