./venv/bin/python3 -m nuitka \
  --standalone \
  --onefile \
  --enable-plugin=pylint-warnings \
  --include-plugin-directory=utils \
  --output-dir=build \
  --remove-output \
  --linux-icon=blush.ico \
  --nofollow-import-to=pip \
  --include-module=colorama \
  --include-module=wcwidth \
  --output-filename=blush \
  main.py