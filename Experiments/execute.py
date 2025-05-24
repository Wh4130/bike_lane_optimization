import subprocess
import argparse



# Command as a list of strings (recommended to avoid shell injection)
Commands = [
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_1", "--B_length", "25000"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_2"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_3", "--B_length", "100000"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_4", "--mu", "0.5"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_5", "--mu", "0.8"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_6", "--w", "2.5"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_7", "--w", "3.5"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_1_np", "--B_length", "5000", "--remove_existing"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_2_np", "--remove_existing", "--B_length", "10000"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_3_np", "--B_length", "15000", "--remove_existing"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_4_np", "--mu", "0.5", "--remove_existing", "--B_length", "10000"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_5_np", "--mu", "0.8", "--remove_existing", "--B_length", "10000"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_6_np", "--w", "2.5", "--remove_existing", "--B_length", "10000"],
    ["python3", "Experiments/main.py", "--exp_mode", "--exp_name", "scenario_7_np", "--w", "3.5", "--remove_existing", "--B_length", "10000"]
]

if __name__ == "__main__":

    print(f"=====================================")
    print(f"=== ** Experiment by Fake Data ** ===")
    print(f"=====================================")

    for i, command in enumerate(Commands):

        print(f"===   Running Experiment {command[4]}   ===")


        try:
            # Run the command and capture the output
            result = subprocess.run(command, capture_output=False, text=True, check=True)

            # Print the standard output
            print("Standard Output:")
            print(result.stdout)

            # Print the return code
            print(f"Return Code: {result.returncode}")

        except subprocess.CalledProcessError as e:
            # Handle errors if the command returns a non-zero exit code
            print(f"Error running command: {e}")
            print(f"Stderr: {e.stderr}")
        except FileNotFoundError:
            print(f"Error: Command '{command[0]}' not found.")