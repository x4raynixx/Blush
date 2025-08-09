from __future__ import annotations
# Combined registry: keep all existing commands and add new ones non-destructively.

import difflib
import shlex

# Import original commands
from .commands.cmd import *  # noqa: F401,F403

# Import unified transfer commands and extras
from .commands.blush import (
    BLUSH_COMMANDS,
    EXTRA_COMMANDS,
    blush_settings as blush_settings_cmd,
    blush_transfer as blush_transfer_cmd,
    extra as extra_cmd_handler,
)

# base command list from original file (kept intact)
command_list = [
    "mkdir", "clear", "cls", "rmdir", "ls", "dir", "cd", "pwd", "cat", "type",
    "echo", "touch", "cp", "copy", "mv", "move", "rm", "del", "find", "grep",
    "wc", "head", "tail", "chmod", "ps", "kill", "killall", "pkill", "date",
    "whoami", "uname", "df", "du", "history", "hist", "alias", "unalias",
    "which", "tree", "help", "exit", "quit", "export", "set", "unset", "env",
    "ping", "wget", "curl", "more", "less", "zip", "unzip", "tar", "untar",
    "checksum", "md5sum", "sha1sum", "sha256sum", "base64", "b64", "json",
    "replace", "sort", "uniq", "split", "sleep", "seq", "calc", "stat",
    "basename", "dirname", "free", "uptime", "hostname", "ip", "netstat",
    "dns", "nslookup", "ssf"
]

# new unified commands and 100+ extra ones
command_list += BLUSH_COMMANDS + EXTRA_COMMANDS

def ifexists(input_cmd):
    if input_cmd.lower() in command_list:
        return True
    aliases = get_aliases()
    return input_cmd.lower() in aliases

def get_similar_commands(input_cmd):
    matches = difflib.get_close_matches(input_cmd.lower(), command_list, n=5, cutoff=0.6)
    return matches

def get_flags_map():
    return {
        "ls": ["-a","-l","-h","-R","-1","-t","-S","--include=","--exclude="],
        "grep": ["-i","-n","-r","-E"],
        # unified API
        "blush-transfer": ["set", "send", "incoming", "status", "open-inbox", "default"],
        "zip": [],
        "tar": [],
        "curl": ["-o"],
    }

def execute(cmd):
    if not cmd:
        return ["ERROR", "Command not found"]
    # expand alias before running
    cmd = expand_alias(cmd)
    add_history(" ".join(cmd))
    command = cmd[0].lower()
    if not ifexists(command):
        return ["ERROR", "Command not found"]

    command_map = {
        # Original commands (omitted for brevity)
        "mkdir": mkdir.run,
        "clear": clear.run,
        "cls": cls.run,
        "rmdir": rmdir.run,
        "ls": ls.run,
        "dir": ls.run,
        "cd": cd.run,
        "pwd": pwd.run,
        "cat": cat.run,
        "type": cat.run,
        "echo": echo.run,
        "touch": touch.run,
        "cp": cp.run,
        "copy": cp.run,
        "mv": mv.run,
        "move": mv.run,
        "rm": rm.run,
        "del": rm.run,
        "find": find.run,
        "grep": grep.run,
        "wc": wc.run,
        "head": head.run,
        "tail": tail.run,
        "chmod": chmod.run,
        "ps": ps.run,
        "kill": kill.run,
        "killall": killall.run,
        "pkill": killall.run,
        "date": date.run,
        "whoami": whoami.run,
        "uname": uname.run,
        "df": df.run,
        "du": du.run,
        "history": history.run,
        "hist": history.run,
        "alias": alias.run,
        "unalias": unalias.run,
        "which": which.run,
        "tree": tree.run,
        "help": help_cmd.run,
        "exit": exit_cmd.run,
        "quit": exit_cmd.run,
        "export": export.run,
        "set": export.run,
        "unset": unset.run,
        "env": env.run,
        "ping": ping.run,
        "wget": wget.run,
        "curl": curl.run,
        "more": cat.run,
        "less": cat.run,
        "zip": zip_cmd.run,
        "unzip": unzip.run,
        "tar": tar.run,
        "untar": untar.run,
        "checksum": checksum.run,
        "md5sum": md5sum.run,
        "sha1sum": sha1sum.run,
        "sha256sum": sha256sum.run,
        "base64": base64_cmd.run,
        "b64": b64.run,
        "json": json_cmd.run,
        "replace": replace.run,
        "sort": sort.run,
        "uniq": uniq.run,
        "split": split.run,
        "sleep": sleep.run,
        "seq": seq.run,
        "calc": calc.run,
        "stat": stat.run,
        "basename": basename.run,
        "dirname": dirname.run,
        "free": free.run,
        "uptime": uptime.run,
        "hostname": hostname.run,
        "ip": ip.run,
        "netstat": netstat.run,
        "dns": dns.run,
        "nslookup": nslookup.run,
        "ssf": ssf.run,

        # Unified new commands
        "blush-settings": blush_settings_cmd.run,
        "blush-transfer": blush_transfer_cmd.run,
    }

    for name in EXTRA_COMMANDS:
        command_map[name] = extra_cmd_handler.run

    handler = command_map.get(command)
    if handler:
        return handler(cmd)
    return ["ERROR", "Command implementation not found"]
