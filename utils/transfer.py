from __future__ import annotations
import os
import socket
import threading
import time
import secrets
import string
import platform
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import subprocess
import signal

from .settings import load_full_config, save_full_config, ensure_config

DISCOVERY_PORT = 35888
TRANSFER_PORT_DEFAULT = 35889
DISCOVERY_MAGIC = b"BLUSH_DISCOVER"
DISCOVERY_REPLY_MAGIC = b"BLUSH_HERE"

Device = Dict[str, str]  # {"device_id","name","ip","port"}

# Ctrl+C aware cancel event
_CANCEL_EVENT = threading.Event()
_SIGNAL_INSTALLED = False
_SIGNAL_LOCK = threading.Lock()

def _install_sigint_handler_once():
    global _SIGNAL_INSTALLED
    with _SIGNAL_LOCK:
        if _SIGNAL_INSTALLED:
            return
        def _handler(signum, frame):
            _CANCEL_EVENT.set()
        try:
            signal.signal(signal.SIGINT, _handler)
            _SIGNAL_INSTALLED = True
        except Exception:
            # Not fatal; fallback to default KeyboardInterrupt behavior
            pass

def _config_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("USERPROFILE")) / "AppData" / "Local" / ".blush" / "config.json"
    elif system in ["Linux", "Darwin"]:
        return Path(os.environ.get("HOME")) / ".blush" / "config.json"
    else:
        raise Exception("Unsupported OS")

def _paths() -> Dict[str, Path]:
    cfg = _config_path()
    root = cfg.parent
    return {"root": root, "config": cfg, "temp": root / "temp", "inbox": root / "inbox"}

def _load_cfg() -> Dict[str, any]:
    p = _config_path()
    ensure_config(p)
    return load_full_config(p)

def _save_cfg(cfg: Dict[str, any]):
    p = _config_path()
    ensure_config(p)
    save_full_config(p, cfg)

def _ensure_transfer(cfg: Dict[str, any]) -> Dict[str, any]:
    changed = False
    if "transfer" not in cfg or not isinstance(cfg["transfer"], dict):
        cfg["transfer"] = {"ask_on_receive": False, "auto_accept_from": [], "last_selected_host": None, "codes": {}}
        changed = True
    else:
        t = cfg["transfer"]
        if "ask_on_receive" not in t: t["ask_on_receive"] = False; changed = True
        if "auto_accept_from" not in t: t["auto_accept_from"] = []; changed = True
        if "last_selected_host" not in t: t["last_selected_host"] = None; changed = True
        if "codes" not in t: t["codes"] = {}; changed = True
    if changed:
        _save_cfg(cfg)
    return cfg

def get_device_identity() -> Tuple[str, str]:
    name = socket.gethostname()
    dev_id = "".join(ch for ch in name if ch.isalnum())[:16] or "device"
    return dev_id, name

def generate_pair_code(n: int = 12) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))

# ----------------- Pending Request Manager (Host-side) -----------------

class Request:
    def __init__(self, req_id: str, their_id: str, their_name: str, fname: str, size: int):
        self.id = req_id
        self.their_id = their_id
        self.their_name = their_name
        self.fname = fname
        self.size = size
        self.event = threading.Event()
        self.allow: Optional[bool] = None
        self.always_trust: bool = False

class RequestManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending: Dict[str, Request] = {}
        self._recent: List[str] = []  # list of saved file paths

    def create(self, their_id: str, their_name: str, fname: str, size: int) -> Request:
        rid = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        req = Request(rid, their_id, their_name, fname, size)
        with self._lock:
            self._pending[rid] = req
        try:
            print(f"\n[!] Incoming request {rid} from {their_name} ({their_id}) for '{fname}' ({size} bytes).")
            print("[!] Use: blush-transfer incoming to approve/deny.")
        except Exception:
            pass
        return req

    def decide(self, req_id: str, allow: bool, always_trust: bool = False) -> bool:
        with self._lock:
            req = self._pending.get(req_id)
            if not req:
                return False
            req.allow = allow
            req.always_trust = always_trust
            req.event.set()
            if not allow:
                if req.id in self._pending:
                    del self._pending[req_id]
            return True

    def wait(self, req: Request, timeout: float = 180.0) -> Tuple[bool, bool]:
        ok = req.event.wait(timeout)
        with self._lock:
            if not ok:
                req.allow = False
                if req.id in self._pending:
                    del self._pending[req.id]
                return False, False
            allow = bool(req.allow)
            always = bool(req.always_trust)
            if req.id in self._pending:
                del self._pending[req.id]
            return allow, always

    def list(self) -> List[Dict[str, str]]:
        with self._lock:
            return [
                {
                    "id": r.id,
                    "from_id": r.their_id,
                    "from_name": r.their_name,
                    "file": r.fname,
                    "size": str(r.size),
                }
                for r in self._pending.values()
            ]

    def push_recent(self, path: str):
        with self._lock:
            self._recent.append(path)

    def pop_recents(self) -> List[str]:
        with self._lock:
            out = self._recent[:]
            self._recent.clear()
            return out

_mgr = RequestManager()

def list_pending_requests() -> List[Dict[str, str]]:
    return _mgr.list()

def accept_request(req_id: str, always_trust: bool = False) -> bool:
    return _mgr.decide(req_id, True, always_trust)

def deny_request(req_id: str) -> bool:
    return _mgr.decide(req_id, False, False)

def pop_recent_received() -> List[str]:
    return _mgr.pop_recents()

def open_folder(path: Path):
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(path)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass

# ----------------- Host Service -----------------

class HostService:
    def __init__(self, port: int = TRANSFER_PORT_DEFAULT):
        self.paths = _paths()
        self.port = port
        self.running = False
        self._udp_thread: Optional[threading.Thread] = None
        self._tcp_thread: Optional[threading.Thread] = None
        self._udp_sock: Optional[socket.socket] = None
        self._tcp_srv: Optional[socket.socket] = None
        self.pair_code = generate_pair_code()
        self.device_id, self.name = get_device_identity()
        self.session_paired: Set[str] = set()

    def start(self):
        if self.running:
            return
        self.running = True
        inbox = self.paths["inbox"]
        inbox.mkdir(parents=True, exist_ok=True)
        self._udp_thread = threading.Thread(target=self._udp_discovery_loop, daemon=True)
        self._udp_thread.start()
        self._tcp_thread = threading.Thread(target=self._tcp_server_loop, daemon=True)
        self._tcp_thread.start()

    def stop(self):
        self.running = False
        try:
            if self._udp_sock:
                self._udp_sock.close()
        except Exception:
            pass
        try:
            if self._tcp_srv:
                self._tcp_srv.close()
        except Exception:
            pass

    def _udp_discovery_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_sock = sock
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
        except Exception:
            return
        while self.running:
            try:
                sock.settimeout(1.0)
                data, addr = sock.recvfrom(4096)
                if not self.running:
                    break
                if data == DISCOVERY_MAGIC:
                    payload = f"{self.device_id}|{self.name}|{self._get_local_ip()}|{self.port}".encode("utf-8")
                    sock.sendto(DISCOVERY_REPLY_MAGIC + b"|" + payload, addr)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception:
                continue

    def _tcp_server_loop(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_srv = srv
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("", self.port))
            srv.listen(5)
        except Exception:
            return
        while self.running:
            try:
                srv.settimeout(1.0)
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception:
                continue
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr):
        try:
            conn.settimeout(300)

            def recvline() -> str:
                buf = b""
                while b"\n" not in buf:
                    try:
                        chunk = conn.recv(1024)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf += chunk
                return buf.strip().decode("utf-8", errors="ignore")

            def sendline(s: str):
                conn.sendall((s + "\n").encode("utf-8"))

            # HELLO
            hello = recvline()
            if not hello.startswith("HELLO "):
                conn.close(); return
            _, their_id, their_name = (hello.split(" ", 2) + ["", ""])[:3]

            # If this device already paired in this host session, skip code challenge
            if their_id in self.session_paired:
                sendline("OK PAIRED")
            else:
                # One-time code exchange (in-memory only)
                sendline(f"CODE {self.pair_code}")
                pair = recvline()
                if not pair.startswith("PAIR "):
                    conn.close(); return
                code = pair.split(" ", 1)[1].strip()
                if code != self.pair_code:
                    sendline("ERR BAD_CODE"); conn.close(); return
                # Mark device as paired for the remainder of this host session
                self.session_paired.add(their_id)
                sendline("OK PAIRED")

            # File meta
            meta = recvline()
            if meta == "CANCEL":
                conn.close(); return
            if not meta.startswith("FILE "):
                conn.close(); return
            _, fname, fsize = (meta.split(" ", 2) + ["", ""])[:3]
            try:
                size = int(fsize)
            except:
                sendline("ERR BAD_META"); conn.close(); return

            # Decide acceptance:
            cfg = _ensure_transfer(_load_cfg())
            trusted = set(cfg["transfer"].get("auto_accept_from", []))

            # Always require explicit approval unless device is trusted
            allow = their_id in trusted
            always = False

            if not allow:
                # Queue the request and wait for host decision
                req = _mgr.create(their_id, their_name, fname, size)
                allow, always = _mgr.wait(req, timeout=180.0)  # wait up to 3 minutes
                if always and allow and their_id not in trusted:
                    cfg["transfer"]["auto_accept_from"].append(their_id)
                    _save_cfg(cfg)

            if not allow:
                try: sendline("ERR NOT_ALLOWED")
                except Exception: pass
                try: conn.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                conn.close()
                return

            sendline("OK SEND")

            # Receive bytes
            inbox = self.paths["inbox"]
            safe_name = os.path.basename(fname) or "received.bin"
            dest = inbox / safe_name
            with open(dest, "wb") as f:
                remaining = size
                while remaining > 0:
                    try:
                        chunk = conn.recv(min(65536, remaining))
                    except socket.timeout:
                        continue
                    if not chunk: break
                    f.write(chunk); remaining -= len(chunk)
            sendline("OK DONE")
            try:
                print(f"\n[✓] Received '{safe_name}' -> {dest}")
                _mgr.push_recent(str(dest))
            except Exception:
                pass
        except Exception:
            try: conn.close()
            except Exception: pass

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

