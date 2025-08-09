import os
import sys
import shutil
import stat as statmod
import time
import platform
import subprocess
import glob
import re
import psutil
import socket
import zipfile
import tarfile
import base64
import hashlib
import getpass
import json
from pathlib import Path
from typing import List
import colorama

prefixes = None

def get_prefixes_dynamic():
    if prefixes is None:
        from main import get_prefixes
        prefixes = get_prefixes()
    return prefixes

current_dir = os.getcwd()
previous_dir = current_dir
command_history: List[str] = []
ALIASES: dict[str, str] = {}

def validate_args(args, min_args, usage):
    if len(args) < min_args:
        return ["WARNING", f"Usage: {usage}"]
    return None

def _include_exclude_filter(name: str, includes: List[str], excludes: List[str]) -> bool:
    import fnmatch
    if includes:
        matched = any(fnmatch.fnmatch(name, pat) for pat in includes)
        if not matched:
            return False
    if excludes:
        if any(fnmatch.fnmatch(name, pat) for pat in excludes):
            return False
    return True

def add_history(cmd_str: str):
    command_history.append(cmd_str)

def get_aliases():
    return dict(ALIASES)

def expand_alias(tokens: List[str]) -> List[str]:
    if not tokens:
        return tokens
    name = tokens[0]
    if name in ALIASES:
        import shlex
        base = shlex.split(ALIASES[name])
        return base + tokens[1:]
    return tokens

class cls:
    @staticmethod
    def run(args):
        return "$C_CLEAR"

class clear:
    @staticmethod
    def run(args):
        return "$C_CLEAR"

class alias:
    @staticmethod
    def run(args):
        if len(args) == 1:
            if not ALIASES:
                return ["INFO", "no aliases"]
            out = []
            for k in sorted(ALIASES.keys()):
                out.append(f"{k}='{ALIASES[k]}'")
            return ["INFO", "\n".join(out)]
        # naive parser: alias name=command...
        for spec in args[1:]:
            if "=" not in spec:
                return ["ERROR", "use alias name=command"]
            name, val = spec.split("=", 1)
            name = name.strip()
            val = val.strip().strip("'").strip('"')
            if not name:
                return ["ERROR", "invalid alias name"]
            ALIASES[name] = val
        return ["SUCCESS"]

class unalias:
    @staticmethod
    def run(args):
        if len(args) < 2:
            return ["WARNING", "Usage: unalias <name> [name...]"]
        removed = []
        for a in args[1:]:
            if a in ALIASES:
                del ALIASES[a]
                removed.append(a)
        if not removed:
            return ["WARNING", "no aliases removed"]
        return ["SUCCESS"]

class mkdir:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "mkdir <directory> [-m 755]")
        if validation:
            return validation
        mode = None
        paths = []
        i = 1
        while i < len(args):
            if args[i] == "-m" and i + 1 < len(args):
                try:
                    mode = int(args[i + 1], 8)
                except:
                    return ["ERROR", "invalid mode"]
                i += 2
            else:
                paths.append(args[i])
                i += 1
        try:
            for p in paths:
                os.makedirs(p, exist_ok=True)
                if mode is not None:
                    os.chmod(p, mode)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class rmdir:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "rmdir <directory>")
        if validation:
            return validation
        try:
            if not os.path.exists(args[1]):
                return ["ERROR", f"Directory '{args[1]}' does not exist"]
            if not os.path.isdir(args[1]):
                return ["ERROR", f"'{args[1]}' is not a directory"]
            os.rmdir(args[1])
            return ["SUCCESS"]
        except OSError as e:
            return ["ERROR", f"Cannot remove directory: {str(e)}"]

class ls:
    @staticmethod
    def run(args):
        path = "."
        show_all = False
        long_format = False
        human = False
        recursive = False
        onecol = False
        sort_time = False
        sort_size = False
        includes = []
        excludes = []
        i = 1
        while i < len(args):
            a = args[i]
            if a in ("-a", "--all"):
                show_all = True
            elif a in ("-l", "--long"):
                long_format = True
            elif a in ("-h", "--human"):
                human = True
            elif a in ("-R", "--recursive"):
                recursive = True
            elif a in ("-1",):
                onecol = True
            elif a in ("-t",):
                sort_time = True
            elif a in ("-S",):
                sort_size = True
            elif a.startswith("--include="):
                includes.append(a.split("=", 1)[1])
            elif a.startswith("--exclude="):
                excludes.append(a.split("=", 1)[1])
            else:
                path = a
            i += 1
        try:
            if not os.path.exists(path):
                return ["ERROR", f"Path '{path}' does not exist"]

            def list_dir(p):
                items = []
                try:
                    for item in os.listdir(p):
                        if not show_all and item.startswith('.'):
                            continue
                        if not _include_exclude_filter(item, includes, excludes):
                            continue
                        items.append(item)
                except PermissionError:
                    pass
                return items

            def fmt_entry(base, name):
                full = os.path.join(base, name)
                try:
                    st = os.stat(full)
                except:
                    return name
                size = st.st_size
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                is_dir = "d" if os.path.isdir(full) else "-"
                perms = oct(st.st_mode)[-3:]
                if human:
                    units = ["B","K","M","G","T"]
                    s = float(size)
                    u = 0
                    while s >= 1024 and u < len(units)-1:
                        s /= 1024.0
                        u += 1
                    size_str = f"{s:.1f}{units[u]}"
                else:
                    size_str = str(size)
                return f"{is_dir}{perms} {size_str:>8} {mtime} {name}"

            def sort_key(base, name):
                full = os.path.join(base, name)
                try:
                    st = os.stat(full)
                    if sort_time:
                        return st.st_mtime
                    if sort_size:
                        return st.st_size
                except:
                    return 0
                return name.lower()

            out = []
            if recursive and os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    entries = list_dir(root)
                    if sort_time or sort_size:
                        entries.sort(key=lambda n: sort_key(root, n), reverse=(sort_time or sort_size))
                    else:
                        entries.sort()
                    out.append(f"{root}:")
                    if long_format:
                        for e in entries:
                            out.append(fmt_entry(root, e))
                    else:
                        out.append((" " if onecol else "  ").join(entries))
            else:
                entries = list_dir(path) if os.path.isdir(path) else [os.path.basename(path)]
                if sort_time or sort_size:
                    entries.sort(key=lambda n: sort_key(path if os.path.isdir(path) else os.path.dirname(path), n), reverse=(sort_time or sort_size))
                else:
                    entries.sort()
                if long_format:
                    result = [fmt_entry(path if os.path.isdir(path) else os.path.dirname(path), e) for e in entries]
                    return ["INFO", "\n".join(result)]
                else:
                    sep = " " if onecol else "  "
                    return ["INFO", sep.join(entries)]
            return ["INFO", "\n".join(out)]
        except Exception as e:
            return ["ERROR", str(e)]

