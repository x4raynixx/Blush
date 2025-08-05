import os
import sys
import requests
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar,
    QMessageBox, QPushButton, QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont

BLUSH_DOWNLOAD_URL_WINDOWS = "https://github.com/x4raynixx/Blush/raw/refs/heads/master/build/blush.exe"
BLUSH_DOWNLOAD_URL_LINUX = "https://github.com/x4raynixx/Blush/raw/refs/heads/master/build/blush"
LICENSE_URL = "https://raw.githubusercontent.com/x4raynixx/Blush/refs/heads/master/LICENSE"

USER_HOME = os.path.expanduser("~")
if sys.platform.startswith("win"):
    INSTALL_PATH = os.path.join(os.getenv('LOCALAPPDATA'), ".blush")
else:
    INSTALL_PATH = os.path.join(USER_HOME, ".blush")

class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url, target_dir):
        super().__init__()
        self.url = url
        self.target_dir = target_dir

    def run(self):
        try:
            os.makedirs(self.target_dir, exist_ok=True)
            filename = "blush.exe" if sys.platform.startswith("win") else "blush"
            target_file = os.path.join(self.target_dir, filename)

            r = requests.get(self.url, stream=True, timeout=15)
            r.raise_for_status()
            total_length = r.headers.get('content-length')

            if total_length is None:
                with open(target_file, "wb") as f:
                    f.write(r.content)
                self.progress.emit(100)
            else:
                dl = 0
                total_length = int(total_length)
                with open(target_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=4096):
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                            done = int(100 * dl / total_length)
                            self.progress.emit(done)

            if not sys.platform.startswith("win"):
                os.chmod(target_file, 0o755)

            self.finished.emit(target_file)
        except Exception as e:
            self.error.emit(str(e))

class LicenseLoader(QThread):
    finished = Signal(str)
    error = Signal(str)

    def run(self):
        try:
            r = requests.get(LICENSE_URL, timeout=10)
            r.raise_for_status()
            self.finished.emit(r.text)
        except Exception as e:
            self.error.emit(str(e))

class InstallerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blush Installer")
        self.setFixedSize(520, 520)
        try:
            self.setWindowIcon(QIcon("blush.ico"))
        except:
            pass

        self.layout = QVBoxLayout()

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 12px;
                background-color: #222;
                text-align: center;
                color: white;
                font-weight: bold;
                font-size: 14px;
                height: 30px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c6ff,
                    stop:0.5 #0072ff,
                    stop:1 #0047b3
                );
            }
        """)
        self.layout.addWidget(self.progress)

        self.license_text = QTextEdit()
        self.license_text.setReadOnly(True)
        self.license_text.setMinimumHeight(320)
        self.license_text.setFont(QFont("Consolas", 10))
        self.license_text.setStyleSheet("""
            background-color: white;
            color: black;
            border: 1px solid #ccc;
        """)
        self.license_text.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.layout.addWidget(self.license_text)

        self.status_label = QLabel("Przewiń do końca licencji, aby aktywować instalację.")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        self.layout.addWidget(self.status_label)

        self.install_button = QPushButton("Zainstaluj Blush")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.start_installation)
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #0072ff;
                color: white;
                font-weight: bold;
                font-size: 16px;
                border-radius: 12px;
                padding: 10px;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #aaa;
            }
            QPushButton:hover:enabled {
                background-color: #0047b3;
            }
        """)
        self.layout.addWidget(self.install_button)

        self.setLayout(self.layout)
        self.load_license()

    def load_license(self):
        self.status_label.setText("Pobieram warunki licencji...")
        self.license_loader = LicenseLoader()
        self.license_loader.finished.connect(self.license_loaded)
        self.license_loader.error.connect(self.license_error)
        self.license_loader.start()

    def license_loaded(self, text):
        self.license_text.setPlainText(text)
        self.status_label.setText("Przewiń do końca licencji, aby aktywować instalację.")

    def license_error(self, error_msg):
        self.license_text.setPlainText("Nie udało się wczytać licencji:\n" + error_msg)
        self.status_label.setText("Nie można kontynuować bez licencji.")

    def on_scroll(self, value):
        scrollbar = self.license_text.verticalScrollBar()
        if value == scrollbar.maximum():
            self.install_button.setEnabled(True)
            self.status_label.setText("Licencja przeczytana. Możesz zainstalować Blush.")
        else:
            self.install_button.setEnabled(False)
            self.status_label.setText("Przewiń do końca licencji, aby aktywować instalację.")

    def start_installation(self):
        self.install_button.setEnabled(False)
        self.status_label.setText("Pobieram Blush...")
        self.progress.setValue(0)

        url = BLUSH_DOWNLOAD_URL_WINDOWS if sys.platform.startswith("win") else BLUSH_DOWNLOAD_URL_LINUX
        self.worker = DownloadWorker(url, INSTALL_PATH)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.installation_complete)
        self.worker.error.connect(self.installation_error)
        self.worker.start()

    def installation_complete(self, blush_path):
        # Zapisz ścieżkę do pliku wykonywalnego
        self.blush_path = blush_path

        # Wyczyść obecny układ
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Ustaw ciemny motyw
        self.setStyleSheet("""
            background-color: #111;
            color: white;
        """)

        # Dodaj nowe elementy UI
        success_label = QLabel("✅ Blush został pomyślnie zainstalowany!")
        success_label.setAlignment(Qt.AlignCenter)
        success_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")

        self.launch_checkbox = QCheckBox("Uruchom Blush po zamknięciu instalatora")
        self.launch_checkbox.setChecked(True)
        self.launch_checkbox.setStyleSheet("font-size: 14px; padding: 5px;")

        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.close_app)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #222;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #0072ff;
            }
        """)

        # Ustaw elementy w układzie z wyśrodkowaniem
        self.layout.addStretch(1)
        self.layout.addWidget(success_label)
        self.layout.addWidget(self.launch_checkbox)
        self.layout.addWidget(close_btn)
        self.layout.addStretch(1)

    def installation_error(self, error_msg):
        self.status_label.setText("Błąd podczas instalacji!")
        QMessageBox.critical(self, "Błąd", f"Nie udało się zainstalować Blush:\n{error_msg}")
        self.install_button.setEnabled(False)

    def close_app(self):
        if self.launch_checkbox.isChecked():
            self.launch_blush()
        self.close()

    def launch_blush(self):
        try:
            subprocess.Popen([self.blush_path], shell=True)
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się uruchomić Blush:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())