# -------- Singleton host manager (one session per process) --------

_CURRENT_HOST: Optional[HostService] = None
_LOCK = threading.Lock()

def start_host(port: int = TRANSFER_PORT_DEFAULT) -> HostService:
    global _CURRENT_HOST
    with _LOCK:
        if _CURRENT_HOST and _CURRENT_HOST.running:
            return _CURRENT_HOST
        if _CURRENT_HOST and not _CURRENT_HOST.running:
            try: _CURRENT_HOST.stop()
            except Exception: pass
        _CURRENT_HOST = HostService(port=port)
        _CURRENT_HOST.start()
        return _CURRENT_HOST

def stop_host() -> bool:
    global _CURRENT_HOST
    with _LOCK:
        if _CURRENT_HOST and _CURRENT_HOST.running:
            _CURRENT_HOST.stop()
            _CURRENT_HOST = None
            return True
        return False

def get_active_host() -> Optional[HostService]:
    return _CURRENT_HOST

def discover_devices(timeout: float = 2.0) -> List[Device]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    res: List[Device] = []
    try:
        sock.sendto(DISCOVERY_MAGIC, ("255.255.255.255", DISCOVERY_PORT))
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                if data.startswith(DISCOVERY_REPLY_MAGIC + b"|"):
                    payload = data.split(b"|", 1)[1].decode("utf-8", errors="ignore")
                    dev_id, name, ip, port = (payload.split("|") + ["", "", "", ""])[:4]
                    res.append({"device_id": dev_id, "name": name, "ip": ip, "port": port})
            except socket.timeout:
                break
            except Exception:
                continue
    finally:
        sock.close()
    return res