class cd:
    @staticmethod
    def run(args):
        global current_dir, previous_dir
        if len(args) == 1:
            target = os.path.expanduser("~")
        else:
            target = args[1]
        if target == "-":
            target = previous_dir
        elif target == "..":
            target = os.path.dirname(current_dir)
        elif not os.path.isabs(target):
            target = os.path.join(current_dir, target)
        try:
            if not os.path.exists(target):
                return ["ERROR", f"Directory '{target}' does not exist"]
            if not os.path.isdir(target):
                return ["ERROR", f"'{target}' is not a directory"]
            previous_dir = current_dir
            os.chdir(target)
            current_dir = os.getcwd()
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class pwd:
    @staticmethod
    def run(args):
        return ["INFO", current_dir]

class cat:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "cat <file> [-n]")
        if validation:
            return validation
        number = "-n" in args
        files = [a for a in args[1:] if not a.startswith("-")]
        try:
            out = []
            for fp in files:
                if not os.path.exists(fp):
                    return ["ERROR", f"File '{fp}' does not exist"]
                if os.path.isdir(fp):
                    return ["ERROR", f"'{fp}' is a directory"]
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    if number:
                        for i, line in enumerate(f, 1):
                            out.append(f"{i:>6}\t{line.rstrip()}")
                    else:
                        out.append(f.read())
            return ["INFO", "\n".join(out)]
        except Exception as e:
            return ["ERROR", str(e)]

class echo:
    @staticmethod
    def run(args):
        if len(args) == 1:
            return ["INFO", ""]
        message = " ".join(args[1:])
        if len(args) > 2 and args[-2] == ">":
            filename = args[-1]
            message = " ".join(args[1:-2])
            try:
                with open(filename, 'w') as f:
                    f.write(message)
                return ["SUCCESS"]
            except Exception as e:
                return ["ERROR", str(e)]
        elif len(args) > 2 and args[-2] == ">>":
            filename = args[-1]
            message = " ".join(args[1:-2])
            try:
                with open(filename, 'a') as f:
                    f.write(message + "\n")
                return ["SUCCESS"]
            except Exception as e:
                return ["ERROR", str(e)]
        return ["INFO", message]

class touch:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "touch <file> [-c] [-m]")
        if validation:
            return validation
        no_create = "-c" in args
        touch_mtime = "-m" in args
        files = [a for a in args[1:] if not a.startswith("-")]
        try:
            for fp in files:
                if os.path.exists(fp):
                    now = time.time()
                    if touch_mtime:
                        os.utime(fp, (now, now))
                    else:
                        os.utime(fp, None)
                else:
                    if not no_create:
                        with open(fp, 'a'):
                            pass
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class cp:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "cp <source> <destination> [-r] [-n] [-u]")
        if validation:
            return validation
        recursive = "-r" in args
        noclobber = "-n" in args
        update_only = "-u" in args
        files = [a for a in args[1:] if not a.startswith("-")]
        src, dst = files[0], files[1]
        try:
            if not os.path.exists(src):
                return ["ERROR", f"Source '{src}' does not exist"]
            if os.path.isdir(src):
                if not recursive:
                    return ["ERROR", "use -r to copy directories"]
                if os.path.exists(dst) and noclobber:
                    return ["WARNING", "destination exists, skipped"]
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                if os.path.isdir(dst):
                    dst = os.path.join(dst, os.path.basename(src))
                if os.path.exists(dst) and noclobber:
                    return ["WARNING", "destination exists, skipped"]
                if update_only and os.path.exists(dst):
                    if os.path.getmtime(dst) >= os.path.getmtime(src):
                        return ["WARNING", "destination newer or same, skipped"]
                shutil.copy2(src, dst)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class mv:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "mv <source> <destination> [-n] [-f]")
        if validation:
            return validation
        noclobber = "-n" in args
        force = "-f" in args
        files = [a for a in args[1:] if not a.startswith("-")]
        src, dst = files[0], files[1]
        try:
            if not os.path.exists(src):
                return ["ERROR", f"Source '{src}' does not exist"]
            if os.path.exists(dst) and noclobber and not force:
                return ["WARNING", "destination exists, skipped"]
            shutil.move(src, dst)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class rm:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "rm <file/directory> [-r] [-f] [-i] [-v]")
        if validation:
            return validation
        recursive = "-r" in args or "-rf" in args
        force = "-f" in args or "-rf" in args
        interactive = "-i" in args
        verbose = "-v" in args
        files = [arg for arg in args[1:] if not arg.startswith('-')]
        msgs = []
        for file_path in files:
            try:
                if not os.path.exists(file_path):
                    if not force:
                        return ["ERROR", f"'{file_path}' does not exist"]
                    continue
                if interactive and not force:
                    pass
                if os.path.isdir(file_path):
                    if recursive:
                        shutil.rmtree(file_path)
                        if verbose:
                            msgs.append(f"removed directory '{file_path}'")
                    else:
                        return ["ERROR", f"'{file_path}' is a directory, use -r flag"]
                else:
                    os.remove(file_path)
                    if verbose:
                        msgs.append(f"removed '{file_path}'")
            except Exception as e:
                if not force:
                    return ["ERROR", str(e)]
        if verbose and msgs:
            return ["INFO", "\n".join(msgs)]
        return ["SUCCESS"]

class find:
    @staticmethod
    def run(args):
        if len(args) < 2:
            return ["WARNING", "Usage: find <path> [-name pattern] [-type f|d] [-maxdepth n]"]
        search_path = args[1] if os.path.exists(args[1]) else "."
        pattern = "*"
        ftype = None
        maxdepth = None
        if "-name" in args:
            name_idx = args.index("-name")
            if name_idx + 1 < len(args):
                pattern = args[name_idx + 1]
        if "-type" in args:
            t_idx = args.index("-type")
            if t_idx + 1 < len(args):
                ftype = args[t_idx + 1]
        if "-maxdepth" in args:
            d_idx = args.index("-maxdepth")
            if d_idx + 1 < len(args):
                try:
                    maxdepth = int(args[d_idx + 1])
                except:
                    return ["ERROR", "invalid max depth"]
        try:
            results = []
            base_depth = Path(search_path).parts.__len__()
            for root, dirs, files in os.walk(search_path):
                depth = Path(root).parts.__len__() - base_depth
                if maxdepth is not None and depth > maxdepth:
                    dirs[:] = []
                    continue
                names = files + dirs
                for name in names:
                    full = os.path.join(root, name)
                    if not glob.fnmatch.fnmatch(name, pattern):
                        continue
                    if ftype == "f" and not os.path.isfile(full):
                        continue
                    if ftype == "d" and not os.path.isdir(full):
                        continue
                    results.append(full)
            return ["INFO", "\n".join(results) if results else "No files found"]
        except Exception as e:
            return ["ERROR", str(e)]

