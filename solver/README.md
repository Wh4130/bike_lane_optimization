# Experiments

To run the experiment, please input the command into your terminal by the following rule:

`python3 solver/Main_wally.py --exp_name scenario[sID] --mu [mu] --alpha [alpha] --B_length [B_length] --w [w] --scale [scale]`

## Solver (Gurobi)
|sID|description | mu     | alpha      | B_length | w | tau | scale
|-| - | - |- |- |- |- |- |
|1|Low Budget | 0.2 | 0.2 | 25,000 | 3 | 100 | medium
|2|Medium Budget | 0.2 | 0.2 | 50,000 | 3 | 100 | medium
|3|High Budget | 0.2 | 0.2 | 100,000 | 3 | 100 | medium
|4|Small Scale | 0.2 | 0.2 | 50000 | 3 | 100 | small
|5|Large Scale | 0.2 | 0.2 | 50000 | 3 | 100 | large
|6|Balanced Road and Adjacency| 0.5 | 0.2 | 50000 | 3 | 100 | medium
|7|Lower Preference toward Adjacency Utility| 0.8 | 0.2 | 50000 | 3 | 100 | medium
|8|Lower Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 50000 | 2.5 | 100 | medium
|9|Higher Unit Cost for Level 2 Bike Lanes| 0.2 | 0.2 | 50000 | 3.5 | 100 | medium