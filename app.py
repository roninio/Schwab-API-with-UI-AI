"""Web UI: launches the NiceGUI app.

Run:  python app.py
Same as: python nicegui_app.py
"""
from pathlib import Path
import runpy

if __name__ in {"__main__", "__mp_main__"}:
    runpy.run_path(str(Path(__file__).resolve().parent / "nicegui_app.py"), run_name="__main__")
