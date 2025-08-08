from __future__ import annotations
import json
import platform
from pathlib import Path
from typing import Any, Dict

def get_blush_paths() -> Dict[str, Path]:
    system = platform.system()
    if system == "Windows":
        root = Path.home() / "AppData" / "Local" / ".blush"
    elif system in ["Linux", "Darwin"]:
        root = Path.home() / ".blush"
    else:
        raise Exception("Unsupported OS")
    return {
        "root": root,
        "temp": root / "temp",
        "config": root / "config.json",
        "inbox": root / "inbox",
    }

def ensure_config(cfg_path: Path):
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if not cfg_path.exists():
        data = {
            "blush_color": "MAGENTA",
            "success_color": "GREEN",
            "warning_color": "YELLOW",
            "error_color": "RED",
            "transfer": {
                "ask_on_receive": False,
                "auto_accept_from": [],  # list of device_id
                "last_selected_host": None,  # {"device_id":..., "name":..., "ip":..., "port":...}
            },
            "host": {
                "enabled": False,
                "port": None,
                "device_id": None,
                "pair_code": None,
                "paired_devices": [],  # list of device_id
            }
        }
        cfg_path.write_text(json.dumps(data, indent=2))

def load_full_config(cfg_path: Path) -> Dict[str, Any]:
    ensure_config(cfg_path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_full_config(cfg_path: Path, data: Dict[str, Any]):
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_config() -> Dict[str, Any]:
    paths = get_blush_paths()
    return load_full_config(paths["config"])
