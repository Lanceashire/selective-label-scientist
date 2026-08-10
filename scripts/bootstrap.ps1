$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests_agent -p "test_*.py" -v