class grep:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "grep <pattern> <file|dir> [-i] [-n] [-r] [-E]")
        if validation:
            return validation
        ignore = "-i" in args
        show_line = "-n" in args
        recursive = "-r" in args
        extended = "-E" in args
        pattern = args[1]
        target = args[2]
        try:
            flags = re.IGNORECASE if ignore else 0
            regex = re.compile(pattern, flags)
            results = []
            def scan_file(fp):
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                if show_line:
                                    results.append(f"{fp}:{i}: {line.rstrip()}")
                                else:
                                    results.append(f"{fp}: {line.rstrip()}")
                except:
                    pass
            if os.path.isdir(target):
                if not recursive:
                    return ["ERROR", "target is a directory, use -r"]
                for root, dirs, files in os.walk(target):
                    for fn in files:
                        scan_file(os.path.join(root, fn))
            else:
                scan_file(target)
            return ["INFO", "\n".join(results) if results else "No matches found"]
        except Exception as e:
            return ["ERROR", str(e)]

class wc:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "wc <file>")
        if validation:
            return validation
        try:
            if not os.path.exists(args[1]):
                return ["ERROR", f"File '{args[1]}' does not exist"]
            with open(args[1], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = len(content.splitlines())
                words = len(content.split())
                chars = len(content)
                return ["INFO", f"{lines:>8} {words:>8} {chars:>8} {args[1]}"]
        except Exception as e:
            return ["ERROR", str(e)]

class head:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "head <file> [-n lines]")
        if validation:
            return validation
        lines_count = 10
        if "-n" in args:
            n_idx = args.index("-n")
            if n_idx + 1 < len(args):
                try:
                    lines_count = int(args[n_idx + 1])
                except ValueError:
                    return ["ERROR", "Invalid number of lines"]
        try:
            if not os.path.exists(args[1]):
                return ["ERROR", f"File '{args[1]}' does not exist"]
            with open(args[1], 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[:lines_count]
                return ["INFO", "".join(lines)]
        except Exception as e:
            return ["ERROR", str(e)]

class tail:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "tail <file> [-n lines] [-f]")
        if validation:
            return validation
        lines_count = 10
        follow = "-f" in args
        if "-n" in args:
            n_idx = args.index("-n")
            if n_idx + 1 < len(args):
                try:
                    lines_count = int(args[n_idx + 1])
                except ValueError:
                    return ["ERROR", "Invalid number of lines"]
        try:
            if not os.path.exists(args[1]):
                return ["ERROR", f"File '{args[1]}' does not exist"]
            with open(args[1], 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-lines_count:]
                out = "".join(lines)
            if follow:
                # simple bounded follow so it doesn't run forever
                try:
                    with open(args[1], 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(0, os.SEEK_END)
                        start = time.time()
                        while time.time() - start < 5:
                            chunk = f.read()
                            if chunk:
                                out += chunk
                            time.sleep(0.2)
                except:
                    pass
            return ["INFO", out]
        except Exception as e:
            return ["ERROR", str(e)]

class chmod:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "chmod <mode> <file> [-R]")
        if validation:
            return validation
        recursive = "-R" in args
        try:
            mode = int(args[1], 8)
            targets = [a for a in args[2:] if not a.startswith("-")]
            for t in targets:
                if recursive and os.path.isdir(t):
                    for root, dirs, files in os.walk(t):
                        for name in dirs + files:
                            os.chmod(os.path.join(root, name), mode)
                os.chmod(t, mode)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class ps:
    @staticmethod
    def run(args):
        try:
            limit = 50
            out = []
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    out.append(f"{proc.info['pid']:>8} {proc.info.get('username',''):<15} {proc.info['name']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return ["INFO", "\n".join(out[:limit])]
        except Exception as e:
            return ["ERROR", str(e)]

class kill:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "kill <pid>")
        if validation:
            return validation
        try:
            pid = int(args[1])
            os.kill(pid, 15)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class killall:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "killall <name>")
        if validation:
            return validation
        name = args[1].lower()
        killed = 0
        for p in psutil.process_iter(['pid','name']):
            try:
                if p.info['name'] and name in p.info['name'].lower():
                    os.kill(p.info['pid'], 15)
                    killed += 1
            except:
                pass
        return ["INFO", f"killed {killed}"]

class date:
    @staticmethod
    def run(args):
        if len(args) > 1 and args[1].startswith("+"):
            fmt = args[1][1:]
            try:
                return ["INFO", time.strftime(fmt)]
            except:
                return ["ERROR", "invalid format"]
        return ["INFO", time.strftime("%Y-%m-%d %H:%M:%S")]

class whoami:
    @staticmethod
    def run(args):
        try:
            return ["INFO", os.getlogin()]
        except:
            u = getpass.getuser() or os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
            return ["INFO", u]

class uname:
    @staticmethod
    def run(args):
        system_info = f"{platform.system()} {platform.release()} {platform.machine()}"
        return ["INFO", system_info]

class df:
    @staticmethod
    def run(args):
        try:
            usage = shutil.disk_usage('/')
            total = usage.total
            used = usage.total - usage.free
            free = usage.free
            def humanize(b):
                units = ["B","K","M","G","T"]
                s = float(b)
                u = 0
                while s >= 1024 and u < len(units)-1:
                    s /= 1024.0
                    u += 1
                return f"{s:.1f}{units[u]}"
            return ["INFO", f"Total: {humanize(total)}, Used: {humanize(used)}, Free: {humanize(free)}"]
        except Exception as e:
            return ["ERROR", str(e)]

class du:
    @staticmethod
    def run(args):
        path = args[1] if len(args) > 1 and not args[1].startswith("-") else "."
        maxdepth = None
        if "--max-depth" in args:
            i = args.index("--max-depth")
            if i + 1 < len(args):
                try:
                    maxdepth = int(args[i+1])
                except:
                    return ["ERROR", "invalid depth"]
        try:
            base = Path(path)
            total_size = 0
            lines = []
            for dirpath, dirnames, filenames in os.walk(path):
                depth = Path(dirpath).relative_to(base).parts.__len__() if Path(dirpath) != base else 0
                if maxdepth is not None and depth > maxdepth:
                    dirnames[:] = []
                    continue
                size_here = 0
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        size_here += os.path.getsize(filepath)
                    except OSError:
                        pass
                total_size += size_here
                lines.append(f"{size_here/(1024*1024):.2f}MB\t{dirpath}")
            lines.append(f"{total_size/(1024*1024):.2f}MB\ttotal")
            return ["INFO", "\n".join(lines)]
        except Exception as e:
            return ["ERROR", str(e)]

