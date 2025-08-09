#!/bin/bash

APP_NAME="blush"
INSTALL_DIR="$HOME/.blush"
BIN_PATH="$INSTALL_DIR/$APP_NAME"
GITHUB_URL="https://github.com/x4raynixx/Blush/raw/refs/heads/master/build/blush"

install_blush() {
    echo "[*] Creating directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"

    echo "[*] Downloading $APP_NAME from GitHub..."
    curl -L "$GITHUB_URL" -o "$BIN_PATH"

    echo "[*] Making it executable..."
    chmod +x "$BIN_PATH"

    echo "[*] Adding alias to ~/.bashrc or ~/.zshrc..."
    SHELL_RC="$HOME/.bashrc"
    if [[ "$SHELL" == *"zsh" ]]; then
        SHELL_RC="$HOME/.zshrc"
    fi

    if ! grep -q "$BIN_PATH" "$SHELL_RC"; then
        echo "alias blush=\"$BIN_PATH\"" >> "$SHELL_RC"
        echo "[*] Alias added to $SHELL_RC"
    else
        echo "[*] Alias already exists in $SHELL_RC"
    fi

    echo "[*] Installation complete. Restart your terminal or run: source $SHELL_RC"
}

install_systemwide() {
    echo "[*] Moving to /usr/local/bin (requires sudo)"
    sudo cp "$BIN_PATH" /usr/local/bin/blush
    echo "[*] System-wide installation complete. You can now use 'blush' globally."
}

install_blush

read -p "Do you want to install blush system-wide (/usr/local/bin)? [y/N]: " choice
case "$choice" in
    y|Y|yes|YES)
        install_systemwide
        ;;
    *)
        echo "[*] Skipped system-wide installation."
        ;;
esac