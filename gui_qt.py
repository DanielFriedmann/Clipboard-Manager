import os
import sys

# Dieselbe Datei startet auch den Speicherdienst (wichtig für die .exe)
if "--service" in sys.argv:
    from service.__main__ import run
    run()
    sys.exit(0)

import ctypes
import threading
import time
import traceback

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

import single_instance
from api_client import ApiClient, ApiError, ServiceUnavailable
from clipboard_service import ClipboardService
from qt_views.main_window import MainWindow
from service.auth import load_or_create_token
from service_runner import ServiceRunner
from settings import load_settings, save_settings
from startup import open_api_data, read_header_from_service
from vault import Vault, WrongPassword
from viewmodel import ClipboardViewModel

APP_VERSION = "3.0.0-dev"
APP_TITLE = f"Zwischenablagen Manager  {APP_VERSION}"
APP_NAME = "Zwischenablagen Manager"
SERVICE_MESSAGE_PAUSE = 30   # Sekunden zwischen zwei Meldungen über den Speicherdienst


def resource_path(filename):
    # In der .exe liegen mitgelieferte Dateien in einem eigenen Ordner von PyInstaller
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)


class IncomingBridge(QObject):
    # Übergabe vom Thread der Zwischenablage in den Oberflächen-Thread.
    # Ein Signal aus einem fremden Thread kommt bei Qt automatisch im richtigen Thread an.
    arrived = Signal()


def ask_password(header):
    # vorläufige Anmeldung bis Schritt 4; liefert den Tresor oder None bei Abbruch
    message = "Passwort:"
    while True:
        password, ok = QInputDialog.getText(None, APP_NAME, message, QLineEdit.EchoMode.Password)
        if not ok:
            return None
        try:
            return Vault.unlock(header, password)
        except WrongPassword:
            message = "Falsches Passwort. Bitte erneut eingeben:"


def install_error_handler(service_runner):
    # Fehler aus Klicks: Dienst-Probleme im Fenster melden, alles andere wie bisher ausgeben
    last = {"time": None}

    def handler(exc_type, error, tb):
        if not isinstance(error, (ServiceUnavailable, ApiError)):
            traceback.print_exception(exc_type, error, tb)
            return
        if isinstance(error, ServiceUnavailable):
            try:
                service_runner.ensure_running()
                text = ("Der Speicherdienst war kurz nicht erreichbar und wurde neu gestartet.\n"
                        "Bitte die letzte Aktion wiederholen.")
            except ServiceUnavailable as again:
                text = f"Der Speicherdienst ist nicht erreichbar.\n\n{again}"
        else:
            text = f"Der Speicherdienst hat einen Fehler gemeldet ({error.status}):\n{error.detail}"

        # nicht bei jedem Fehler erneut melden
        now = time.monotonic()
        if last["time"] is not None and now - last["time"] < SERVICE_MESSAGE_PAUSE:
            return
        last["time"] = now
        QMessageBox.warning(None, APP_NAME, text)

    sys.excepthook = handler


def main():
    # nur eine Instanz: sonst laufendes Fenster nach vorne holen und beenden
    if not single_instance.acquire():
        single_instance.bring_to_front(APP_TITLE)
        return 0

    # eigene Programmkennung, damit Windows in der Taskleiste unser Symbol zeigt
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Abkoo.Zwischenablagen.Manager")

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    settings = load_settings()

    # Speicherdienst starten
    api = ApiClient(load_or_create_token())
    service_runner = ServiceRunner(api)
    try:
        service_runner.ensure_running()
        header = read_header_from_service(api)
    except (ServiceUnavailable, ApiError) as error:
        QMessageBox.critical(None, APP_NAME, f"Der Speicherdienst ist nicht verfügbar.\n\n{error}")
        service_runner.stop()
        return 1

    if header is None:
        QMessageBox.information(None, APP_NAME, "Es gibt noch keinen Tresor. Bitte einmal mit der alten "
                                                "Oberfläche (gui.py) anlegen, das Einrichten folgt in Schritt 4.")
        service_runner.stop()
        return 0

    # Anmelden und Daten öffnen
    vault = ask_password(header)
    if vault is None:
        service_runner.stop()
        return 0
    try:
        repository = open_api_data(api, vault, is_new=False, header_changed=False)
    except (OSError, ValueError, ApiError, ServiceUnavailable) as error:
        QMessageBox.critical(None, APP_NAME, f"Die Daten konnten nicht geöffnet werden.\n\n{error}")
        service_runner.stop()
        return 1

    install_error_handler(service_runner)

    # ViewModel und Zwischenablage verbinden
    vm = ClipboardViewModel(repository)
    bridge = IncomingBridge()
    bridge.arrived.connect(vm.process_incoming)

    def on_clipboard_changed(capture):
        # läuft im Thread der Zwischenablage
        vm.receive_capture(capture)
        bridge.arrived.emit()

    service = ClipboardService(on_clipboard_changed)
    vm.service = service

    # Fenster
    vm.select_group_by_id(settings["selected_group"])
    window = MainWindow(vm, settings, APP_TITLE)

    def on_closing():
        try:
            save_settings(settings)
        except OSError as error:
            print(f"Einstellungen konnten nicht gespeichert werden: {error}")

    window.closing.connect(on_closing)
    window.restore_state()
    window.show()

    threading.Thread(target=service.start, daemon=True).start()
    code = app.exec()

    # aufräumen: Dienst beenden, Klartext und Schlüssel überschreiben
    service_runner.stop()
    try:
        repository.close()
    except Exception as error:
        print(f"Aufräumen fehlgeschlagen: {error}")
    return code


if __name__ == "__main__":
    sys.exit(main())
