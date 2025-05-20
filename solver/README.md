# Experiments

To run the experiment, please input the command into your terminal by the following rule:

`python3 solver/Main_wally.py --exp_name scenario[sID] --mu [mu] --alpha [alpha] --B_length [B_length] --w [w] --scale [scale]`

To run all pre-defined experiments by once, please run the following command in your terminal:
`python3 solver/standard_experiment.py`

The parameter $\tau$ (tau) is not our main focus for comparison. However, for some scenario setting, low $\tau$ makes the feasible region too small and thus the program becomes infeasible. After some testing, we determine that $\tau = 300$ is the best level as it makes all scenario feasible.

## Solver (Gurobi)
|sID|description | mu     | alpha      | B_length | w | tau | scale
|-| - | - |- |- |- |- |- |
|1|Low Budget | 0.2 | 0.2 | 25,000 | 3 | 300 | medium
|2|Medium Budget | 0.2 | 0.2 | 50,000 | 3 | 300 | medium
|3|High Budget | 0.2 | 0.2 | 100,000 | 3 | 300 | medium
|4|Small Scale | 0.2 | 0.2 | 50000 | 3 | 300 | small
|5|Large Scale | 0.2 | 0.2 | 50000 | 3 | 300 | large
|6|Balanced Road and Adjacency| 0.5 | 0.2 | 50000 | 3 | 300 | medium
|7|Lower Preference toward Adjacency Utility| 0.8 | 0.2 | 50000 | 3 | 300 | medium
|8|Lower Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 50000 | 2.5 | 300 | medium
|9|Higher Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 50000 | 3.5 | 300 | medium