import os
import subprocess
import sys
from pathlib import Path
import platform
from utils import fetcher
import shlex
import json
import time

# auto-install list
importlist = ["colorama", "pathlib", "wcwidth", "prompt_toolkit"]

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

    def pad_display(text, width=2):
        w = sum(wcwidth.wcwidth(c) or 0 for c in text)
        return text + " " * max(0, width - w)

    def colorize(color, text):
        return color + text + col.Style.RESET_ALL

    base = {
        "blush": "[🍀]",
        "success": "[✓]",
        "warning": "[!]",
        "error": "[✗]",
        "think": "[⏳]",
        "cin": "[»]",
    }

    return {
        "blush_prefix": pad_display(base["blush"]),
        "success_prefix": colorize(col.Fore.GREEN, pad_display(base["success"])),
        "warning_prefix": colorize(col.Fore.YELLOW, pad_display(base["warning"])),
        "error_prefix": colorize(col.Fore.RED, pad_display(base["error"])),
        "think_prefix": pad_display(base["think"]),
        "cin_prefix": pad_display(base["cin"]),
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
    for line in load_banner.splitlines():
        print(blush_color + line + col.Style.RESET_ALL)
    print("")
    print(col.Fore.GREEN + f"{success_prefix}"+ col.Fore.GREEN + " All modules loaded" + col.Style.RESET_ALL)
    print(col.Fore.BLUE + f"{blush_prefix} Blush - Fast & Optimized Shell" + col.Style.RESET_ALL)
    print("")

# simple sentence-capitalizer per line
def _format_lines(text: str) -> str:
    lines = text.splitlines()
    out = []
    for ln in lines:
        if ln and ln[0].islower():
            out.append(ln[0].upper() + ln[1:])
        else:
            out.append(ln)
    return "\n".join(out)

# tab completion
def _build_flags_map():
    return {
        "ls": ["-a", "--all", "-l", "--long", "-h", "--human", "-R", "--recursive", "-1", "-t", "-S", "--include=", "--exclude="],
        "grep": ["-i", "-n", "-r", "-E"],
        "find": ["-name", "-type", "f", "d", "-maxdepth"],
        "cp": ["-r", "-n", "-u"],
        "mv": ["-n", "-f"],
        "rm": ["-r", "-f", "-i", "-v"],
        "chmod": ["-R"],
        "head": ["-n"],
        "tail": ["-n", "-f"],
        "du": ["--max-depth"],
        "tree": ["--include=", "--exclude=", "--max-depth="],
        "ping": ["-c"],
        "curl": ["-o"],
        "wget": [],
        "mkdir": ["-m"],
        "touch": ["-c", "-m"],
        "date": ["+%Y-%m-%d %H:%M:%S"],
        "history": ["-n", "-c"],
        "json": ["--get", "--set", "--pretty"],
        "replace": ["--regex", "--in-place"],
        "sort": ["-r", "-n", "-u"],
        "uniq": ["-c"],
        "split": ["-l"],
        "base64": ["encode", "decode"],
        "b64": ["encode", "decode"],
        "checksum": ["--algo", "md5", "sha1", "sha256"],
        "killall": [],
        "pkill": [],
        "zip": [],
        "unzip": [],
        "tar": [],
        "untar": [],
        "seq": [],
        "calc": [],
        "stat": [],
        "basename": [],
        "dirname": [],
        "free": [],
        "uptime": [],
        "hostname": [],
        "ip": [],
        "netstat": [],
        "dns": [],
        "nslookup": [],
        "alias": [],
        "unalias": [],
        "which": [],
        "export": [],
        "unset": [],
        "env": []
    }

def _iter_path_completions(prefix: str):
    base = prefix or ""
    if base.startswith(("'", '"')):
        base = base[1:]
    d = os.path.dirname(base) or "."
    partial = os.path.basename(base)
    try:
        for name in os.listdir(d):
            if name.startswith(partial):
                full = os.path.join(d, name)
                if os.path.isdir(full):
                    yield os.path.join(d, name) + os.sep
                else:
                    yield os.path.join(d, name)
    except Exception:
        return

def _get_alias_names():
    try:
        from utils.commands.cmd import get_aliases
        return list(get_aliases().keys())
    except Exception:
        return []

def _tokenize_for_complete(text: str):
    try:
        # keep an unfinished token at end
        lexer = shlex.shlex(text, posix=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
        ends_with_space = text.endswith(" ")
        return tokens, ends_with_space
    except Exception:
        parts = text.split()
        return parts, text.endswith(" ")

def input_loop():
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.completion import Completer, Completion

    class BlushCompleter(Completer):
        def __init__(self):
            self.flags = _build_flags_map()

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            tokens, ends_with_space = _tokenize_for_complete(text)
            prefix = document.get_word_before_cursor(WORD=True)
            cmds = fetcher.command_list[:]
            cmds += _get_alias_names()

            # first word -> command names
            if len(tokens) == 0 or (len(tokens) == 1 and not ends_with_space):
                for c in cmds:
                    if c.startswith(prefix):
                        yield Completion(c, start_position=-len(prefix))
                return

            # determine current command
            cmd = tokens[0].lower()
            is_flag_context = prefix.startswith("-")
            # offer flags for known commands
            if is_flag_context:
                for fl in self.flags.get(cmd, []):
                    if fl.startswith(prefix):
                        yield Completion(fl, start_position=-len(prefix))
                return

            # special positional words
            specials = {
                "base64": ["encode", "decode"],
                "b64": ["encode", "decode"],
                "checksum": ["--algo", "md5", "sha1", "sha256"],
                "find": ["-name", "-type", "f", "d", "-maxdepth"],
                "json": ["--get", "--set", "--pretty"],
                "replace": ["--regex", "--in-place"]
            }
            if cmd in specials:
                for w in specials[cmd]:
                    if w.startswith(prefix):
                        yield Completion(w, start_position=-len(prefix))

            # fallback to filesystem suggestions
            for p in _iter_path_completions(prefix):
                yield Completion(p, start_position=-len(prefix))

    session = PromptSession(history=InMemoryHistory(), auto_suggest=AutoSuggestFromHistory())
    completer = BlushCompleter()

    while True:
        try:
            user_input = session.prompt(f"{cin_prefix} ", completer=completer, complete_while_typing=True).strip()
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
        print(col.Fore.YELLOW + f"{warning_prefix}" + col.Fore.YELLOW + f" Command '{command}' not found")
        suggestions = fetcher.get_similar_commands(command)
        if suggestions:
            print(col.Fore.YELLOW + f"{warning_prefix}" + col.Fore.YELLOW + f" Did you mean: {', '.join(suggestions)}?")
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
            print(f"{error_prefix} {_format_lines(response[1])}")
        elif len(response) >= 2 and response[0] == "WARNING":
            print(f"{warning_prefix} {_format_lines(response[1])}")
        elif len(response) >= 2 and response[0] == "INFO":
            print(f"{blush_prefix} {_format_lines(response[1])}")
    elif isinstance(response, str) and response:
        print(f"{success_prefix} {_format_lines(response)}")

def get_blush_color():
    col = globals().get("colorama")
    if col is None:
        return ""
    color_name = load_config("blush_color")
    return getattr(col.Fore, color_name, col.Fore.MAGENTA)

def main():
    prepare()
    col = globals().get("colorama")
    col.init(autoreset=True, strip=False, convert=True)
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
