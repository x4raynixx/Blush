from __future__ import annotations
import os
import platform
from pathlib import Path
from typing import List, Dict, Any

from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit import prompt

from ..transfer import (
    start_host, stop_host, get_active_host,
    discover_devices, client_send_file,
    list_pending_requests, accept_request, deny_request,
    pop_recent_received, open_folder
)
from ..colors import list_supported_colors

BLUSH_COMMANDS = ["blush", "blush-settings", "blush-transfer", "blush-connect"]
EXTRA_COMMANDS: List[str] = [
    "lower", "upper", "titlecase", "reverse", "length", "trim", "ltrim", "rtrim",
    "snake", "kebab", "camel", "rot13", "url-encode", "url-decode",
    "base32-encode", "base32-decode", "shuffle-lines", "uniq-lines", "sort-lines",
    "dedent", "indent", "uuid", "random-int", "random-float", "password", "nanoid",
    "now", "epoch", "iso-now", "ts-to-date", "sleepms", "gcd", "lcm", "factorial",
    "sum", "avg", "cpu", "mem", "disk", "proc-count", "platform", "python",
    "localip", "portscan", "mkdirs", "rmr", "touchmany", "rename-ext", "find-large",
    "watch", "diff", "crc32", "hexdump", "lines",
] + [f"cmd{i:02d}" for i in range(1, 61)]

def _config_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("USERPROFILE")) / "AppData" / "Local" / ".blush" / "config.json"
    elif system in ["Linux", "Darwin"]:
        return Path(os.environ.get("HOME")) / ".blush" / "config.json"
    else:
        raise Exception("Unsupported OS")

def _load_cfg() -> Dict[str, Any]:
    from ..settings import load_full_config, ensure_config
    cfg_path = _config_path()
    ensure_config(cfg_path)
    return load_full_config(cfg_path)

def _save_cfg(cfg: Dict[str, Any]):
    from ..settings import save_full_config, ensure_config
    cfg_path = _config_path()
    ensure_config(cfg_path)
    save_full_config(cfg_path, cfg)

def _ensure_transfer(cfg: Dict[str, Any]) -> Dict[str, Any]:
    changed = False
    if "transfer" not in cfg or not isinstance(cfg["transfer"], dict):
        cfg["transfer"] = {"ask_on_receive": False, "auto_accept_from": [], "last_selected_host": None}
        changed = True
    else:
        t = cfg["transfer"]
        if "ask_on_receive" not in t: t["ask_on_receive"] = False; changed = True
        if "auto_accept_from" not in t: t["auto_accept_from"] = []; changed = True
        if "last_selected_host" not in t: t["last_selected_host"] = None; changed = True
    if changed:
        _save_cfg(cfg)
    return cfg

def _inbox_path() -> Path:
    # mirror utils.settings path logic
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("USERPROFILE")) / "AppData" / "Local" / ".blush" / "inbox"
    else:
        return Path(os.environ.get("HOME")) / ".blush" / "inbox"

