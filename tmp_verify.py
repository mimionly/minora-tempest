import importlib
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(r"c:\sahyadri")
sys.path.insert(0, str(root))

demo_runner = importlib.import_module("demo_runner")
import demo_runner_osm

with patch("demo_runner_osm.main", autospec=True) as mocked_main:
    demo_runner.main()

print("called", mocked_main.call_count)
