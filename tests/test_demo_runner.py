import importlib
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_demo_runner_uses_osm_demo_entrypoint():
    demo_runner = importlib.import_module("demo_runner")

    with patch("demo_runner.demo_runner_osm.main", autospec=True) as mocked_main:
        demo_runner.main()

    mocked_main.assert_called_once_with()