def client_send_file(target: Device, file_path: str) -> Tuple[bool, str]:
    """
    Sender waits for host decision; Ctrl+C cancels cleanly.
    Pair code is cached per device_id and reused. If cache is wrong, we prompt once and update.
    """
    from prompt_toolkit import prompt

    dev_id, name, ip, port = target["device_id"], target["name"], target["ip"], int(target["port"])
    size = os.path.getsize(file_path)

    # Prepare cancel and config
    _CANCEL_EVENT.clear()
    _install_sigint_handler_once()
    cfg = _ensure_transfer(_load_cfg())
    codes = cfg["transfer"].get("codes", {})

    def connect():
        try:
            conn = socket.create_connection((ip, port), timeout=10)
            conn.settimeout(0.5)  # short timeouts to honor Ctrl+C quickly
            return conn
        except Exception as e:
            return None

    def recvline(conn: socket.socket) -> str:
        buf = b""
        while b"\n" not in buf:
            if _CANCEL_EVENT.is_set():
                try:
                    conn.sendall(b"CANCEL\n")
                except Exception:
                    pass
                raise KeyboardInterrupt()
            try:
                chunk = conn.recv(1024)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
        return buf.strip().decode("utf-8", errors="ignore")

    def sendline(conn: socket.socket, s: str):
        conn.sendall((s + "\n").encode("utf-8"))

    try:
        # 1) Connect and pair (with one retry if cached code fails)
        for attempt in range(2):
            conn = connect()
            if not conn:
                return False, f"connect failed: could not reach {ip}:{port}"

            try:
                my_id, my_name = get_device_identity()
                sendline(conn, f"HELLO {my_id} {my_name}")

                got = recvline(conn)
                if got.startswith("OK"):
                    # already paired this host session
                    break

                if got.startswith("CODE "):
                    # try cached code first (only first attempt)
                    use_cached = (attempt == 0 and dev_id in codes and codes[dev_id])
                    if use_cached:
                        sendline(conn, f"PAIR {codes[dev_id]}")
                        ok = recvline(conn)
                        if ok.startswith("OK"):
                            break  # paired
                        # cached code invalid -> drop and retry with prompt
                        try:
                            del codes[dev_id]
                            cfg["transfer"]["codes"] = codes
                            _save_cfg(cfg)
                        except Exception:
                            pass
                        # reconnect for next attempt
                        try: conn.close()
                        except Exception: pass
                        continue

                    # prompt for code and persist on success
                    entered = prompt(f"Enter host code for {name} ({ip}): ").strip().upper()
                    sendline(conn, f"PAIR {entered}")
                    ok = recvline(conn)
                    if not ok.startswith("OK"):
                        try: conn.close()
                        except Exception: pass
                        return False, "pair failed"
                    # save code
                    codes[dev_id] = entered
                    cfg["transfer"]["codes"] = codes
                    _save_cfg(cfg)
                    break
                else:
                    try: conn.close()
                    except Exception: pass
                    return False, "bad handshake"
            except KeyboardInterrupt:
                try:
                    sendline(conn, "CANCEL")
                except Exception:
                    pass
                try: conn.close()
                except Exception: pass
                return False, "sender cancelled"

        # 2) Send file meta and wait for approval
        try:
            fname = os.path.basename(file_path)
            sendline(conn, f"FILE {fname} {size}")
            ack = recvline(conn)  # waits for host approval (or rejection)
            if not ack.startswith("OK"):
                try: conn.close()
                except Exception: pass
                return False, "transfer rejected by host (not accepted, denied, or timed out)"
        except KeyboardInterrupt:
            try:
                sendline(conn, "CANCEL")
            except Exception:
                pass
            try: conn.close()
            except Exception: pass
            return False, "sender cancelled"

        # 3) Stream bytes
        try:
            with open(file_path, "rb") as f:
                while True:
                    if _CANCEL_EVENT.is_set():
                        try:
                            sendline(conn, "CANCEL")
                        except Exception:
                            pass
                        try: conn.close()
                        except Exception: pass
                        return False, "sender cancelled"
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    conn.sendall(chunk)
            done = recvline(conn)
            if not done.startswith("OK"):
                try: conn.close()
                except Exception: pass
                return False, "transfer failed"
            try: conn.close()
            except Exception: pass
            return True, f"sent {fname} ({size} bytes) to {name} [{ip}]"
        except KeyboardInterrupt:
            try:
                sendline(conn, "CANCEL")
            except Exception:
                pass
            try: conn.close()
            except Exception: pass
            return False, "sender cancelled"
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return False, f"send failed: {e}"