class blush:
    @staticmethod
    def run(args: List[str]):
        # blush set host | blush host stop | blush connect select | blush transfer <file> | blush incoming | blush accept <id> [--always] | blush deny <id> | blush open-inbox | blush status
        if len(args) == 1:
            return ["INFO", "Usage: blush set host | blush host stop | blush connect select | blush transfer <file> | blush incoming | blush accept <id> [--always] | blush deny <id> | blush open-inbox | blush status"]

        sub = args[1].lower()

        # Start/stop host
        if sub == "set" and len(args) >= 3 and args[2].lower() == "host":
            host = start_host()
            msg = f"Host enabled on port {host.port}.\nDevice ID: {host.device_id}\nPair Code: {host.pair_code}\nWaiting for connections...\nUse 'blush incoming' to review pending requests."
            return ["INFO", msg]

        if (sub == "host" and len(args) >= 3 and args[2].lower() == "stop") or (sub == "stop" and len(args) >= 3 and args[2].lower() == "host"):
            ok = stop_host()
            return ["INFO", "Host stopped"] if ok else ["WARNING", "Host not running"]

        # Status
        if sub == "status":
            host = get_active_host()
            cfg = _ensure_transfer(_load_cfg())
            ask = cfg["transfer"].get("ask_on_receive", False)
            last = cfg["transfer"].get("last_selected_host")
            if host and host.running:
                return ["INFO", f"Host: ON port={host.port}\nDevice: {host.device_id}\nPair Code: {host.pair_code}\nAsk on receive: {ask}\nLast target: {last or '-'}"]
            return ["INFO", f"Host: OFF\nAsk on receive: {ask}\nLast target: {last or '-'}"]

        # Incoming queue (interactive)
        if sub == "incoming":
            try:
                while True:
                    items = list_pending_requests()
                    print("\nPending requests:")
                    if not items:
                        print("  (none)")
                    else:
                        for idx, it in enumerate(items, 1):
                            print(f"  {idx}. {it['from_name']} ({it['from_id']}) -> {it['file']} [{it['size']} bytes]  id={it['id']}")

                    # Show recent received and ask to open
                    recents = pop_recent_received()
                    for p in recents:
                        print(f"\n[✓] Received: {p}")
                        ans = input("Open folder now? (y/N): ").strip().lower()
                        if ans == "y":
                            inbox = _inbox_path()
                            inbox.mkdir(parents=True, exist_ok=True)
                            open_folder(inbox)

                    sel = input("\nEnter number to accept/deny, 'r' to refresh, 'exit' to quit: ").strip().lower()
                    if sel == "exit":
                        break
                    if sel == "r" or sel == "":
                        continue
                    if sel.isdigit():
                        idx = int(sel) - 1
                        if idx < 0 or idx >= len(items):
                            print("Invalid selection")
                            continue
                        req_id = items[idx]["id"]
                        yn = input("Accept? (y/N/a=always trust): ").strip().lower()
                        if yn == "a":
                            ok = accept_request(req_id, always_trust=True)
                            print("Accepted and trusted" if ok else "Invalid request id")
                        elif yn == "y":
                            ok = accept_request(req_id, always_trust=False)
                            print("Accepted" if ok else "Invalid request id")
                        else:
                            ok = deny_request(req_id)
                            print("Denied" if ok else "Invalid request id")
                        # loop continues; host will receive if accepted
                        continue
                    else:
                        print("Invalid input")
                        continue
            except KeyboardInterrupt:
                pass
            return ["INFO", "Incoming review closed"]

        if sub == "accept" and len(args) >= 3:
            rid = args[2]
            always = ("--always" in args)
            ok = accept_request(rid, always_trust=always)
            return ["INFO", ("Accepted" + (" and trusted" if always else ""))] if ok else ["ERROR", "Invalid request id"]

        if sub == "deny" and len(args) >= 3:
            rid = args[2]
            ok = deny_request(rid)
            return ["INFO", "Denied"] if ok else ["ERROR", "Invalid request id"]

        if sub == "open-inbox":
            inbox = _inbox_path()
            inbox.mkdir(parents=True, exist_ok=True)
            open_folder(inbox)
            return ["SUCCESS"]

        # Discover/select target
        if sub == "connect" and len(args) >= 3 and args[2].lower() == "select":
            devs = discover_devices(timeout=2.0)
            if not devs:
                return ["WARNING", "No devices discovered on LAN"]
            items = [(str(i), f"{d['name']} [{d['ip']}:{d['port']}] ({d['device_id']})") for i, d in enumerate(devs)]
            choice = radiolist_dialog(title="Blush Connect", text="Select a host:", values=items).run()
            if choice is None:
                return ["WARNING", "Selection aborted"]
            sel = devs[int(choice)]
            cfg = _ensure_transfer(_load_cfg())
            cfg["transfer"]["last_selected_host"] = sel
            _save_cfg(cfg)
            return ["INFO", f"Selected {sel['name']} [{sel['ip']}:{sel['port']}]"]

        # Send file
        if sub == "transfer" and len(args) >= 3:
            file_path = args[2]
            if not os.path.isfile(file_path):
                return ["ERROR", "file not found"]
            cfg = _ensure_transfer(_load_cfg())
            tgt = cfg["transfer"].get("last_selected_host")
            if not tgt:
                return ["WARNING", "No host selected. Use: blush connect select"]
            ok, msg = client_send_file(tgt, file_path)
            return ["INFO", msg] if ok else ["ERROR", msg]

        return ["WARNING", "Unknown blush subcommand"]

