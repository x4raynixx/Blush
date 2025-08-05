python -m nuitka ^
  --standalone ^
  --onefile ^
  --enable-plugin=pylint-warnings ^
  --include-plugin-directory=utils ^
  --output-dir=build ^
  --remove-output ^
  --msvc=latest ^
  --windows-icon-from-ico=blush.ico ^
  --nofollow-import-to=pip ^
  --include-module=colorama ^
  --include-module=wcwidth ^
  --output-filename=blush.exe ^
  main.py