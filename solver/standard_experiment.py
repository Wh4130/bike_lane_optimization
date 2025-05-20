import subprocess

# Command as a list of strings (recommended to avoid shell injection)
Commands = [
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_1", "--B_length", "25000"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_2"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_3", "--B_length", "100000"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_4", "--scale", "small"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_5", "--scale", "large"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_6", "--mu", "0.5"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_7", "--mu", "0.8"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_8", "--w", "2.5"],
    ["python3", "solver/Main_wally.py", "--exp_name", "scenario_9", "--w", "3"]
]

if __name__ == "__main__":
    for i, command in enumerate(Commands):

        print(f"====================================")
        print(f"===   Running Experiment {i+1}   ===")
        print(f"====================================")

        try:
            # Run the command and capture the output
            result = subprocess.run(command, capture_output=True, text=True, check=True)

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