class history:
    @staticmethod
    def run(args):
        n = 20
        if "-c" in args:
            command_history.clear()
            return ["SUCCESS"]
        if "-n" in args:
            i = args.index("-n")
            if i + 1 < len(args):
                try:
                    n = int(args[i+1])
                except:
                    return ["ERROR", "invalid number"]
        return ["INFO", "\n".join(f"{i+1}: {cmd}" for i, cmd in enumerate(command_history[-n:]))]

class which:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "which <command>")
        if validation:
            return validation
        command = args[1]
        path = shutil.which(command)
        return ["INFO", path if path else f"Command '{command}' not found"]

class tree:
    @staticmethod
    def run(args):
        path = "."
        includes = []
        excludes = []
        maxdepth = None
        for a in args[1:]:
            if a.startswith("--include="):
                includes.append(a.split("=",1)[1])
            elif a.startswith("--exclude="):
                excludes.append(a.split("=",1)[1])
            elif a.startswith("--max-depth="):
                try:
                    maxdepth = int(a.split("=",1)[1])
                except:
                    return ["ERROR", "invalid max depth"]
            else:
                path = a
        def build_tree(directory, prefix="", depth=0):
            items = []
            try:
                entries = sorted(os.listdir(directory))
                filtered = []
                for entry in entries:
                    if entry.startswith('.'):
                        continue
                    if not _include_exclude_filter(entry, includes, excludes):
                        continue
                    filtered.append(entry)
                for i, entry in enumerate(filtered):
                    entry_path = os.path.join(directory, entry)
                    is_last = i == len(filtered) - 1
                    current_prefix = "└── " if is_last else "├── "
                    items.append(f"{prefix}{current_prefix}{entry}")
                    if os.path.isdir(entry_path):
                        if maxdepth is not None and depth + 1 >= maxdepth:
                            continue
                        extension = "    " if is_last else "│   "
                        items.extend(build_tree(entry_path, prefix + extension, depth + 1))
            except PermissionError:
                pass
            return items
        try:
            tree_lines = [path] + build_tree(path)
            return ["INFO", "\n".join(tree_lines)]
        except Exception as e:
            return ["ERROR", str(e)]

class help_cmd:
    @staticmethod
    def run(args):
        help_text = """
available commands
 file & directory:
   ls/dir         - list directory contents (flags: -a -l -h -R -1 -t -S --include= --exclude=)
   cd             - change directory (cd -, cd ..)
   pwd            - show current directory
   mkdir          - create directory [-m 755]
   rmdir          - remove empty directory
   rm/del         - remove files/directories [-r] [-f] [-i] [-v]
   cp/copy        - copy files/directories [-r] [-n] [-u]
   mv/move        - move/rename files [-n] [-f]
   find           - search for files [-name] [-type f|d] [-maxdepth]
   tree           - directory tree [--include=] [--exclude=] [--max-depth=]
   touch          - create file or update timestamp [-c] [-m]
   stat           - file info
   basename       - basename of path
   dirname        - dirname of path
   zip/unzip      - zip or unzip files
   tar/untar      - tar or untar archives

 text:
   cat/type       - display file contents [-n]
   head           - show first lines [-n]
   tail           - show last lines [-n] [-f]
   wc             - count lines, words, chars
   grep           - search text [-i] [-n] [-r] [-E]
   sort           - sort lines [-r] [-n] [-u]
   uniq           - unique lines [-c]
   split          - split file [-l N] <file> <prefix>
   replace        - replace text in file (replace <file> <pattern> <replacement> [--regex] [--in-place])
   json           - json helper (json <file> [--get a.b] [--set a.b=value] [--pretty])

 system:
   ps             - list processes
   kill           - kill by pid
   killall/pkill  - kill by name
   date           - show date/time or format with +FMT
   whoami         - show current user
   uname          - system info
   df             - disk usage
   du             - directory size [--max-depth N]
   free           - memory usage
   uptime         - system uptime
   hostname       - host name

 network:
   ping           - ping a host
   wget           - download a url [output]
   curl           - fetch a url [-o file]
   ip             - show addresses
   netstat        - connections
   dns/nslookup   - resolve name
   blush-transfer - send files

 utils:
   echo           - print text
   clear/cls      - clear screen
   history/hist   - show history [-n N] [-c]
   which          - locate command
   sleep          - sleep seconds
   seq            - generate sequence
   calc           - evaluate math
   base64/b64     - encode/decode (base64 encode|decode <in> [out])
   checksum       - file checksum [--algo md5|sha1|sha256]
   alias          - list/add alias (alias name=command)
   unalias        - remove alias
   env            - environment vars [filter]
   export/set     - set env VAR=value
   unset          - unset env var
   help           - this help
   exit/quit      - exit shell

 use '!' prefix to run system commands directly.
        """
        return ["INFO", help_text.strip()]

class exit_cmd:
    @staticmethod
    def run(args):
        return "$C_EXIT"

class export:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "export <VAR=value>")
        if validation:
            return validation
        try:
            if "=" in args[1]:
                var, value = args[1].split("=", 1)
                os.environ[var] = value
                return ["SUCCESS"]
            else:
                return ["ERROR", "invalid format. use VAR=value"]
        except Exception as e:
            return ["ERROR", str(e)]

class unset:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "unset <VAR>")
        if validation:
            return validation
        var = args[1]
        if var in os.environ:
            del os.environ[var]
            return ["SUCCESS"]
        return ["WARNING", "variable not set"]

class env:
    @staticmethod
    def run(args):
        env_vars = []
        filt = args[1] if len(args) > 1 else None
        for key, value in sorted(os.environ.items()):
            if filt and filt.lower() not in key.lower():
                continue
            env_vars.append(f"{key}={value}")
        return ["INFO", "\n".join(env_vars)]

class ping:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "ping <host> [-c N]")
        if validation:
            return validation
        host = args[1]
        count = 4
        if "-c" in args:
            c_idx = args.index("-c")
            if c_idx + 1 < len(args):
                try:
                    count = int(args[c_idx + 1])
                except ValueError:
                    return ["ERROR", "Invalid count value"]
        try:
            if platform.system().lower() == "windows":
                result = subprocess.run(["ping", "-n", str(count), host],
                                        capture_output=True, text=True, timeout=30)
            else:
                result = subprocess.run(["ping", "-c", str(count), host],
                                        capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return ["INFO", result.stdout]
            else:
                return ["ERROR", f"Ping failed: {result.stderr}"]
        except subprocess.TimeoutExpired:
            return ["ERROR", "Ping timeout"]
        except Exception as e:
            return ["ERROR", str(e)]

class wget:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "wget <url> [output_file]")
        if validation:
            return validation
        url = args[1]
        output_file = args[2] if len(args) > 2 else None
        try:
            import urllib.request
            if output_file:
                urllib.request.urlretrieve(url, output_file)
                return ["SUCCESS", f"Downloaded to {output_file}"]
            else:
                filename = url.split("/")[-1] or "index.html"
                urllib.request.urlretrieve(url, filename)
                return ["SUCCESS", f"Downloaded to {filename}"]
        except Exception as e:
            return ["ERROR", str(e)]

