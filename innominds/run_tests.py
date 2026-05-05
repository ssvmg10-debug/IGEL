import subprocess
import os
from datetime import datetime
import os

os.environ["PYTHONFAULTHANDLER"] = "0"

project_root = os.path.dirname(os.path.abspath(__file__))
os.environ["PYTHONPATH"] = project_root

timestamp = datetime.now().strftime("%d%b%Y-%H%M")

results_dir = f"reports/allure-results-{timestamp}"
report_dir = f"reports/allure-report-{timestamp}"

# Run pytest
subprocess.run([
    "pytest",
    "tests/CIC/test_QCL_5022_04.py",
    "--alluredir",
    results_dir
], env=os.environ)

try:
# Generate report
    subprocess.run(f"allure generate {results_dir} -o {report_dir} --clean", shell=True)

# Open report

    subprocess.run(f"allure open {report_dir}", shell=True)
except KeyboardInterrupt:
    print("\nAllure server stopped.")
