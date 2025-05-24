# Experiments

To run the experiment, please input the command into your terminal by the following rule:

`python3 solver/Main_wally.py --exp_name scenario[sID] --mu [mu] --alpha [alpha] --B_length [B_length] --w [w] --scale [scale]`

To run all pre-defined experiments by once, please run the following command in your terminal:
`python3 solver/standard_experiment.py`

The parameter $\tau$ (tau) is not our main focus for comparison. However, for some scenario setting, low $\tau$ makes the feasible region too small and thus the program becomes infeasible. After some testing, we determine that $\tau = 300$ is the best level as it makes all scenario feasible.

## Experiments
|sID|description | mu     | alpha      | B_length | w | scale | rm_ex |
|-| - | - |- |- |- |- | - |
|1|Low Budget | 0.2 | 0.2 | 25,000 | 3 | medium | False
|2|Medium Budget | 0.2 | 0.2 | 50,000 | 3 | medium | False
|3|High Budget | 0.2 | 0.2 | 100,000 | 3| medium |False
|4|Balanced Road and Adjacency| 0.5 | 0.2 | 50000 | 3 | medium | False
|5|Lower Preference toward Adjacency Utility| 0.8 | 0.2 | 50000 | 3 | medium | False
|6|Lower Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 50000 | 2.5  | medium | False
|7|Higher Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 50000 | 3.5 | medium |False
|1_np|Low Budget | 0.2 | 0.2 | 5,000 | 3 | medium | True
|2_np|Medium Budget | 0.2 | 0.2 | 10,000 | 3 | medium | True
|3_np|High Budget | 0.2 | 0.2 | 15,000 | 3| medium |True
|4_np|Balanced Road and Adjacency| 0.5 | 0.2 | 50000 | 3 | medium | True
|5_np|Lower Preference toward Adjacency Utility| 0.8 | 0.2 | 50000 | 3 | medium | True
|6_np|Lower Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 10000 | 2.5  | medium | True
|7_np|Higher Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 10000 | 3.5 | medium |True

