from __future__ import annotations
from typing import Dict

# Map friendly names to colorama Fore codes
def get_color(name: str) -> str:
    try:
        import colorama as c
    except Exception:
        class Dummy:
            class Fore:
                RESET = ""
        c = Dummy()
    table: Dict[str, str] = {
        "BLACK": getattr(__import__("colorama").Fore, "BLACK", ""),
        "RED": getattr(__import__("colorama").Fore, "RED", ""),
        "GREEN": getattr(__import__("colorama").Fore, "GREEN", ""),
        "YELLOW": getattr(__import__("colorama").Fore, "YELLOW", ""),
        "BLUE": getattr(__import__("colorama").Fore, "BLUE", ""),
        "MAGENTA": getattr(__import__("colorama").Fore, "MAGENTA", ""),
        "CYAN": getattr(__import__("colorama").Fore, "CYAN", ""),
        "WHITE": getattr(__import__("colorama").Fore, "WHITE", ""),
        "RESET": getattr(__import__("colorama").Style, "RESET_ALL", ""),
    }
    return table.get(name.upper(), table["RESET"])

def list_supported_colors():
    return ["BLACK","RED","GREEN","YELLOW","BLUE","MAGENTA","CYAN","WHITE"]
