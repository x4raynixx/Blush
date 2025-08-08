import os
import subprocess
import sys
from pathlib import Path
import platform
from utils import fetcher
import shlex
import json
import time

importlist = ["colorama", "pathlib", "wcwidth"]

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_blush_path():
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("USERPROFILE")) / "AppData" / "Local" / ".blush"
    elif system in ["Linux", "Darwin"]:
        return Path(os.environ.get("HOME")) / ".blush"
    else:
        raise Exception("Unsupported OS")

BLUSH_PATH = get_blush_path()
TEMP_PATH = BLUSH_PATH / "temp"
BLUSH_CONFIG_PATH = BLUSH_PATH / "config.json"
RESTART_SCRIPT = TEMP_PATH / ("restart.bat" if os.name == "nt" else "restart.sh")

def load_config(config_type):
    if BLUSH_CONFIG_PATH.exists():
        try:
            with open(BLUSH_CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config.get(config_type, "MAGENTA")
        except:
            pass
    return "MAGENTA"

def get_prefixes():
    import wcwidth
    col = globals().get("colorama")
    def pad_emoji_prefix(prefix, width=2):
        current_width = sum(wcwidth.wcwidth(c) or 0 for c in prefix)
        return prefix + " " * max(0, width - current_width)
    return {
        "blush_prefix": pad_emoji_prefix("[🍀]"),
        "success_prefix": pad_emoji_prefix("[✓]" + col.Fore.GREEN),
        "warning_prefix": pad_emoji_prefix("[!]" + col.Fore.YELLOW),
        "error_prefix": pad_emoji_prefix("[✗]" + col.Fore.RED),
        "think_prefix": pad_emoji_prefix("[⏳]"),
        "cin_prefix": pad_emoji_prefix("[»]")
    }

def delete_restart_script():
    if RESTART_SCRIPT.exists():
        RESTART_SCRIPT.unlink()

def prepare():
    os.makedirs(TEMP_PATH, exist_ok=True)
    delete_restart_script()
    missing_modules = []
    for module in importlist:
        try:
            globals()[module] = __import__(module)
        except ImportError:
            missing_modules.append(module)
    if missing_modules:
        print("[*] Missing modules: " + ", ".join(missing_modules))
        for module in missing_modules:
            print(f"[*] Installing {module}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", module],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                globals()[module] = __import__(module)
                print(f"[+] {module} installed")
            except:
                print(f"[!] Failed to install {module}.")
                sys.exit(1)
        restart_content = (
            f"@echo off\ntimeout /t 1 >nul\n\"{sys.executable}\" \"{__file__}\"\ndel \"%~f0\"\n"
            if os.name == "nt" else
            f"#!/bin/bash\nsleep 1\n\"{sys.executable}\" \"{__file__}\"\nrm -- \"$0\"\n"
        )
        RESTART_SCRIPT.write_text(restart_content)
        if os.name != "nt":
            RESTART_SCRIPT.chmod(0o755)
            subprocess.Popen(["bash", str(RESTART_SCRIPT)])
        else:
            os.startfile(RESTART_SCRIPT)
        sys.exit(0)
    col = globals().get("colorama")
    if not BLUSH_PATH.exists():
        print(col.Fore.YELLOW + "[⏳] Preparing")
        os.makedirs(BLUSH_PATH, exist_ok=True)
        BLUSH_CONFIG_PATH.write_text('{"blush_color": "MAGENTA"}')
        clear_terminal()
    if not BLUSH_CONFIG_PATH.exists():
        BLUSH_CONFIG_PATH.write_text('{"blush_color": "MAGENTA"}')

load_banner = r"""$$$$$$$\  $$\       $$\   $$\  $$$$$$\  $$\   $$\
$$  __$$\ $$ |      $$ |  $$ |$$  __$$\ $$ |  $$ |
$$ |  $$ |$$ |      $$ |  $$ |$$ |  $$ |$$ |  $$ |
$$ |  $$ |$$ |      $$ |  $$ |$$ |  $$ |$$ |  $$ |
$$ |  $$ |$$ |      $$ |  $$ |$$$$$$$  |$$$$$$$$ |
$$ |  $$ |$$ |      $$ |  $$ |$$  __$$< $$  __$$ |
$$ |  $$ |$$$$$$$$\ \$$$$$$  |$$ |  $$ |$$ |  $$ |
\__|  \__|\________| \______/ \__|  \__|\__|  \__|"""

def display_banner():
    col = globals().get("colorama")
    blush_color = get_blush_color()
    prints = [
        blush_color + load_banner + col.Style.RESET_ALL,
        "",
        col.Fore.GREEN + f"{success_prefix} All modules loaded" + col.Style.RESET_ALL,
        col.Fore.BLUE + f"{blush_prefix} Blush - Fast & Optimized Shell" + col.Style.RESET_ALL,
        ""
    ]
    for p in prints:
        print(p)

def input_loop():
    while True:
        try:
            user_input = input(get_blush_color() + f"{cin_prefix} ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print(f"{success_prefix} Goodbye!")
                break
            execute_command(user_input)
        except KeyboardInterrupt:
            print(f"\n{warning_prefix} use 'exit' or 'quit' to leave")
            continue
        except EOFError:
            break

def execute_command(cmd):
    col = globals().get("colorama")
    if cmd.startswith("!"):
        mod_cmd = cmd[1:].strip()
        if not mod_cmd:
            print(f"{error_prefix} no command provided after '!'")
            return
        result = subprocess.run(mod_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            if result.stdout.strip():
                print(result.stdout.rstrip())
        else:
            print(f"{error_prefix} {result.stderr.strip()}")
        return
    try:
        args = shlex.split(cmd)
    except ValueError as e:
        print(f"{error_prefix} invalid command syntax: {e}")
        return
    if not args:
        return
    command = args[0].lower()
    arguments = args[1:]
    if not fetcher.ifexists(command):
        print(col.Fore.YELLOW + f"{warning_prefix} Command '{command}' not found")
        suggestions = fetcher.get_similar_commands(command)
        if suggestions:
            print(col.Fore.YELLOW + f"{warning_prefix} Did you mean: {', '.join(suggestions)}?")
        return
    try:
        response = fetcher.execute([command] + arguments)
        handle_response(response)
    except Exception as e:
        print(f"{error_prefix} Error executing command: {str(e)}")

def handle_response(response):
    col = globals().get("colorama")
    if response == "$C_CLEAR":
        clear_terminal()
    elif response == "$C_EXIT":
        sys.exit(0)
    elif isinstance(response, list):
        if len(response) == 1 and response[0] == "SUCCESS":
            print(f"{success_prefix} Done")
        elif len(response) >= 2 and response[0] == "ERROR":
            print(f"{error_prefix} {response[1]}")
        elif len(response) >= 2 and response[0] == "WARNING":
            print(f"{warning_prefix} {response[1]}")
        elif len(response) >= 2 and response[0] == "INFO":
            print(f"{blush_prefix} {response[1]}")
    elif isinstance(response, str) and response:
        print(f"{success_prefix} {response}")

def get_blush_color():
    col = globals().get("colorama")
    if col is None:
        return ""
    color_name = load_config("blush_color")
    return getattr(col.Fore, color_name, col.Fore.MAGENTA)

def main():
    prepare()
    col = globals().get("colorama")
    col.init(autoreset=True)
    prefixes = get_prefixes()
    global blush_prefix, success_prefix, warning_prefix, error_prefix, think_prefix, cin_prefix
    blush_prefix = prefixes["blush_prefix"]
    success_prefix = prefixes["success_prefix"]
    warning_prefix = prefixes["warning_prefix"]
    error_prefix = prefixes["error_prefix"]
    think_prefix = prefixes["think_prefix"]
    cin_prefix = prefixes["cin_prefix"]
    display_banner()
    input_loop()

if __name__ == "__main__":
    main()
