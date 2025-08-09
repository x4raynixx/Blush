import os
import platform
import subprocess
import sys

system = platform.system().lower()
is_windows = system == "windows"

if not is_windows:
    import termios
    import tty

options = [
    {"name": "bsdiag", "selected": True},
    {"name": "blush", "selected": False},
    {"name": "blush-installer", "selected": False},
]

def clear_screen():
    os.system('cls' if is_windows else 'clear')

def print_menu(selected_index):
    clear_screen()
    print("Use UP/DOWN arrows to move, SPACE to toggle, Y to build selected:\n")
    for i, opt in enumerate(options):
        prefix = "[x]" if opt["selected"] else "[-]"
        pointer = "->" if i == selected_index else "  "
        print(f"{pointer} {prefix} {opt['name']}")

def getch():
    if is_windows:
        import msvcrt
        ch = msvcrt.getch()
        if ch in b'\x00\xe0':
            ch2 = msvcrt.getch()
            return ch + ch2
        return ch
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch += sys.stdin.read(2)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def compile_bsdiag():
    diag_build_dir = os.path.join("utils", "ext", "bsdiag")
    gpp_cmd = [
        "g++",
        "diag.cpp",
        "-o",
        "bsdiag.exe" if is_windows else "bsdiag",
        "-ldxgi",
        "-lole32"
    ]
    subprocess.run(gpp_cmd, cwd=diag_build_dir, check=True)
    src = os.path.join(diag_build_dir, "bsdiag.exe" if is_windows else "bsdiag")
    dst_dir = os.path.join("release", "ext")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "bsdiag.exe" if is_windows else "bsdiag")
    os.replace(src, dst)

def compile_blush():
    output_name = f"blush-{arch_name}" + (".exe" if is_windows else "")
    icon_arg = f"--windows-icon-from-ico=blush.ico" if is_windows else f"--linux-icon=blush.ico"
    msvc_arg = "--msvc=latest" if is_windows else None
    cmd = [
        python_exec, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--enable-plugin=pylint-warnings",
        "--include-plugin-directory=utils",
        f"--output-dir=build",
        "--remove-output",
        icon_arg,
        f"--output-filename={output_name}",
        "main.py",
    ]
    if msvc_arg:
        cmd.append(msvc_arg)
    if is_windows:
        for mod in ["colorama", "wcwidth", "prompt_toolkit", "psutil"]:
            cmd.append(f"--include-module={mod}")
        for mod in ["pip"]:
            cmd.append(f"--nofollow-import-to={mod}")
    else:
        for mod in ["colorama", "wcwidth", "prompt_toolkit", "psutil"]:
            cmd.append(f"--include-module={mod}")
        for mod in ["pip"]:
            cmd.append(f"--nofollow-import-to={mod}")
    subprocess.run(cmd, check=True)
    src = os.path.join("build", output_name)
    dst_dir = os.path.join("release", "blush", system, arch_name)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, output_name)
    os.replace(src, dst)

def compile_installer():
    icon_path = "blush.ico"
    if is_windows:
        # poprawiona hardcoded ścieżka Windows
        pyside6_plugins_path = r"C:\Users\ytkey\AppData\Local\Programs\Python\Python313\Lib\site-packages\PySide6\plugins"
        pyside6_plugins_path = os.path.abspath(pyside6_plugins_path)
        if not os.path.isdir(pyside6_plugins_path):
            raise RuntimeError(f"PySide6 plugins directory not found: {pyside6_plugins_path}")
        cmd = [
            python_exec, "-m", "nuitka",
            "--standalone",
            "--onefile",
            "--enable-plugin=pylint-warnings",
            "--enable-plugin=pyside6",
            "--output-dir=build",
            "--remove-output",
            "--msvc=latest",
            f"--windows-icon-from-ico={icon_path}",
            "--nofollow-import-to=pip",
            "--include-module=colorama",
            "--include-module=wcwidth",
            "--include-module=requests",
            "--include-module=urllib3",
            "--include-module=charset_normalizer",
            "--include-module=idna",
            "--include-module=certifi",
            "--include-module=shiboken6",
            "--include-module=PySide6",
            "--output-filename=blush-installer.exe",
            "--windows-console-mode=disable",
            f"--include-data-dir={pyside6_plugins_path}=PySide6/plugins",
            "./installer/installer.py"
        ]
    else:
        pyside6_plugins_path = "/mnt/d/Codes/tests/Blush/venv/lib64/python3.12/site-packages/PySide6/Qt/plugins"
        pyside6_plugins_path = os.path.abspath(pyside6_plugins_path)
        if not os.path.isdir(pyside6_plugins_path):
            raise RuntimeError(f"PySide6 plugins directory not found: {pyside6_plugins_path}")
        cmd = [
            python_exec, "-m", "nuitka",
            "--standalone",
            "--onefile",
            "--enable-plugin=pylint-warnings",
            "--enable-plugin=pyside6",
            "--output-dir=build",
            "--remove-output",
            "--nofollow-import-to=pip",
            "--include-module=colorama",
            "--include-module=wcwidth",
            "--include-module=requests",
            "--include-module=urllib3",
            "--include-module=charset_normalizer",
            "--include-module=idna",
            "--include-module=certifi",
            "--include-module=shiboken6",
            "--include-module=PySide6",
            f"--linux-icon={icon_path}",
            "--output-filename=blush-installer",
            f"--include-data-dir={pyside6_plugins_path}=PySide6/plugins",
            "./installer/installer.py"
        ]
    subprocess.run(cmd, check=True)
    installer_name = "blush-installer.exe" if is_windows else "blush-installer"
    src = os.path.join("build", installer_name)
    dst_dir = os.path.join("release", "blush_installer", system, arch_name)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, installer_name)
    os.replace(src, dst)

arch = platform.machine().lower()

if arch in ["amd64", "x86_64"]:
    arch_name = "x64"
elif arch in ["x86", "i386", "i686"]:
    arch_name = "x86"
elif "arm" in arch or "aarch" in arch:
    arch_name = "arm64"
else:
    arch_name = arch

python_exec = "python" if is_windows else "./venv/bin/python3"

selected_index = 0
print_menu(selected_index)

while True:
    c = getch()
    if is_windows:
        if c in (b'\xe0H', b'k'):
            selected_index = (selected_index - 1) % len(options)
            print_menu(selected_index)
        elif c in (b'\xe0P', b'j'):
            selected_index = (selected_index + 1) % len(options)
            print_menu(selected_index)
        elif c == b' ':
            options[selected_index]["selected"] = not options[selected_index]["selected"]
            print_menu(selected_index)
        elif c in (b'y', b'Y'):
            break
    else:
        if c in ("\x1b[A", "k"):
            selected_index = (selected_index - 1) % len(options)
            print_menu(selected_index)
        elif c in ("\x1b[B", "j"):
            selected_index = (selected_index + 1) % len(options)
            print_menu(selected_index)
        elif c == " ":
            options[selected_index]["selected"] = not options[selected_index]["selected"]
            print_menu(selected_index)
        elif c in ("y", "Y"):
            break

clear_screen()
to_build = [opt["name"] for opt in options if opt["selected"]]
print(f"Building: {', '.join(to_build)}")

for target in to_build:
    if target == "bsdiag":
        compile_bsdiag()
    elif target == "blush":
        compile_blush()
    elif target == "blush-installer":
        compile_installer()

print("Done.")