class blush_settings:
    @staticmethod
    def run(args: List[str]):
        cfg = _ensure_transfer(_load_cfg())
        colors = list_supported_colors()
        current = {
            "blush": cfg.get("blush_color", "MAGENTA"),
            "success": cfg.get("success_color", "GREEN"),
            "warning": cfg.get("warning_color", "YELLOW"),
            "error": cfg.get("error_color", "RED"),
        }

        def choose(label: str, cur: str) -> str:
            vals = [(c, c) for c in colors]
            sel = radiolist_dialog(title="Blush Settings", text=f"Select {label} color", values=vals, default=cur).run()
            return sel or cur

        current["blush"] = choose("blush", current["blush"])
        current["success"] = choose("success", current["success"])
        current["warning"] = choose("warning", current["warning"])
        current["error"] = choose("error", current["error"])

        ask_default = "Y" if cfg["transfer"].get("ask_on_receive", False) else "N"
        ask = prompt(f"Ask before receiving from untrusted devices? (y/N) [{ask_default}]: ").strip().lower()
        ask_on_receive = True if ask == "y" else (False if ask == "n" else cfg["transfer"].get("ask_on_receive", False))

        trust = cfg["transfer"].get("auto_accept_from", [])
        add_trust = prompt("Add a trusted device_id (enter to skip): ").strip()
        if add_trust and add_trust not in trust:
            trust.append(add_trust)

        cfg["blush_color"] = current["blush"]
        cfg["success_color"] = current["success"]
        cfg["warning_color"] = current["warning"]
        cfg["error_color"] = current["error"]
        cfg["transfer"]["ask_on_receive"] = ask_on_receive
        cfg["transfer"]["auto_accept_from"] = trust
        _save_cfg(cfg)
        return ["INFO", "Settings saved"]

class blush_transfer:
    @staticmethod
    def run(args: List[str]):
        if len(args) < 2:
            return ["WARNING", "Usage: blush-transfer <file>"]
        return blush.run(["blush", "transfer", args[1]])

class blush_connect:
    @staticmethod
    def run(args: List[str]):
        if len(args) >= 2 and args[1].lower() == "select":
            return blush.run(["blush", "connect", "select"])
        return ["WARNING", "Usage: blush-connect select"]

