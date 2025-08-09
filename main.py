import os
import subprocess
import sys
from pathlib import Path
import platform
import shlex
import json

from utils import fetcher
from utils.settings import load_full_config, ensure_config, get_blush_paths
from utils.colors import get_color

import colorama
import wcwidth
import prompt_toolkit
import psutil

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

BLUSH_PATHS = get_blush_paths()
BLUSH_PATH = BLUSH_PATHS["root"]
TEMP_PATH = BLUSH_PATHS["temp"]
BLUSH_CONFIG_PATH = BLUSH_PATHS["config"]
RESTART_SCRIPT = TEMP_PATH / ("restart.bat" if os.name == "nt" else "restart.sh")

def delete_restart_script():
    if RESTART_SCRIPT.exists():
        RESTART_SCRIPT.unlink()

def prepare():
    os.makedirs(TEMP_PATH, exist_ok=True)
    ensure_config(BLUSH_CONFIG_PATH)
    delete_restart_script()

load_banner = r"""$$$$$$$\  $$\       $$\   $$\  $$$$$$\  $$\   $$\
$$  __$$\ $$ |      $$ |  $$ |$$  __$$\ $$ |  $$ |
$$ |  $$ |$$ |      $$ |  $$ |$$ |  $$ |$$ |  $$ |
$$ |  $$ |$$ |      $$ |  $$ |$$ |  $$ |$$ |  $$ |
$$ |  $$ |$$ |      $$ |  $$ |$$$$$$$  |$$$$$$$$ |
$$ |  $$ |$$ |      $$ |  $$ |$$  __$$< $$  __$$ |
$$ |  $$ |$$$$$$$$\ \$$$$$$  |$$ |  $$ |$$ |  $$ |
\__|  \__|\________| \______/ \__|  \__|\__|  \__|"""

def display_banner():
    col = colorama
    cfg = load_full_config(BLUSH_CONFIG_PATH)
    colors = {
        "blush": get_color(cfg.get("blush_color", "MAGENTA")),
        "success": get_color(cfg.get("success_color", "GREEN")),
        "warning": get_color(cfg.get("warning_color", "YELLOW")),
        "error": get_color(cfg.get("error_color", "RED")),
    }
    for line in load_banner.splitlines():
        print(colors["blush"] + line + col.Style.RESET_ALL)
    print("")
    print(colors["success"] + f"{success_prefix} All modules loaded" + col.Style.RESET_ALL)
    print(get_color("BLUE") + f"{blush_prefix} Blush - Fast & Optimized Shell" + col.Style.RESET_ALL)
    print("")

def _format_lines(text: str) -> str:
    lines = text.splitlines()
    out = []
    for ln in lines:
        if ln and ln[0].islower():
            out.append(ln[0].upper() + ln[1:])
        else:
            out.append(ln)
    return "\n".join(out)

def _build_flags_map():
    return fetcher.get_flags_map()

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
    import shlex as _sh
    try:
        lexer = _sh.shlex(text, posix=True)
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

            if len(tokens) == 0 or (len(tokens) == 1 and not ends_with_space):
                for c in cmds:
                    if c.startswith(prefix):
                        yield Completion(c, start_position=-len(prefix))
                return

            cmd = tokens[0].lower()
            is_flag_context = prefix.startswith("-")
            if is_flag_context:
                for fl in self.flags.get(cmd, []):
                    if fl.startswith(prefix):
                        yield Completion(fl, start_position=-len(prefix))
                return

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
    col = colorama
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
        print(get_color("YELLOW") + f"{warning_prefix} Command '{command}' not found")
        suggestions = fetcher.get_similar_commands(command)
        if suggestions:
            print(get_color("YELLOW") + f"{warning_prefix} Did you mean: {', '.join(suggestions)}?")
        return
    try:
        response = fetcher.execute([command] + arguments)
        handle_response(response)
    except Exception as e:
        print(f"{error_prefix} Error executing command: {str(e)}")

def handle_response(response):
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

def get_prefixes():
    import wcwidth
    col = colorama
    cfg = load_full_config(BLUSH_CONFIG_PATH)

    def pad_display(text, width=2):
        w = sum(wcwidth.wcwidth(c) or 0 for c in text)
        return text + " " * max(0, width - w)

    def colorize(color_name, text):
        return get_color(color_name) + text + col.Style.RESET_ALL

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
        "success_prefix": colorize(cfg.get("success_color", "GREEN"), pad_display(base["success"])),
        "warning_prefix": colorize(cfg.get("warning_color", "YELLOW"), pad_display(base["warning"])),
        "error_prefix": colorize(cfg.get("error_color", "RED"), pad_display(base["error"])),
        "think_prefix": pad_display(base["think"]),
        "cin_prefix": pad_display(base["cin"]),
    }

def main():
    prepare()
    col = colorama
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
