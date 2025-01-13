#!/apps/python3/3.10.0/bin/python3

import os
import sys
import re

class CP2KOutputAnalyzer:
    def __init__(self, output_file):
        # Initialize the CP2KOutputAnalyzer object with the output file
        self.output_file = output_file
        self.static_parameters = {}  # Dictionary to store static parameters from the output file
        self.parsed_data = {}  # Dictionary to store parsed data from the output file
        self.optimization_step_data = []  # List to store optimization step data

    def print_usage(self):
        # Print the usage information for the script
        print("""
**********************************************
      *** The format of the script: ***
python3 cp2k-output-analyse.py OUTPUT_FILE.out
**********************************************
        """)

    def parse_cp2k_output(self):
        """
        Parses a CP2K output file and extracts sections based on keywords.

        Returns:
            dict: A dictionary where keys are section titles and values are parsed results.
        """
        keywords = [
            r'OPTIMIZATION STEP:\s+\d+',  # Matches each optimization step
            r'GEOMETRY OPTIMIZATION COMPLETED',  # Matches the completion of geometry optimization
            r'Specific L-BFGS convergence criteria'  # Matches specific convergence criteria using L-BFGS
        ]
        # Read the entire content of the output file
        with open(self.output_file, 'r') as f:
            content = f.read()
            backup_content = content[:]  # Make a backup copy of the content

        # Split the content based on the keywords defined
        pattern = r'|'.join(keywords)
        sections = re.split(f'({pattern})', content)
        step_data = {}

        # Iterate over the sections to extract titles and content
        for i in range(1, len(sections), 2):
            title = sections[i].strip()
            content = sections[i + 1] if i + 1 < len(sections) else ""
            step_data[title] = content

        # Handle the removal of unnecessary sections
        if "Specific L-BFGS convergence criteria" in step_data.keys():
            the_second_to_last_key = list(step_data.keys())[-2]
            step_data.pop(the_second_to_last_key)
        if "PROGRAM ENDED AT" not in backup_content:
            last_key = list(step_data.keys())[-1]
            step_data.pop(last_key)

        # Store the parsed data in the object's attribute
        self.parsed_data = step_data

    def extract_static_parameters(self):
        """
        Extracts static parameters from a CP2K output file.

        Returns:
            dict: A dictionary containing extracted static parameters.
        """
        static_parameters = {}
        # Default values for static parameters
        static_parameters['SCF_OPTIMIZER'] = "DIAGONALIZATION"
        static_parameters['OUTER_SCF_CHECK'] = "FALSE"
        OT_CHECK = "TRUE"
        GEO_OPTIMIZER_FINDER = "TRUE"
        MAX_D_threshold_FINDER = "TRUE"
        RMS_D_threshold_FINDER = "TRUE"
        MAX_F_threshold_FINDER = "TRUE"
        RMS_F_threshold_FINDER = "TRUE"

        # Read the output file line by line to extract static parameters
        with open(self.output_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if "PROGRAM STARTED AT" in line:
                    starttime = line.split('AT')[-1].strip()
                    static_parameters['starttime'] = starttime
                elif "Run type" in line:
                    RUN_TYPE = line.split()[-1]
                    # Only allow GEO_OPT and CELL_OPT run types
                    if RUN_TYPE != "GEO_OPT" and RUN_TYPE != "CELL_OPT":
                        print("\033[31mERROR:\033[0m This script can only be used for Geometry Optimization results!")
                        sys.exit()
                    static_parameters['RUN_TYPE'] = RUN_TYPE
                elif "eps_scf:" in line:
                    EPS_SCF = line.split(':')[-1].strip()
                    static_parameters['EPS_SCF'] = EPS_SCF
                elif "Outer loop SCF in use" in line:
                    static_parameters['OUTER_SCF_CHECK'] = "TRUE"
                elif "max_scf:" in line:
                    MAX_SCF = line.split(':')[-1].strip()
                    static_parameters['MAX_SCF'] = MAX_SCF
                elif any(term in line for term in ["Optimization method", "Optimization Method"]):
                    if GEO_OPTIMIZER_FINDER == "TRUE":
                        GEO_OPTIMIZER = str(line.replace("=", " ").split()[-1].strip())
                        static_parameters['GEO_OPTIMIZER'] = GEO_OPTIMIZER
                        GEO_OPTIMIZER_FINDER = "FALSE"
                elif " OT " in line:
                    if OT_CHECK == "TRUE":
                        static_parameters['SCF_OPTIMIZER'] = "OT"
                        OT_CHECK = "FALSE"
                elif any(term in line for term in ["Conv. limit for step size", "Convergence limit for maximum step size"]):
                    if MAX_D_threshold_FINDER == "TRUE":
                        MAX_D_threshold = line.replace("=", " ").split()[-1].strip()
                        static_parameters['MAX_D'] = float(MAX_D_threshold)
                        MAX_D_threshold_FINDER = "FALSE"
                elif any(term in line for term in ["Conv. limit for RMS step", "Convergence limit for RMS step size"]):
                    if RMS_D_threshold_FINDER == "TRUE":
                        RMS_D_threshold = line.replace("=", " ").split()[-1].strip()
                        static_parameters['RMS_D'] = float(RMS_D_threshold)
                        RMS_D_threshold_FINDER = "FALSE"
                elif any(term in line for term in ["Conv. limit for gradients", "Convergence limit for maximum gradient"]):
                    if MAX_F_threshold_FINDER == "TRUE":
                        MAX_F_threshold = line.replace("=", " ").split()[-1].strip()
                        static_parameters['MAX_F'] = float(MAX_F_threshold)
                        MAX_F_threshold_FINDER = "FALSE"
                elif any(term in line for term in ["Conv. limit for RMS grad", "Convergence limit for RMS gradient"]):
                    if RMS_F_threshold_FINDER == "TRUE":
                        RMS_F_threshold = line.replace("=", " ").split()[-1].strip()
                        static_parameters['RMS_F'] = float(RMS_F_threshold)
                        RMS_F_threshold_FINDER = "FALSE"

        # Store the extracted static parameters in the object's attribute
        self.static_parameters = static_parameters

    def extract_optimization_step_data(self):
        # Extracts data related to each optimization step
        optimization_step_data_list = []
        for step, data in self.parsed_data.items():
            optimization_step_data_dir = {}
            optimization_step_data_dir['scf_convergence'] = "YES"
            if "GEOMETRY OPTIMIZATION COMPLETED" in step or "Specific L-BFGS convergence criteria" in step:
                optimization_step_data_dir['step'] = "Final"
            else:
                STEP_NUMBER = int(step.split(':')[-1].strip())
                optimization_step_data_dir['step'] = STEP_NUMBER

            # Extract relevant data for each optimization step
            for line in data.splitlines():
                if any(term in line for term in ["ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]"]):
                    if optimization_step_data_dir['step'] == "Final":
                        TOTAL_ENERGY = float(line.replace("=", " ").split()[-1].strip())
                        optimization_step_data_dir['energy'] = TOTAL_ENERGY
                elif any(term in line for term in ["SCF run NOT converged"]):
                    optimization_step_data_dir['scf_convergence'] = "! NO"
                elif any(term in line for term in ["Total Energy      ", "Total energy [hartree]"]):
                    TOTAL_ENERGY = float(line.replace("=", " ").split()[-1].strip())
                    optimization_step_data_dir['energy'] = TOTAL_ENERGY
                elif any(term in line for term in ["Decrease in energy   "]):
                    ENERGY_CHANGE = line.replace("=", " ").split()[-1].strip()
                    optimization_step_data_dir['energy_decrease'] = ENERGY_CHANGE
                elif any(term in line for term in ["Real energy change   ", "Effective energy change [hartree]"]):
                    ENERGY_CHANGE_VALUE = float(line.replace("=", " ").split()[-1].strip())
                    ENERGY_CHANGE_VALUE = "{:.2e}".format(ENERGY_CHANGE_VALUE)
                    optimization_step_data_dir['delta_E'] = ENERGY_CHANGE_VALUE
                elif any(term in line for term in ["Max. step size   ", "Maximum step size   "]) and "limit" not in line:
                    MAX_D_VALUE = line.replace("=", " ").split()[-1].strip()
                    MAX_D_VALUE = float(MAX_D_VALUE)
                    optimization_step_data_dir['MAX_D_value'] = MAX_D_VALUE
                    if MAX_D_VALUE > self.static_parameters['MAX_D']:
                        optimization_step_data_dir['MAX_D_CONVERGENCE'] = "NO"
                    else:
                        optimization_step_data_dir['MAX_D_CONVERGENCE'] = "YES"
                elif any(term in line for term in ["RMS step size   "]) and "limit" not in line:
                    RMS_D_VALUE = line.replace("=", " ").split()[-1].strip()
                    RMS_D_VALUE = float(RMS_D_VALUE)
                    optimization_step_data_dir['RMS_D_value'] = RMS_D_VALUE
                    if RMS_D_VALUE > self.static_parameters['RMS_D']:
                        optimization_step_data_dir['RMS_D_CONVERGENCE'] = "NO"
                    else:
                        optimization_step_data_dir['RMS_D_CONVERGENCE'] = "YES"
                elif any(term in line for term in ["Max. gradient   ", "Maximum gradient   "]) and "limit" not in line:
                    MAX_F_VALUE = line.replace("=", " ").split()[-1].strip()
                    MAX_F_VALUE = float(MAX_F_VALUE)
                    optimization_step_data_dir['MAX_F_value'] = MAX_F_VALUE
                    if MAX_F_VALUE > self.static_parameters['MAX_F']:
                        optimization_step_data_dir['MAX_F_CONVERGENCE'] = "NO"
                    else:
                        optimization_step_data_dir['MAX_F_CONVERGENCE'] = "YES"
                elif any(term in line for term in ["RMS gradient   "]) and "limit" not in line:
                    RMS_F_VALUE = line.replace("=", " ").split()[-1].strip()
                    RMS_F_VALUE = float(RMS_F_VALUE)
                    optimization_step_data_dir['RMS_F_value'] = RMS_F_VALUE
                    if RMS_F_VALUE > self.static_parameters['RMS_F']:
                        optimization_step_data_dir['RMS_F_CONVERGENCE'] = "NO"
                    else:
                        optimization_step_data_dir['RMS_F_CONVERGENCE'] = "YES"
                elif any(term in line for term in ["Used time [s]", "Used time   "]):
                    USEDTIME = line.replace("=", " ").split()[-1].strip()
                    USEDTIME = round(float(USEDTIME))
                    optimization_step_data_dir['used_time'] = USEDTIME
            optimization_step_data_list.append(optimization_step_data_dir)

        # Store the extracted optimization step data in the object's attribute
        self.optimization_step_data = optimization_step_data_list

    def write_data_to_file(self):
        # Write the extracted data to a CSV file
        output = self.output_file.split('.out')[0] + "__data.csv"
        with open(output, 'w') as f:
            f.write("# Job Starting Date: " + str(self.static_parameters['starttime']) \
                    + "\n# Directory: " + os.getcwd() \
                    + "\n# RUN_TYPE: " + str(self.static_parameters['RUN_TYPE']) \
                    + "\n# EPS_SCF: " + str(self.static_parameters['EPS_SCF']) \
                    + "\n# MAX_SCF: " + str(self.static_parameters['MAX_SCF']) \
                    + "\n# SCF_OPTIMIZER: " + str(self.static_parameters['SCF_OPTIMIZER']) \
                    + "\n# OUTER_SCF: " + str(self.static_parameters['OUTER_SCF_CHECK']) \
                    + "\n# GEO_OPTIMIZER: " + str(self.static_parameters['GEO_OPTIMIZER']) \
                    + "\n# STEP | SCF |    E [a.u.]    |  Delta E  | M_D(" + f"{self.static_parameters['MAX_D']:.4f}" + ") | R_D(" + f"{self.static_parameters['RMS_D']:.4f}" + ") | M_F(" + f"{self.static_parameters['MAX_F']:.5f}" + ") | R_F(" + f"{self.static_parameters['RMS_F']:.4f}" + ") | TIME [s]" + "\n")

            for step_data in self.optimization_step_data:
                if step_data['step'] == "Final":
                    # Write data for the final step
                    line = "%6s |%4s |%15.8f |%7s    |%8s     |%8s     |%9s     |%8s     |%8s\n" % (
                        step_data['step'],
                        str(step_data['scf_convergence']),
                        step_data['energy'],
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A"
                    )
                else:
                    # Format the line for non-"Final" steps
                    if step_data['energy_decrease'] == "YES":
                        line = "%6s |%4s |%15.8f |%10s |%8.5f %3s |%8.5f %3s |%9.6f %3s |%8.5f %3s |%8s\n" % (
                            str(step_data['step']),               # Step number
                            str(step_data['scf_convergence']),    # SCF convergence status
                            float(step_data['energy']),           # Total energy
                            str(step_data['delta_E']),            # Change in energy
                            float(step_data['MAX_D_value']),      # Maximum displacement
                            str(step_data['MAX_D_CONVERGENCE']),  # Convergence status for maximum displacement
                            float(step_data['RMS_D_value']),      # RMS displacement
                            str(step_data['RMS_D_CONVERGENCE']),  # Convergence status for RMS displacement
                            float(step_data['MAX_F_value']),      # Maximum force
                            str(step_data['MAX_F_CONVERGENCE']),  # Convergence status for maximum force
                            float(step_data['RMS_F_value']),      # RMS force
                            str(step_data['RMS_F_CONVERGENCE']),  # Convergence status for RMS force
                            str(step_data['used_time'])           # Time used for this step
                        )
                    else:
                        line = "%1s %4s |%4s |%15.8f |%10s |%8.5f %3s |%8.5f %3s |%9.6f %3s |%8.5f %3s |%8s\n" % (
                            "↑",                                  # Indicator for energy increase
                            str(step_data['step']),               # Step number
                            str(step_data['scf_convergence']),    # SCF convergence status
                            float(step_data['energy']),           # Total energy
                            str(step_data['delta_E']),            # Change in energy
                            float(step_data['MAX_D_value']),      # Maximum displacement
                            str(step_data['MAX_D_CONVERGENCE']),  # Convergence status for maximum displacement
                            float(step_data['RMS_D_value']),      # RMS displacement
                            str(step_data['RMS_D_CONVERGENCE']),  # Convergence status for RMS displacement
                            float(step_data['MAX_F_value']),      # Maximum force
                            str(step_data['MAX_F_CONVERGENCE']),  # Convergence status for maximum force
                            float(step_data['RMS_F_value']),      # RMS force
                            str(step_data['RMS_F_CONVERGENCE']),  # Convergence status for RMS force
                            str(step_data['used_time'])           # Time used for this step
                        )

                # Write the formatted line to the file
                f.write(line)
            f.write("# Done!")

    def plot_step_vs_energy(self):
        # Plot the optimization step versus energy using matplotlib
        import math
        import matplotlib.pyplot as plt
        from matplotlib.pyplot import MultipleLocator

        # Prepare data for plotting
        steps = [item['step'] for item in self.optimization_step_data if item['step'] != "Final"]
        energies = [item['energy'] for item in self.optimization_step_data if item['step'] != "Final"]

        # Scatter plot of step versus energy
        plt.scatter(steps, energies, s=10)
        plt.xlabel("Step")
        plt.ylabel("Energy (a.u.)")

        # Set x-axis spacing based on the number of steps
        x_spacing = 5 * math.ceil(len(steps) / 50)
        x_major_locator = MultipleLocator(x_spacing)
        ax = plt.gca()
        ax.xaxis.set_major_locator(x_major_locator)
        plt.show()

    def analyze(self):
        # Main method to run the analysis process
        print("=======================================")
        print("In process...")
        print("...")
        try:
            # Run all the necessary methods to complete the analysis
            self.extract_static_parameters()
            self.parse_cp2k_output()
            self.extract_optimization_step_data()
            self.write_data_to_file()
        except FileNotFoundError:
            # Handle the case where the output file is not found
            print(f"Error: File '{self.output_file}' not found.")
            sys.exit(1)
        print("=======================================")
        print("Do you want to plot cycle vs. energy?\n(y/n)")
        plot_choice = input()
        if plot_choice.lower() == "y":
            self.plot_step_vs_energy()
        print("Done!")
        print("=======================================")

if __name__ == "__main__":
    # Entry point of the script
    if len(sys.argv) < 2:
        # If no output file is provided, print an error and usage instructions
        print("\033[31mERROR:\033[0m Missing file operand! Please identify the name of OUTPUT_FILE.out")
        CP2KOutputAnalyzer('').print_usage()
        sys.exit(1)

    # Extract the output file from command line arguments
    output_file = sys.argv[1]

    # Create an instance of CP2KOutputAnalyzer and run the analysis
    analyzer = CP2KOutputAnalyzer(output_file)
    analyzer.analyze()