class curl:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "curl <url> [-o file]")
        if validation:
            return validation
        url = args[1]
        output_file = None
        if "-o" in args:
            o_idx = args.index("-o")
            if o_idx + 1 < len(args):
                output_file = args[o_idx + 1]
        try:
            import urllib.request
            with urllib.request.urlopen(url) as response:
                content = response.read().decode('utf-8', errors='ignore')
                if output_file:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return ["SUCCESS", f"Content saved to {output_file}"]
                else:
                    return ["INFO", content[:1000] + "..." if len(content) > 1000 else content]
        except Exception as e:
            return ["ERROR", str(e)]

class free:
    @staticmethod
    def run(args):
        try:
            v = psutil.virtual_memory()
            s = psutil.swap_memory()
            def h(b):
                units = ["B","K","M","G","T"]
                s = float(b)
                u = 0
                while s >= 1024 and u < len(units)-1:
                    s /= 1024.0
                    u += 1
                return f"{s:.1f}{units[u]}"
            out = []
            out.append(f"mem: total {h(v.total)} used {h(v.used)} free {h(v.available)}")
            out.append(f"swap: total {h(s.total)} used {h(s.used)} free {h(s.free)}")
            return ["INFO", "\n".join(out)]
        except Exception as e:
            return ["ERROR", str(e)]

class uptime:
    @staticmethod
    def run(args):
        try:
            bt = psutil.boot_time()
            up = int(time.time() - bt)
            days = up // 86400
            up %= 86400
            hrs = up // 3600
            up %= 3600
            mins = up // 60
            secs = up % 60
            return ["INFO", f"{days}d {hrs}h {mins}m {secs}s"]
        except Exception as e:
            return ["ERROR", str(e)]

class hostname:
    @staticmethod
    def run(args):
        try:
            return ["INFO", socket.gethostname()]
        except Exception as e:
            return ["ERROR", str(e)]

class ip:
    @staticmethod
    def run(args):
        try:
            out = []
            for name, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET:
                        out.append(f"{name}: {a.address}")
            return ["INFO", "\n".join(out) if out else "no ipv4 addresses"]
        except Exception as e:
            return ["ERROR", str(e)]

class netstat:
    @staticmethod
    def run(args):
        try:
            conns = psutil.net_connections(kind='inet')
            out = []
            for c in conns[:200]:
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                out.append(f"{c.status:<13} {laddr:<22} {raddr:<22} {c.pid or ''}")
            return ["INFO", "\n".join(out) if out else "no connections"]
        except Exception as e:
            return ["ERROR", str(e)]

class dns:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "dns <name>")
        if validation:
            return validation
        try:
            name = args[1]
            host, aliases, addrs = socket.gethostbyname_ex(name)
            lines = [f"host: {host}", f"aliases: {', '.join(aliases) if aliases else '-'}", f"addrs: {', '.join(addrs) if addrs else '-'}"]
            return ["INFO", "\n".join(lines)]
        except Exception as e:
            return ["ERROR", str(e)]

class nslookup:
    @staticmethod
    def run(args):
        return dns.run(args)

class zip_cmd:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "zip <input file/dir> <output.zip>")
        if validation:
            return validation
        src = args[1]
        out = args[2]
        try:
            if os.path.isdir(src):
                with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
                    for root, dirs, files in os.walk(src):
                        for f in files:
                            full = os.path.join(root, f)
                            arc = os.path.relpath(full, start=os.path.dirname(src))
                            z.write(full, arc)
            else:
                with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
                    z.write(src, os.path.basename(src))
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class unzip:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "unzip <archive.zip> [dest]")
        if validation:
            return validation
        src = args[1]
        dest = args[2] if len(args) > 2 else "."
        try:
            with zipfile.ZipFile(src, 'r') as z:
                z.extractall(dest)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class tar:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "tar <input file/dir> <output.tar.gz>")
        if validation:
            return validation
        src = args[1]
        out = args[2]
        try:
            mode = "w:gz" if out.endswith(".gz") or out.endswith(".tgz") else "w"
            with tarfile.open(out, mode) as t:
                t.add(src, arcname=os.path.basename(src))
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class untar:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "untar <archive.tar[.gz]> [dest]")
        if validation:
            return validation
        src = args[1]
        dest = args[2] if len(args) > 2 else "."
        try:
            with tarfile.open(src, 'r:*') as t:
                t.extractall(dest)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class checksum:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "checksum <file> [--algo md5|sha1|sha256]")
        if validation:
            return validation
        algo = "sha256"
        if "--algo" in args:
            i = args.index("--algo")
            if i + 1 < len(args):
                algo = args[i+1].lower()
        algomap = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256}
        if algo not in algomap:
            return ["ERROR", "unsupported algo"]
        fp = args[1]
        if not os.path.isfile(fp):
            return ["ERROR", "file not found"]
        h = algomap[algo]()
        try:
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return ["INFO", f"{h.hexdigest()}  {fp}"]
        except Exception as e:
            return ["ERROR", str(e)]

class md5sum:
    @staticmethod
    def run(args):
        return checksum.run(args + ["--algo", "md5"])

class sha1sum:
    @staticmethod
    def run(args):
        return checksum.run(args + ["--algo", "sha1"])

class sha256sum:
    @staticmethod
    def run(args):
        return checksum.run(args + ["--algo", "sha256"])

class base64_cmd:
    @staticmethod
    def run(args):
        validation = validate_args(args, 3, "base64 encode|decode <in> [out]")
        if validation:
            return validation
        mode = args[1]
        inf = args[2]
        outf = args[3] if len(args) > 3 else None
        try:
            if mode == "encode":
                with open(inf, "rb") as f:
                    data = f.read()
                b = base64.b64encode(data)
                if outf:
                    with open(outf, "wb") as o:
                        o.write(b)
                    return ["SUCCESS"]
                return ["INFO", b.decode("ascii")]
            elif mode == "decode":
                with open(inf, "rb") as f:
                    data = f.read()
                b = base64.b64decode(data)
                if outf:
                    with open(outf, "wb") as o:
                        o.write(b)
                    return ["SUCCESS"]
                return ["INFO", b.decode("utf-8", errors="ignore")]
            else:
                return ["ERROR", "use encode or decode"]
        except Exception as e:
            return ["ERROR", str(e)]

