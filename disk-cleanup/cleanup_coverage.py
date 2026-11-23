"""Line coverage for disk-cleanup.sh (bash_coverage.py, copied from the
infrastructure repo's scripts/)."""
from pathlib import Path

from bash_coverage import Coverage

cov = Coverage(Path(__file__).resolve().parent, ("disk-cleanup.sh",))
run = cov.run