class extra:
    @staticmethod
    def run(args: List[str]):
        # unchanged utility commands (truncated for brevity)
        import re, time, base64, binascii, random, hashlib, socket, psutil, textwrap, urllib.parse, uuid as uuidlib
        name = args[0].lower()
        rest = args[1:]
        def need_file(): return ["WARNING", f"Usage: {name} <file>"]
        if name == "lower":   return ["INFO", " ".join(rest).lower()]
        if name == "upper":   return ["INFO", " ".join(rest).upper()]
        if name == "titlecase": return ["INFO", " ".join(rest).title()]
        if name == "reverse": return ["INFO", " ".join(rest)[::-1]]
        if name == "length":  return ["INFO", str(len(" ".join(rest)))]
        if name == "trim":    return ["INFO", " ".join(rest).strip()]
        if name == "ltrim":   return ["INFO", " ".join(rest).lstrip()]
        if name == "rtrim":   return ["INFO", " ".join(rest).rstrip()]
        if name == "snake":
            s = " ".join(rest); s = re.sub(r"[\s\-]+", "_", s).lower(); return ["INFO", s]
        if name == "kebab":
            s = " ".join(rest); s = re.sub(r"[\s_]+", "-", s).lower(); return ["INFO", s]
        if name == "camel":
            s = " ".join(rest); parts = re.split(r"[\s_\-]+", s)
            return ["INFO", parts[0].lower() + "".join(p.capitalize() for p in parts[1:])] if parts else ["INFO", ""]
        if name == "rot13":
            s = " ".join(rest)
            tbl = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz","NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm")
            return ["INFO", s.translate(tbl)]
        if name == "url-encode": return ["INFO", urllib.parse.quote(" ".join(rest))]
        if name == "url-decode": return ["INFO", urllib.parse.unquote(" ".join(rest))]
        if name == "base32-encode":
            b = " ".join(rest).encode("utf-8"); return ["INFO", base64.b32encode(b).decode("ascii")]
        if name == "base32-decode":
            try:
                b = base64.b32decode(" ".join(rest).encode("ascii")); return ["INFO", b.decode("utf-8", errors="ignore")]
            except Exception as e: return ["ERROR", str(e)]
        if name == "shuffle-lines":
            if not rest: return ["WARNING", "Usage: shuffle-lines <file>"]
            try:
                with open(rest[0], "r", encoding="utf-8", errors="ignore") as f: lines = f.readlines()
                random.shuffle(lines); return ["INFO", "".join(lines)]
            except Exception as e: return ["ERROR", str(e)]
        if name == "uniq-lines":
            if not rest: return ["WARNING", "Usage: uniq-lines <file>"]
            try:
                with open(rest[0], "r", encoding="utf-8", errors="ignore") as f:
                    seen, out = set(), []
                    for line in f:
                        if line not in seen:
                            seen.add(line); out.append(line)
                return ["INFO", "".join(out)]
            except Exception as e: return ["ERROR", str(e)]
        if name == "sort-lines":
            if not rest: return ["WARNING", "Usage: sort-lines <file>"]
            try:
                with open(rest[0], "r", encoding="utf-8", errors="ignore") as f:
                    lines = sorted(f.readlines())
                return ["INFO", "".join(lines)]
            except Exception as e: return ["ERROR", str(e)]
        if name == "dedent": return ["INFO", textwrap.dedent(" ".join(rest))]
        if name == "indent": return ["INFO", textwrap.indent(" ".join(rest), "  ")]
        if name == "uuid":
            import uuid as uuidlib; return ["INFO", str(uuidlib.uuid4())]
        if name == "random-int":
            a, b = 0, 100
            if len(rest) >= 2:
                try: a, b = int(rest[0]), int(rest[1])
                except: pass
            return ["INFO", str(random.randint(a, b))]
        if name == "random-float": return ["INFO", f"{random.random():.6f}"]
        if name == "password":
            import secrets, string
            length = int(rest[0]) if rest and rest[0].isdigit() else 16
            alphabet = string.ascii_letters + string.digits
            return ["INFO", "".join(secrets.choice(alphabet) for _ in range(length))]
        if name == "nanoid":
            import secrets, string
            alphabet = string.ascii_letters + string.digits + "_-"
            length = int(rest[0]) if rest and rest[0].isdigit() else 21
            return ["INFO", "".join(secrets.choice(alphabet) for _ in range(length))]
        if name == "now":
            import time; return ["INFO", time.strftime("%Y-%m-%d %H:%M:%S")]
        if name == "epoch":
            import time; return ["INFO", str(int(time.time()))]
        if name == "iso-now":
            import datetime; return ["INFO", datetime.datetime.utcnow().isoformat() + "Z"]
        if name == "ts-to-date":
            import datetime
            if not rest: return ["WARNING", "Usage: ts-to-date <epoch>"]
            try: ts = int(rest[0]); return ["INFO", datetime.datetime.utcfromtimestamp(ts).isoformat() + "Z"]
            except: return ["ERROR", "invalid timestamp"]
        if name == "sleepms":
            import time
            ms = int(rest[0]) if rest and rest[0].isdigit() else 100
            time.sleep(min(ms, 5000)/1000.0); return ["SUCCESS"]
        if name == "gcd":
            import math
            if len(rest) < 2: return ["WARNING", "Usage: gcd a b"]
            try: return ["INFO", str(math.gcd(int(rest[0]), int(rest[1])))]
            except: return ["ERROR", "invalid numbers"]
        if name == "lcm":
            import math
            if len(rest) < 2: return ["WARNING", "Usage: lcm a b"]
            try:
                a, b = int(rest[0]), int(rest[1]); return ["INFO", str(abs(a*b)//math.gcd(a,b))]
            except: return ["ERROR", "invalid numbers"]
        if name == "factorial":
            import math
            if not rest: return ["WARNING", "Usage: factorial n"]
            try:
                n = int(rest[0]); 
                if n < 0 or n > 1000: return ["ERROR", "n out of range"]
                return ["INFO", str(math.factorial(n))]
            except: return ["ERROR", "invalid n"]
        if name == "sum":
            try: return ["INFO", str(sum(float(x) for x in rest))]
            except: return ["ERROR", "invalid numbers"]
        if name == "avg":
            try:
                xs = [float(x) for x in rest]; return ["INFO", str(sum(xs)/len(xs))]
            except: return ["ERROR", "invalid numbers"]
        if name == "cpu":
            import psutil; return ["INFO", f"cores: {psutil.cpu_count(logical=True)}, load: {psutil.cpu_percent(interval=0.2)}%"]
        if name == "mem":
            import psutil; v = psutil.virtual_memory(); return ["INFO", f"total {v.total} used {v.used} free {v.available}"]
        if name == "disk":
            import psutil, os as _os; du = psutil.disk_usage(_os.sep); return ["INFO", f"total {du.total} used {du.used} free {du.free}"]
        if name == "proc-count":
            import psutil
            try: return ["INFO", str(len(list(psutil.process_iter())))]
            except: return ["ERROR", "cannot read processes"]
        if name == "platform":
            import platform as pf; return ["INFO", f"{pf.system()} {pf.release()} {pf.machine()}"]
        if name == "python":
            import sys; return ["INFO", sys.version.split()[0]]
        if name == "localip":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.1); s.connect(("8.8.8.8",80))
                ip = s.getsockname()[0]; s.close(); return ["INFO", ip]
            except: return ["INFO", "127.0.0.1"]
        if name == "portscan":
            if len(rest) < 2: return ["WARNING", "Usage: portscan <host> <start-end>"]
            host = rest[0]
            try:
                a, b = [int(x) for x in rest[1].split("-")]
                open_ports = []
                for p in range(a, min(b, a+200)):
                    try:
                        with socket.create_connection((host, p), timeout=0.1): open_ports.append(p)
                    except: pass
                return ["INFO", f"open: {open_ports}"]
            except: return ["ERROR", "invalid range"]
        if name == "mkdirs":
            if not rest: return ["WARNING", "Usage: mkdirs <path>"]
            try: os.makedirs(rest[0], exist_ok=True); return ["SUCCESS"]
            except Exception as e: return ["ERROR", str(e)]
        if name == "rmr":
            import shutil
            if not rest: return ["WARNING", "Usage: rmr <path>"]
            try: shutil.rmtree(rest[0]); return ["SUCCESS"]
            except Exception as e: return ["ERROR", str(e)]
        if name == "touchmany":
            if not rest: return ["WARNING", "Usage: touchmany <file1> <file2> ..."]
            try:
                for f in rest: open(f,"a").close()
                return ["SUCCESS"]
            except Exception as e: return ["ERROR", str(e)]
        if name == "rename-ext":
            if len(rest) < 3: return ["WARNING", "Usage: rename-ext <dir> <old> <new>"]
            d, old, new = rest[0], rest[1], rest[2]
            try:
                changed = 0
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.endswith("." + old):
                            src = os.path.join(root, f)
                            dst = os.path.join(root, f[:-(len(old))] + new)
                            os.rename(src, dst); changed += 1
                return ["INFO", f"renamed {changed} files"]
            except Exception as e: return ["ERROR", str(e)]
        if name == "find-large":
            if len(rest) < 2: return ["WARNING", "Usage: find-large <dir> <size-bytes>"]
            try:
                base, sz = rest[0], int(rest[1]); out = []
                for root, _, files in os.walk(base):
                    for f in files:
                        p = os.path.join(root, f)
                        try:
                            if os.path.getsize(p) >= sz: out.append(p)
                        except: pass
                return ["INFO", "\n".join(out) if out else "None"]
            except: return ["ERROR", "invalid size"]
        if name == "watch":
            import time
            if not rest: return ["WARNING", "Usage: watch <file>"]
            p = rest[0]
            try:
                last = os.path.getmtime(p); out = []; t0 = time.time()
                while time.time() - t0 < 5:
                    t = os.path.getmtime(p)
                    if t != last: out.append(f"changed at {t}"); last = t
                    time.sleep(0.25)
                return ["INFO", "\n".join(out) if out else "no changes"]
            except Exception as e: return ["ERROR", str(e)]
        if name == "diff":
            if len(rest) < 2: return ["WARNING", "Usage: diff <a> <b>"]
            try:
                import difflib
                a = open(rest[0], "r", encoding="utf-8", errors="ignore").read().splitlines()
                b = open(rest[1], "r", encoding="utf-8", errors="ignore").read().splitlines()
                d = difflib.unified_diff(a, b, lineterm="")
                return ["INFO", "\n".join(d)]
            except Exception as e: return ["ERROR", str(e)]
        if name == "crc32":
            if not rest: return need_file()
            try:
                with open(rest[0], "rb") as f: data = f.read()
                return ["INFO", f"{binascii.crc32(data) & 0xffffffff:08x}  {rest[0]}"]
            except Exception as e: return ["ERROR", str(e)]
        if name == "hexdump":
            if not rest: return need_file()
            try:
                with open(rest[0], "rb") as f: data = f.read(1024)
                out = binascii.hexlify(data).decode("ascii"); return ["INFO", out]
            except Exception as e: return ["ERROR", str(e)]
        if name == "lines":
            if not rest: return need_file()
            try:
                with open(rest[0], "r", encoding="utf-8", errors="ignore") as f:
                    return ["INFO", str(sum(1 for _ in f))]
            except Exception as e: return ["ERROR", str(e)]
        if name.startswith("cmd"):
            return ["INFO", f"{name}: placeholder command (expand as needed)"]
        return ["WARNING", f"{name}: not implemented"]