class b64:
    @staticmethod
    def run(args):
        return base64_cmd.run(args)

class json_cmd:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "json <file> [--get a.b] [--set a.b=value] [--pretty]")
        if validation:
            return validation
        fp = args[1]
        if not os.path.isfile(fp):
            return ["ERROR", "file not found"]
        get_key = None
        set_spec = None
        pretty = "--pretty" in args
        if "--get" in args:
            i = args.index("--get")
            if i + 1 < len(args):
                get_key = args[i+1]
        if "--set" in args:
            i = args.index("--set")
            if i + 1 < len(args):
                set_spec = args[i+1]
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if get_key:
                cur = data
                for part in get_key.split("."):
                    if isinstance(cur, list):
                        idx = int(part)
                        cur = cur[idx]
                    else:
                        cur = cur.get(part)
                return ["INFO", json.dumps(cur, indent=2) if pretty else json.dumps(cur)]
            if set_spec:
                path, val = set_spec.split("=", 1)
                try:
                    val_json = json.loads(val)
                except:
                    val_json = val
                cur = data
                parts = path.split(".")
                for part in parts[:-1]:
                    if part not in cur or not isinstance(cur[part], (dict, list)):
                        cur[part] = {}
                    cur = cur[part]
                cur[parts[-1]] = val_json
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2 if pretty else None)
                return ["SUCCESS"]
            return ["INFO", json.dumps(data, indent=2) if pretty else json.dumps(data)]
        except Exception as e:
            return ["ERROR", str(e)]

class replace:
    @staticmethod
    def run(args):
        validation = validate_args(args, 4, "replace <file> <pattern> <replacement> [--regex] [--in-place]")
        if validation:
            return validation
        fp = args[1]
        pat = args[2]
        repl = args[3]
        regex = "--regex" in args
        inplace = "--in-place" in args
        if not os.path.isfile(fp):
            return ["ERROR", "file not found"]
        try:
            with open(fp, "r", encoding="utf-8", errors='ignore') as f:
                s = f.read()
            if regex:
                s2 = re.sub(pat, repl, s)
            else:
                s2 = s.replace(pat, repl)
            if inplace:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(s2)
                return ["SUCCESS"]
            else:
                return ["INFO", s2]
        except Exception as e:
            return ["ERROR", str(e)]

class sort:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "sort <file> [-r] [-n] [-u]")
        if validation:
            return validation
        reverse = "-r" in args
        numeric = "-n" in args
        unique = "-u" in args
        fp = args[1]
        try:
            with open(fp, "r", encoding="utf-8", errors='ignore') as f:
                lines = [l.rstrip("\n") for l in f]
            if numeric:
                def key(x):
                    try:
                        return float(x.strip().split()[0])
                    except:
                        return 0.0
                lines.sort(key=key, reverse=reverse)
            else:
                lines.sort(reverse=reverse)
            if unique:
                seen = set()
                new = []
                for l in lines:
                    if l not in seen:
                        seen.add(l)
                        new.append(l)
                lines = new
            return ["INFO", "\n".join(lines)]
        except Exception as e:
            return ["ERROR", str(e)]

class uniq:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "uniq <file> [-c]")
        if validation:
            return validation
        count = "-c" in args
        fp = args[1]
        try:
            with open(fp, "r", encoding="utf-8", errors='ignore') as f:
                prev = None
                c = 0
                out = []
                for line in f:
                    line = line.rstrip("\n")
                    if prev is None:
                        prev = line
                        c = 1
                    elif line == prev:
                        c += 1
                    else:
                        out.append(f"{c:>6} {prev}" if count else prev)
                        prev = line
                        c = 1
                if prev is not None:
                    out.append(f"{c:>6} {prev}" if count else prev)
            return ["INFO", "\n".join(out)]
        except Exception as e:
            return ["ERROR", str(e)]

class split:
    @staticmethod
    def run(args):
        validation = validate_args(args, 4, "split -l N <file> <prefix>")
        if validation:
            return validation
        if args[1] != "-l":
            return ["ERROR", "use -l N"]
        try:
            n = int(args[2])
        except:
            return ["ERROR", "invalid N"]
        fp = args[3]
        prefix = args[4] if len(args) > 4 else "x"
        try:
            with open(fp, "r", encoding="utf-8", errors='ignore') as f:
                part = 0
                lines = []
                for line in f:
                    lines.append(line)
                    if len(lines) >= n:
                        with open(f"{prefix}{part:02d}", "w", encoding="utf-8") as o:
                            o.writelines(lines)
                        lines = []
                        part += 1
                if lines:
                    with open(f"{prefix}{part:02d}", "w", encoding="utf-8") as o:
                        o.writelines(lines)
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class sleep:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "sleep <seconds>")
        if validation:
            return validation
        try:
            sec = float(args[1])
            time.sleep(min(sec, 5.0))
            return ["SUCCESS"]
        except Exception as e:
            return ["ERROR", str(e)]

class seq:
    @staticmethod
    def run(args):
        start = 1
        end = None
        step = 1
        nums = [a for a in args[1:] if not a.startswith("-")]
        try:
            if len(nums) == 1:
                end = int(nums[0])
            elif len(nums) == 2:
                start = int(nums[0])
                end = int(nums[1])
            elif len(nums) >= 3:
                start = int(nums[0])
                step = int(nums[1])
                end = int(nums[2])
            else:
                return ["WARNING", "Usage: seq <end> | seq <start> <end> | seq <start> <step> <end>"]
            out = []
            i = start
            if step == 0:
                return ["ERROR", "step cannot be 0"]
            if step > 0:
                while i <= end:
                    out.append(str(i))
                    i += step
            else:
                while i >= end:
                    out.append(str(i))
                    i += step
            return ["INFO", "\n".join(out)]
        except Exception as e:
            return ["ERROR", str(e)]

class calc:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "calc <expression>")
        if validation:
            return validation
        expr = " ".join(args[1:])
        try:
            import ast, operator as op
            ops = {
                ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
                ast.Mod: op.mod, ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos,
                ast.FloorDiv: op.floordiv
            }
            def eval_(node):
                if isinstance(node, ast.Num):
                    return node.n
                if isinstance(node, ast.BinOp):
                    return ops[type(node.op)](eval_(node.left), eval_(node.right))
                if isinstance(node, ast.UnaryOp):
                    return ops[type(node.op)](eval_(node.operand))
                raise ValueError("unsupported")
            node = ast.parse(expr, mode='eval')
            val = eval_((node.body))
            return ["INFO", str(val)]
        except Exception as e:
            return ["ERROR", "invalid expression"]

