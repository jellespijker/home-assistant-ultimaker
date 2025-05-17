"""Script to run the example test."""
import pytest
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Run the example test
if __name__ == "__main__":
    print("Running example test...")
    pytest.main(["-xvs", "tests/test_sensor.py::test_run_example"])
    print("Example test completed.")