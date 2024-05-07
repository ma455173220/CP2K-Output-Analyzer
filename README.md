# CP2K-Output-Analyzer
This Python script analyzes CP2K output files generated during structure optimization (GEO_OPT and CELL_OPT only) and provides useful insights into the optimization process. It was inspired by similar scripts used in VASP.

## Features
- Analyzes CP2K output files to extract optimization data
- Generates a CSV file containing optimization data
- Additional functionality to plot energy vs. optimization step for easy monitoring

## Usage
1. Clone the repository to your local machine.
2. Navigate to the directory containing your CP2K output file.
3. Run the script using Python 3: `python3 cp2k-output-analyse.py cp2k.out`. Replace `cp2k.out` with the name of your CP2K output file.
4. The script will generate a `cp2k_data.csv` file in the current directory.

## Output File Format
- **Column 1:** Optimization step number
- **Column 2:** Number of SCF steps used in optimization
- **Column 3:** Structure energy
- **Column 4:** Energy change
- **Columns 5-8:** Convergence parameters (YES indicates convergence)
- **Column 9:** Time taken for optimization

If "x" is prefixed before the STEP column, it indicates an increase in energy for that step. If "!" is prefixed before the SCF column, it means the CYCLE reached the maximum set SCF steps.

---

Example:

![Screenshot](https://github.com/ma455173220/CP2K-Output-Analyzer/assets/42956329/c7fd90de-7b32-4b56-b007-e91b238fa0db)

![Plot](https://github.com/ma455173220/CP2K-Output-Analyzer/assets/42956329/de0f19b5-a187-4ee8-8aa4-a7b46cc3f574)

---

Feel free to optimize the script further!

---

### Note
This script is primarily intended for personal use and may require adjustments based on your specific CP2K output format and optimization settings.