class stat:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "stat <path>")
        if validation:
            return validation
        p = args[1]
        try:
            st = os.stat(p)
            is_dir = os.path.isdir(p)
            perms = statmod.filemode(st.st_mode)
            out = []
            out.append(f"path: {p}")
            out.append(f"type: {'dir' if is_dir else 'file'}")
            out.append(f"size: {st.st_size}")
            out.append(f"mode: {perms}")
            out.append(f"mtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}")
            out.append(f"atime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_atime))}")
            out.append(f"ctime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_ctime))}")
            return ["INFO", "\n".join(out)]
        except Exception as e:
            return ["ERROR", str(e)]

class basename:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "basename <path>")
        if validation:
            return validation
        return ["INFO", os.path.basename(args[1])]

class dirname:
    @staticmethod
    def run(args):
        validation = validate_args(args, 2, "dirname <path>")
        if validation:
            return validation
        return ["INFO", os.path.dirname(args[1])]

class ssf:
    @staticmethod
    def run(args=None):
        if args is None:
            args = []
        from main import get_prefixes
        prefixes = get_prefixes()
        
        RESET = '\033[0m'
        BOLD = '\033[1m'
        
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        MAGENTA = '\033[95m'
        BLUE = '\033[94m'
        RED = '\033[91m'
        WHITE = '\033[97m'
        GRAY = '\033[90m'
        
        BG_CYAN = '\033[46m'
        BG_GREEN = '\033[42m'
        BG_MAGENTA = '\033[45m'
        BG_BLUE = '\033[44m'
        
        print(f"{prefixes['think_prefix']} Fetching System Specifications", end='', flush=True)

        import platform, psutil, sys, socket, os, time, subprocess, requests

        def get_all_gpus():
            gpus = []
            try:
                if platform.system() == "Windows":
                    cmd = ['powershell', '-Command',
                           "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, CurrentRefreshRate, DriverVersion, Status"]
                    output = subprocess.check_output(cmd, text=True).strip()
                    current_gpu = {}
                    for line in output.split('\n'):
                        line = line.strip()
                        if line.startswith('Name'):
                            if current_gpu:
                                gpus.append(current_gpu)
                            name = line.split(':', 1)[1].strip() if ':' in line else ''
                            current_gpu = {'name': name, 'vram': '', 'driver': '', 'status': ''}
                        elif line.startswith('AdapterRAM'):
                            if current_gpu:
                                try:
                                    ram = line.split(':', 1)[1].strip() if ':' in line else '0'
                                    if ram and ram != '0':
                                        ram_int = int(ram)
                                        # spróbuj tak: jeśli ram_int jest podejrzanie małe, to pomnóż
                                        if ram_int < 1e9:
                                            # wtedy prawdopodobnie jest w bajtach, dzielimy na MB, potem na GB
                                            ram_gb = ram_int / (1024**2) / 1024
                                        else:
                                            ram_gb = ram_int / (1024**3)
                                        current_gpu['vram'] = f"{ram_gb:.1f} GB"
                                except:
                                    pass
                        elif line.startswith('DriverVersion'):
                            if current_gpu:
                                current_gpu['driver'] = line.split(':', 1)[1].strip() if ':' in line else ''
                        elif line.startswith('Status'):
                            if current_gpu:
                                current_gpu['status'] = line.split(':', 1)[1].strip() if ':' in line else ''
                    if current_gpu:
                        gpus.append(current_gpu)
                    
                    dedicated_gpus = []
                    integrated_gpus = []
                    for gpu in gpus:
                        name_lower = gpu['name'].lower()
                        if any(x in name_lower for x in ['nvidia', 'geforce', 'rtx', 'gtx', 'radeon rx', 'arc']):
                            dedicated_gpus.append(gpu)
                        elif gpu['name'] and gpu['name'] != 'N/A':
                            integrated_gpus.append(gpu)
                    
                    return dedicated_gpus if dedicated_gpus else integrated_gpus
                else:
                    return []
            except Exception:
                return []

        def get_cpu_expanded():
            info = []
            try:
                if platform.system() == "Windows":
                    import wmi
                    c = wmi.WMI()
                    for cpu in c.Win32_Processor():
                        info.append(("Name", cpu.Name))
                        info.append(("Manufacturer", cpu.Manufacturer))
                        info.append(("Number of Cores", cpu.NumberOfCores))
                        info.append(("Number of Logical Threads", cpu.NumberOfLogicalProcessors))
                        info.append(("Max Clock Speed", f"{cpu.MaxClockSpeed} MHz"))
                        info.append(("L2 Cache Size", f"{cpu.L2CacheSize} KB"))
                        info.append(("L3 Cache Size", f"{cpu.L3CacheSize} KB"))
                else:
                    info.append(("Processor", platform.processor()))
                    info.append(("CPU Count (Logical)", psutil.cpu_count(logical=True)))
                    info.append(("CPU Count (Physical)", psutil.cpu_count(logical=False)))
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        info.append(("Current Frequency", f"{cpu_freq.current:.2f} MHz"))
                        info.append(("Min Frequency", f"{cpu_freq.min:.2f} MHz"))
                        info.append(("Max Frequency", f"{cpu_freq.max:.2f} MHz"))
                    info.append(("CPU Percent per CPU", psutil.cpu_percent(interval=1, percpu=True)))
            except Exception:
                info.append(("CPU Expanded Info Not Available", ""))
            return info

        def get_memory_expanded():
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            return [
                ("Total", f"{vm.total // (1024**2)} MB"),
                ("Available", f"{vm.available // (1024**2)} MB"),
                ("Used", f"{vm.used // (1024**2)} MB"),
                ("Percentage Used", f"{vm.percent}%"),
                ("Swap Total", f"{sm.total // (1024**2)} MB"),
                ("Swap Used", f"{sm.used // (1024**2)} MB"),
                ("Swap Free", f"{sm.free // (1024**2)} MB"),
                ("Swap Percent", f"{sm.percent}%")
            ]

        def get_disk_expanded():
            partitions = psutil.disk_partitions()
            result = []
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    result.append((
                        f"{p.device}",
                        [
                            ("FS", p.fstype),
                            ("Total", f"{usage.total // (1024**3)} GB"),
                            ("Used", f"{usage.used // (1024**3)} GB"),
                            ("Free", f"{usage.free // (1024**3)} GB"),
                            ("Use%", f"{usage.percent}%")
                        ]
                    ))
                except Exception:
                    continue
            return result

        def get_network_expanded():
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            io = psutil.net_io_counters(pernic=True)
            result = []
            
            for iface, addrs_list in addrs.items():
                if iface in stats and stats[iface].isup:
                    iface_data = []
                    s = stats[iface]
                    iface_data.append(("Status", "Active"))
                    iface_data.append(("Speed", f"{s.speed} Mbps"))
                    
                    for addr in addrs_list:
                        if addr.family.name == 'AF_INET':
                            iface_data.append(("IPv4", addr.address))
                        elif addr.family.name == 'AF_INET6':
                            iface_data.append(("IPv6", addr.address))
                    
                    if iface in io:
                        io_counters = io[iface]
                        sent_mb = io_counters.bytes_sent / (1024**2)
                        recv_mb = io_counters.bytes_recv / (1024**2)
                        iface_data.append(("Data Sent", f"{sent_mb:.2f} MB"))
                        iface_data.append(("Data Received", f"{recv_mb:.2f} MB"))
                    
                    result.append((iface, iface_data))
            return result

        def get_system_expanded():
            uptime_sec = int(time.time() - psutil.boot_time())
            hours = uptime_sec // 3600
            minutes = (uptime_sec // 60) % 60
            seconds = uptime_sec % 60
            
            version_info = platform.version()
            short_version = version_info.split('.')[2] if len(version_info.split('.')) > 2 else version_info
            
            return [
                ("System", platform.system()),
                ("Node", platform.node()),
                ("Release", f"Windows {platform.release()}"),
                ("Build", short_version),
                ("Architecture", platform.machine()),
                ("Boot Time", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(psutil.boot_time()))),
                ("Uptime", f"{hours}h {minutes}m {seconds}s"),
                ("User", os.getlogin()),
            ]

        def get_real_ip():
            try:
                resp = requests.get("https://api.ipify.org", timeout=5)
                if resp.status_code == 200:
                    return resp.text.strip()
            except Exception:
                return "N/A"
            return "N/A"

        def print_header(title, emoji):
            print(f"\n{CYAN}{'─' * 60}{RESET}")
            print(f"{BOLD}{WHITE}[ {emoji} {title} ]{RESET}")
            print(f"{CYAN}{'─' * 60}{RESET}")

        def print_item(emoji, key, value, key_color=YELLOW, val_color=GREEN):
            print(f"[{emoji}] {key_color}{key:<28}{RESET}: {val_color}{value}{RESET}")

        expanded = '-ex' in args or '--expanded' in args

        cpu_name = 'Unknown Processor'
        try:
            if platform.system() == "Windows":
                import wmi
                c = wmi.WMI()
                processors = c.Win32_Processor()
                if processors and processors[0].Name:
                    cpu_name = processors[0].Name.strip()
            else:
                cpu_name = platform.processor() or 'Unknown Processor'
        except Exception:
            cpu_name = platform.processor() or 'Unknown Processor'

        total_memory_gb = psutil.virtual_memory().total / (1024**3)
        mem_used_gb = psutil.virtual_memory().used / (1024**3)
        mem_percent = psutil.virtual_memory().percent

        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_percent = disk.percent

        ip_addr_local = 'N/A'
        try:
            hostname = socket.gethostname()
            ip_addr_local = socket.gethostbyname(hostname)
        except Exception:
            pass

        gpus = get_all_gpus()
        gpu_display = gpus[0]['name'] if gpus else 'No GPU detected'

        print(f"\n{BOLD}{MAGENTA}╔══════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{MAGENTA}║{RESET}  {BOLD}{WHITE}                SYSTEM SPECIFICATIONS                 {RESET}  {BOLD}{MAGENTA}║{RESET}")
        print(f"{BOLD}{MAGENTA}╚══════════════════════════════════════════════════════════╝{RESET}")

        print(f"\n{CYAN}🧠 {BOLD}{GREEN}{cpu_name}{RESET}")
        print(f"{MAGENTA}🧮 Memory: {BOLD}{YELLOW}{mem_used_gb:.2f}GB / {total_memory_gb:.2f}GB ({mem_percent}%){RESET}")
        print(f"{BLUE}💾 Disk: {BOLD}{YELLOW}{disk_used_gb:.2f}GB / {disk_total_gb:.2f}GB ({disk_percent}%){RESET}")
        print(f"{GREEN}🌐 Local IP: {BOLD}{CYAN}{ip_addr_local}{RESET}")
        print(f"{RED}🎮 GPU: {BOLD}{MAGENTA}{gpu_display}{RESET}")

        if expanded:
            print_header("CPU", "🧠")
            cpu_info = get_cpu_expanded()
            for key, val in cpu_info:
                if "Threads" in key or "Logical" in key:
                    print_item("🧠", key, val, CYAN, YELLOW)
                else:
                    print_item("🧠", key, val, CYAN, GREEN)

            print_header("MEMORY", "🧮")
            mem_info = get_memory_expanded()
            for key, val in mem_info:
                color = YELLOW if "Used" in key or "Percent" in key else GREEN
                print_item("🧮", key, val, MAGENTA, color)

            disk_info = get_disk_expanded()
            for device, details in disk_info:
                print_header(f"DISK {device}", "💾")
                for key, val in details:
                    color = RED if key == "Use%" and float(val.strip('%')) > 80 else GREEN
                    print_item("💾", key, val, BLUE, color)

            net_info = get_network_expanded()
            if net_info:
                print_header("NETWORK", "🌐")
                for iface, details in net_info:
                    print(f"\n{BOLD}{YELLOW}[📡] {iface}{RESET}")
                    for key, val in details:
                        print_item("  📡", key, val, CYAN, GREEN)

            if gpus:
                print_header("GPU", "🎮")
                for i, gpu in enumerate(gpus, 1):
                    if len(gpus) > 1:
                        print(f"\n{BOLD}{YELLOW}GPU #{i}{RESET}")
                    print_item("🎮", "Name", gpu['name'], RED, MAGENTA)
                    if gpu.get('vram'):
                        print_item("🎮", "VRAM", gpu['vram'], RED, CYAN)
                    if gpu.get('driver'):
                        print_item("🎮", "Driver Version", gpu['driver'], RED, WHITE)
                    if gpu.get('status'):
                        status_color = GREEN if gpu['status'].lower() == 'ok' else YELLOW
                        print_item("🎮", "Status", gpu['status'], RED, status_color)

            print_header("SYSTEM", "💻")
            sys_info = get_system_expanded()
            for key, val in sys_info:
                print_item("💻", key, val, GRAY, WHITE)

            print_header("PUBLIC IP", "🌍")
            public_ip = get_real_ip()
            print_item("🌍", "External IP", public_ip, YELLOW, CYAN)

        print(f"\n{CYAN}{'═' * 60}{RESET}")
        print(f"{BOLD}{GREEN}[✓] System scan complete!{RESET}")
        print(f"{CYAN}{'═' * 60}{RESET}\n")