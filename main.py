import os
import subprocess
import sys
from pathlib import Path
import platform
from utils import fetcher
import shlex
import subprocess

importlist = [
    "colorama",
    "pathlib",
    "wcwidth"
]

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_blush_path():
    system = platform.system()
    if system == "Windows":
        user = os.environ.get("USERPROFILE")
        return Path(user) / "AppData" / "Local" / ".blush"
    elif system == "Linux" or system == "Darwin":
        user = os.environ.get("HOME")
        return Path(user) / ".blush"
    else:
        raise Exception("Unsupported OS")

BLUSH_PATH = get_blush_path()
TEMP_PATH = BLUSH_PATH / "temp"
BLUSH_CONFIG_PATH = BLUSH_PATH / "config.json"
RESTART_SCRIPT = TEMP_PATH / ("restart.bat" if os.name == "nt" else "restart.sh")

def loadConfig(type):
    if type == "blush_color":
        return "MAGENTA"

def get_prefixes():
    import wcwidth
    col = globals().get("colorama")
    def pad_emoji_prefix(prefix, width=1):
        current_width = sum(wcwidth.wcwidth(c) for c in prefix)
        return prefix + " " * max(0, width - current_width)
    return {
        "blush_prefix": pad_emoji_prefix("[🍀]"),
        "success_prefix": pad_emoji_prefix("[»]" + col.Fore.GREEN),
        "warning_prefix": pad_emoji_prefix("[ ]" + col.Fore.YELLOW),
        "error_prefix": pad_emoji_prefix("[]" + col.Fore.RED),
        "think_prefix": pad_emoji_prefix("[⏳]"),
        "cin_prefix": pad_emoji_prefix("[»]")
    }

def delete_restart_script_if_exists():
    if RESTART_SCRIPT.exists():
        RESTART_SCRIPT.unlink()

def prepare():
    os.makedirs(TEMP_PATH, exist_ok=True)
    delete_restart_script_if_exists()

    missing_modules = []

    for module in importlist:
        try:
            globals()[module] = __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"[*] Missing modules detected: {', '.join(missing_modules)}")
        for module in missing_modules:
            print(f"[*] Installing {module}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", module],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                globals()[module] = __import__(module)
                print(f"[+] {module} installed")
            except Exception:
                print(f"[!] Failed to install {module}.")
                sys.exit(1)

        if os.name == "nt":
            RESTART_SCRIPT.write_text(
                f"@echo off\n"
                f"timeout /t 1 >nul\n"
                f'"{sys.executable}" "{__file__}"\n'
                f"del \"%~f0\"\n"
            )
            os.startfile(RESTART_SCRIPT)
        else:
            RESTART_SCRIPT.write_text(
                f"#!/bin/bash\n"
                f"sleep 1\n"
                f'"{sys.executable}" "{__file__}"\n'
                f"rm -- \"$0\"\n"
            )
            RESTART_SCRIPT.chmod(0o755)
            subprocess.Popen(["bash", str(RESTART_SCRIPT)])

        sys.exit(0)

    col = globals().get("colorama")

    if not BLUSH_PATH.exists():
        print(col.Fore.YELLOW + f"[⏳] Preparing")
        os.makedirs(BLUSH_PATH, exist_ok=True)
        BLUSH_CONFIG_PATH.write_text('{}')
        clear_terminal()

    if not BLUSH_CONFIG_PATH.exists():
        BLUSH_CONFIG_PATH.write_text('{}')
        clear_terminal()

load = r"""
$$$$$$$\  $$\      $$\   $$\  $$$$$$\  $$\   $$\ 
$$  __$$\ $$ |     $$ |  $$ |$$  __$$\ $$ |  $$ |
$$ |  $$ |$$ |     $$ |  $$ |$$ /  \__|$$ |  $$ |
$$$$$$$\ |$$ |     $$ |  $$ |\$$$$$$\  $$$$$$$$ |
$$  __$$\ $$ |     $$ |  $$ | \____$$\ $$  __$$ |
$$ |  $$ |$$ |     $$ |  $$ |$$\   $$ |$$ |  $$ |
$$$$$$$  |$$$$$$$$\$$$$$$  |\$$$$$$  |$$ |  $$ |
\_______/ \________|\______/  \______/ \__|  \__|
"""

def lod():
    col = globals().get("colorama")
    blush_color = get_blush_color()
    prints = [
        blush_color + load + col.Style.RESET_ALL,
        "",
        col.Fore.GREEN + f"{success_prefix} All modules up to date" + col.Style.RESET_ALL,
        col.Fore.BLUE + f"{blush_prefix} Blush - A Fast, And Optimized Shell" + col.Style.RESET_ALL,
        ""
    ]
    for p in prints:
        print(p)

def doinput():
    while True:
        try:
            current_input = input(get_blush_color() + f"{cin_prefix} ")
            if current_input == "":
                continue
            execute(current_input)
        except KeyboardInterrupt:
            break

def execute(cmd):
    if cmd and cmd[0] == "!":
        mod_cmd = cmd[1:]  # Usuń pierwszy znak '!'
        args = shlex.split(mod_cmd)  # Rozbij na listę (np. 'ls -la' -> ['ls', '-la'])
        
        if not args:
            return f"${error_prefix} No command provided!"

        result = subprocess.run(mod_cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            return print(result.stdout)
        else:
            return f"${error_prefix} {result.stderr.strip()}"
        
    col = globals().get("colorama")

    args = shlex.split(cmd)
    if not args:
        return

    command = args[0]
    arguments = args[1:] if len(args) > 1 else []

    checker = fetcher.ifexists(command)
    if not checker:
        print(f"{warning_prefix} Error: Command not found")
        return
    
    full_args = [command] + arguments

    response = fetcher.execute(full_args)

    if len(response) == 1:
        return print(f"{success_prefix} Done")
    if len(response) >= 2:
        col = globals().get("colorama")
        col.init()
        return print(error_prefix + f" Failed: {response[1]}")
    
    if response == "$C_CLEAR":
        clear_terminal()
    elif response != "$C_CLEAR":
        print(success_prefix + " " + response)

def get_blush_color():
    col = globals().get("colorama")
    if col is None:
        return "NO_INIT"
    color_name = loadConfig("blush_color")
    return getattr(col.Fore, color_name)

def main():
    prepare()
    col = globals().get("colorama")
    col.init()

    prefixes = get_prefixes()
    global blush_prefix, success_prefix, warning_prefix, error_prefix, think_prefix, cin_prefix
    blush_prefix = prefixes["blush_prefix"]
    success_prefix = prefixes["success_prefix"]
    warning_prefix = prefixes["warning_prefix"]
    error_prefix = prefixes["error_prefix"]
    think_prefix = prefixes["think_prefix"]
    cin_prefix = prefixes["cin_prefix"]

    lod()
    doinput()

if __name__ == "__main__":
    main()