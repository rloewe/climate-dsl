import sys
import os
import subprocess

"""
Runs all pyOM tests back to back and compares the results with the legacy backend.
Expects path to the compiled Fortran library as first command line argument.
"""

try:
    fortran_path = sys.argv[1]
except IndexError:
    raise RuntimeError("First command line argument must be path to Fortran library")

success, fail = "passed", "failed"
if sys.stdout.isatty():
    success = "\x1b[{}m{}\x1b[0m".format("32",success)
    fail = "\x1b[{}m{}\x1b[0m".format("31",fail)

for f in os.listdir("./pyom"):
    if f.endswith("_test.py"):
        sys.stdout.write("Running test {} ... ".format(f))
        sys.stdout.flush()
        try: # must run each test in its own Python subprocess to reload the Fortran library
	        output = subprocess.check_output(["python", os.path.join("./pyom", f), fortran_path],
                                              stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            sys.stdout.write(fail + "\n\n")
            print(e.output)
            continue
        sys.stdout.write(success + "\n")
