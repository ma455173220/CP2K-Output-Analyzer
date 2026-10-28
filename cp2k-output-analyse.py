#!/usr/bin/env python3

import os
import sys
import re
import datetime

class CP2KOutputAnalyzer:
    def __init__(self, output_file, plot=None):
        # Initialize the CP2KOutputAnalyzer object with the output file
        # plot: True (--plot), False (--no-plot) or None (ask if stdin is a terminal)
        self.output_file = output_file
        self.plot = plot
        self.static_parameters = {}  # Dictionary to store static parameters from the output file
        self.parsed_data = {}  # Dictionary to store parsed data from the output file
        self.optimization_step_data = []  # List to store optimization step data

    def print_usage(self):
        # Print the usage information for the script
        print("""
**********************************************
      *** The format of the script: ***
python3 cp2k-output-analyse.py OUTPUT_FILE.out [--plot | --no-plot]
  (without --plot/--no-plot you are asked, if
   the script runs in a terminal)
**********************************************
        """)

    # Section titles: each optimization step, the end of the optimization, the L-BFGS summary
    SECTION_PATTERN = re.compile(r'OPTIMIZATION STEP:\s+\d+'
                                 r'|GEOMETRY OPTIMIZATION COMPLETED'
                                 r'|Specific L-BFGS convergence criteria')
    # Extra CELL_OPT quantities (old "Internal Pressure [bar] = x" and new "OPT| Internal pressure [bar]  x" formats)
    CELL_PATTERNS = [
        ('p_internal', re.compile(r'Internal pressure \[bar\]', re.IGNORECASE)),
        ('p_deviation', re.compile(r'Pressure deviation \[bar\]', re.IGNORECASE)),
        ('p_converged', re.compile(r'Conv\. for\s+PRESSURE|Pressure is converged', re.IGNORECASE)),
        ('volume', re.compile(r'(?<!_)\bCELL\| Volume \[angstrom\^3\]', re.IGNORECASE)),
    ]
    CELL_LENGTH = re.compile(r'(?<!_)\bCELL\| Vector ([abc]) \[angstrom\].*\|[abc]\|\s*=\s*([-+0-9.Ee]+)', re.IGNORECASE)

    def scan_output(self):
        """
        Single streaming pass over the CP2K output file (constant memory):
          * static parameters (run type, EPS_SCF, optimizer, convergence limits, start/end time)
          * the file split into sections at "OPTIMIZATION STEP: n", "GEOMETRY OPTIMIZATION COMPLETED"
            and "Specific L-BFGS convergence criteria"; the data of each section is extracted as it is read.
        Equivalent to reading the whole file and splitting it with re.split on the section titles.
        """
        static_parameters = {}
        # Default values for static parameters
        static_parameters['SCF_OPTIMIZER'] = "DIAGONALIZATION"
        static_parameters['OUTER_SCF_CHECK'] = "FALSE"
        self._finders = {'OT': True, 'GEO_OPTIMIZER': True, 'MAX_D': True, 'RMS_D': True, 'MAX_F': True, 'RMS_F': True}
        self.static_parameters = static_parameters
        sections = {}        # title -> step data (a repeated title replaces the data but keeps its position)
        current = None
        self._program_ended = False

        with open(self.output_file, 'r') as f:
            for line in f:
                self._static_line(line)
                if "PROGRAM ENDED AT" in line:
                    self._program_ended = True
                rest = line
                while True:
                    m = self.SECTION_PATTERN.search(rest)
                    if not m:
                        break
                    if current is not None:
                        self._section_line(current, rest[:m.start()])
                    title = m.group(0).strip()
                    current = self._new_section(title)
                    sections[title] = current
                    rest = rest[m.end():]
                if current is not None:
                    self._section_line(current, rest)

        # Handle the removal of unnecessary sections
        if "Specific L-BFGS convergence criteria" in sections.keys():
            the_second_to_last_key = list(sections.keys())[-2]
            sections.pop(the_second_to_last_key)
        if not self._program_ended:
            last_key = list(sections.keys())[-1]
            sections.pop(last_key)
        self.parsed_data = sections

    def _static_line(self, line):
        static_parameters = self.static_parameters
        finders = self._finders
        if "PROGRAM STARTED AT" in line:
            starttime = line.split('AT')[-1].strip()
            static_parameters['starttime'] = starttime
        elif "PROGRAM ENDED AT" in line:
            static_parameters['endtime'] = line.split('AT')[-1].strip()
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
            if finders['GEO_OPTIMIZER']:
                GEO_OPTIMIZER = str(line.replace("=", " ").split()[-1].strip())
                static_parameters['GEO_OPTIMIZER'] = GEO_OPTIMIZER
                finders['GEO_OPTIMIZER'] = False
        elif " OT " in line:
            if finders['OT']:
                static_parameters['SCF_OPTIMIZER'] = "OT"
                finders['OT'] = False
        elif any(term in line for term in ["Conv. limit for step size", "Convergence limit for maximum step size"]):
            if finders['MAX_D']:
                static_parameters['MAX_D'] = float(line.replace("=", " ").split()[-1].strip())
                finders['MAX_D'] = False
        elif any(term in line for term in ["Conv. limit for RMS step", "Convergence limit for RMS step size"]):
            if finders['RMS_D']:
                static_parameters['RMS_D'] = float(line.replace("=", " ").split()[-1].strip())
                finders['RMS_D'] = False
        elif any(term in line for term in ["Conv. limit for gradients", "Convergence limit for maximum gradient"]):
            if finders['MAX_F']:
                static_parameters['MAX_F'] = float(line.replace("=", " ").split()[-1].strip())
                finders['MAX_F'] = False
        elif any(term in line for term in ["Conv. limit for RMS grad", "Convergence limit for RMS gradient"]):
            if finders['RMS_F']:
                static_parameters['RMS_F'] = float(line.replace("=", " ").split()[-1].strip())
                finders['RMS_F'] = False

    @staticmethod
    def _new_section(title):
        optimization_step_data_dir = {}
        optimization_step_data_dir['scf_convergence'] = "YES"
        if "GEOMETRY OPTIMIZATION COMPLETED" in title or "Specific L-BFGS convergence criteria" in title:
            optimization_step_data_dir['step'] = "Final"
        else:
            optimization_step_data_dir['step'] = int(title.split(':')[-1].strip())
        return optimization_step_data_dir

    def _section_line(self, optimization_step_data_dir, line):
        # Extract relevant data for each optimization step (the convergence YES/NO flags are set in
        # finalize_steps, once all convergence limits are known)
        if any(term in line for term in ["ENERGY| Total FORCE_EVAL ( QS ) energy"]):
            if optimization_step_data_dir['step'] == "Final":
                TOTAL_ENERGY = float(line.replace("=", " ").split()[-1].strip())
                optimization_step_data_dir['energy'] = TOTAL_ENERGY
        elif any(term in line for term in ["SCF run NOT converged"]):
            optimization_step_data_dir['scf_convergence'] = "! NO"
        elif "*** SCF run converged in" in line:
            # e.g. "*** SCF run converged in    12 steps ***"
            optimization_step_data_dir['scf_steps'] = line.split()[-3]
        elif any(term in line for term in ["outer SCF loop converged in", "outer SCF loop FAILED to converge",
                                           "Leaving inner SCF loop after reaching"]):
            # e.g. "outer SCF loop converged in   3 iterations or   45 steps"
            #      "Leaving inner SCF loop after reaching    50 steps."
            optimization_step_data_dir['scf_steps'] = line.split()[-2]
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
            optimization_step_data_dir['MAX_D_value'] = float(line.replace("=", " ").split()[-1].strip())
        elif any(term in line for term in ["RMS step size   "]) and "limit" not in line:
            optimization_step_data_dir['RMS_D_value'] = float(line.replace("=", " ").split()[-1].strip())
        elif any(term in line for term in ["Max. gradient   ", "Maximum gradient   "]) and "limit" not in line:
            optimization_step_data_dir['MAX_F_value'] = float(line.replace("=", " ").split()[-1].strip())
        elif any(term in line for term in ["RMS gradient   "]) and "limit" not in line:
            optimization_step_data_dir['RMS_F_value'] = float(line.replace("=", " ").split()[-1].strip())
        elif any(term in line for term in ["Used time [s]", "Used time   "]):
            USEDTIME = line.replace("=", " ").split()[-1].strip()
            USEDTIME = round(float(USEDTIME))
            optimization_step_data_dir['used_time'] = USEDTIME

        # CELL_OPT: pressure, volume and cell lengths (only written for RUN_TYPE CELL_OPT)
        if "CELL|" in line or "RESSURE" in line.upper():
            for key, pattern in self.CELL_PATTERNS:
                if pattern.search(line):
                    optimization_step_data_dir[key] = line.replace("=", " ").split()[-1].strip()
            m = self.CELL_LENGTH.search(line)
            if m:
                optimization_step_data_dir['cell_' + m.group(1).lower()] = m.group(2)

    CELL_HEADER = " | P_INT [bar] | P_DEV [bar] | P_CONV | VOLUME [A^3] |   a [A]   |   b [A]   |   c [A]  "

    @staticmethod
    def cell_columns(step_data):
        """CELL_OPT columns: internal pressure, pressure deviation, pressure converged, volume, |a| |b| |c|."""
        def num(key, width, prec):
            try:
                return "%*.*f" % (width, prec, float(step_data[key]))
            except (KeyError, ValueError):
                return "%*s" % (width, "N/A")
        return " |%12s |%12s |%7s |%13s |%10s |%10s |%10s" % (
            num('p_internal', 12, 2), num('p_deviation', 12, 2),
            step_data.get('p_converged', "N/A"), num('volume', 13, 4),
            num('cell_a', 10, 5), num('cell_b', 10, 5), num('cell_c', 10, 5))

    def finalize_steps(self):
        # Convergence flags (value above the limit -> NO) and the list of step data, in file order
        optimization_step_data_list = []
        for step, optimization_step_data_dir in self.parsed_data.items():
            for name in ('MAX_D', 'RMS_D', 'MAX_F', 'RMS_F'):
                if name + '_value' in optimization_step_data_dir:
                    if optimization_step_data_dir[name + '_value'] > self.static_parameters[name]:
                        optimization_step_data_dir[name + '_CONVERGENCE'] = "NO"
                    else:
                        optimization_step_data_dir[name + '_CONVERGENCE'] = "YES"
            optimization_step_data_list.append(optimization_step_data_dir)

        # Store the extracted optimization step data in the object's attribute
        self.optimization_step_data = optimization_step_data_list

    def get_total_used_time(self):
        # Wall time between "PROGRAM STARTED AT" and "PROGRAM ENDED AT" if the job has finished,
        # otherwise the sum of the "Used time" of all optimization steps
        time_format = "%Y-%m-%d %H:%M:%S.%f"
        try:
            total_time = (datetime.datetime.strptime(self.static_parameters['endtime'], time_format)
                          - datetime.datetime.strptime(self.static_parameters['starttime'], time_format)).total_seconds()
        except (KeyError, ValueError):
            total_time = sum(item.get('used_time', 0) for item in self.optimization_step_data)
        return str(datetime.timedelta(seconds=round(total_time)))

    def write_data_to_file(self):
        # Write the extracted data to a CSV file
        output = self.output_file.split('.out')[0] + "__data.csv"
        # CELL_OPT runs get extra columns at the end of each row (GEO_OPT rows are unchanged)
        cell_opt = self.static_parameters.get('RUN_TYPE') == "CELL_OPT"
        with open(output, 'w') as f:
            f.write("# Job Starting Date: " + str(self.static_parameters['starttime']) \
                    + "\n# Total used time: " + self.get_total_used_time() \
                    + "\n# Directory: " + os.getcwd() \
                    + "\n# RUN_TYPE: " + str(self.static_parameters['RUN_TYPE']) \
                    + "\n# EPS_SCF: " + str(self.static_parameters['EPS_SCF']) \
                    + "\n# MAX_SCF: " + str(self.static_parameters['MAX_SCF']) \
                    + "\n# SCF_OPTIMIZER: " + str(self.static_parameters['SCF_OPTIMIZER']) \
                    + "\n# OUTER_SCF: " + str(self.static_parameters['OUTER_SCF_CHECK']) \
                    + "\n# GEO_OPTIMIZER: " + str(self.static_parameters['GEO_OPTIMIZER']) \
                    + "\n# STEP | SCF |    E [a.u.]    |  Delta E  | M_D(" + f"{self.static_parameters['MAX_D']:.4f}" + ") | R_D(" + f"{self.static_parameters['RMS_D']:.4f}" + ") | M_F(" + f"{self.static_parameters['MAX_F']:.5f}" + ") | R_F(" + f"{self.static_parameters['RMS_F']:.4f}" + ") | TIME [s] | SCF_STEPS"
                    + (self.CELL_HEADER if cell_opt else "") + "\n")

            for step_data in self.optimization_step_data:
                if step_data['step'] == "Final":
                    # Write data for the final step
                    line = "%6s |%4s |%15.8f |%7s    |%8s     |%8s     |%9s     |%8s     |%8s |%9s\n" % (
                        step_data['step'],
                        str(step_data['scf_convergence']),
                        step_data['energy'],
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        str(step_data.get('scf_steps', "N/A"))
                    )
                else:
                    # Format the line for non-"Final" steps
                    # "Decrease in energy" is only printed by some optimizers (e.g. BFGS, not L-BFGS/CG);
                    # if it is missing, derive it from the sign of the energy change
                    energy_decrease = step_data.get('energy_decrease')
                    if energy_decrease is None:
                        energy_decrease = "YES" if float(step_data.get('delta_E', 0)) <= 0 else "NO"
                    if energy_decrease.upper() == "YES":
                        line = "%6s |%4s |%15.8f |%10s |%8.5f %3s |%8.5f %3s |%9.6f %3s |%8.5f %3s |%8s |%9s\n" % (
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
                            str(step_data['used_time']),          # Time used for this step
                            str(step_data.get('scf_steps', "N/A"))  # SCF steps of this step
                        )
                    else:
                        line = "%1s %4s |%4s |%15.8f |%10s |%8.5f %3s |%8.5f %3s |%9.6f %3s |%8.5f %3s |%8s |%9s\n" % (
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
                            str(step_data['used_time']),          # Time used for this step
                            str(step_data.get('scf_steps', "N/A"))  # SCF steps of this step
                        )

                if cell_opt:
                    line = line[:-1] + self.cell_columns(step_data) + "\n"
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
            self.scan_output()
            self.finalize_steps()
            self.write_data_to_file()
        except FileNotFoundError:
            # Handle the case where the output file is not found
            print(f"Error: File '{self.output_file}' not found.")
            sys.exit(1)
        print("=======================================")
        if self.plot is None:
            # no --plot/--no-plot: ask, but only when someone can answer (stdin is a terminal)
            if sys.stdin.isatty():
                print("Do you want to plot cycle vs. energy?\n(y/n)")
                self.plot = input().lower() == "y"
            else:
                self.plot = False
        if self.plot:
            self.plot_step_vs_energy()
        print("Done!")
        print("=======================================")

if __name__ == "__main__":
    # Entry point of the script
    plot = None
    if "--plot" in sys.argv[1:]:
        plot = True
    if "--no-plot" in sys.argv[1:]:
        plot = False
    files = [a for a in sys.argv[1:] if a not in ("--plot", "--no-plot")]
    if len(files) < 1:
        # If no output file is provided, print an error and usage instructions
        print("\033[31mERROR:\033[0m Missing file operand! Please identify the name of OUTPUT_FILE.out")
        CP2KOutputAnalyzer('').print_usage()
        sys.exit(1)

    # Extract the output file from command line arguments
    output_file = files[0]

    # Create an instance of CP2KOutputAnalyzer and run the analysis
    analyzer = CP2KOutputAnalyzer(output_file, plot=plot)
    analyzer.analyze()
