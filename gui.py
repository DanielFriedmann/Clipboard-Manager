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

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import single_instance
from api_client import ApiClient, ApiError, ServiceUnavailable
from clipboard_service import ClipboardService
from lock_watcher import LockWatcher
from qt_views.login_view import LoginView
from qt_views.settings_dialog import ChangePasswordDialog, NewRecoveryDialog, SettingsDialog
from qt_views.main_window import MainWindow
from service.auth import load_or_create_token
from service_runner import ServiceRunner
from settings import load_settings, save_settings
from startup import (change_vault_password, open_api_data, prepare_new_recovery,
                     read_header_from_service, save_header)
from vault import WrongPassword
from viewmodel import ClipboardViewModel

APP_VERSION = "3.1.0"
APP_TITLE = f"abk-Clippy  {APP_VERSION}"
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


class TimerHost:
    # LockWatcher erwartet ein after(ms, funktion) wie bei Tkinter; in Qt erledigt das QTimer
    def after(self, milliseconds, callback):
        QTimer.singleShot(milliseconds, callback)


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

    install_error_handler(service_runner)

    # ViewModel startet gesperrt: keine Daten, bis die Anmeldung geklappt hat
    vm = ClipboardViewModel(None)
    vm.locked = True
    vm._locked_group_id = settings["selected_group"]   # wird nach dem Entsperren gewählt

    bridge = IncomingBridge()
    bridge.arrived.connect(vm.process_incoming)

    def on_clipboard_changed(capture):
        # läuft im Thread der Zwischenablage
        vm.receive_capture(capture)
        bridge.arrived.emit()

    service = ClipboardService(on_clipboard_changed)
    vm.service = service

    window = MainWindow(vm, settings, APP_TITLE)
    # aktueller Header (ändert sich z. B. nach "Passwort vergessen") und offene Daten
    session = {"header": header, "repository": None}

    def on_unlocked(vault, is_new, header_changed):
        # liefert None bei Erfolg, sonst einen Fehlertext für die Anmeldeseite
        try:
            repository = open_api_data(api, vault, is_new, header_changed)
        except (OSError, ValueError, ApiError, ServiceUnavailable) as error:
            return f"Die Daten konnten nicht geöffnet werden: {error}"
        session.update(header=vault.header, repository=repository)
        vm.unlock(repository)
        window.hide_login()
        return None

    def lock_app():
        if vm.locked:
            return
        window.prepare_lock()
        try:
            service.clear()   # Zwischenablage leeren, z. B. ein gerade kopiertes Passwort
        except Exception as error:
            print(f"Zwischenablage konnte nicht geleert werden: {error}")
        vm.lock()
        repository, session["repository"] = session["repository"], None
        repository.close()   # Klartext und Schlüssel entfernen
        window.show_login(LoginView(session["header"], on_unlocked, locked=True))

    window.lock_requested.connect(lock_app)

    # Einstellungen

    def set_setting(key, value):
        # sofort speichern, damit nichts verloren geht, falls die App abstürzt
        settings[key] = value
        try:
            save_settings(settings)
        except OSError as error:
            print(f"Einstellungen konnten nicht gespeichert werden: {error}")

    def change_password(parent):
        def submit(current, new):
            try:
                session["header"] = change_vault_password(api, session["header"], current, new)
            except WrongPassword:
                return "Das aktuelle Passwort ist falsch."
            except ServiceUnavailable:
                return "Der Speicherdienst antwortet nicht. Das Passwort wurde nicht geändert."
            except ApiError as error:
                return f"Speichern fehlgeschlagen ({error.status}). Das Passwort wurde nicht geändert."
            return None

        ChangePasswordDialog(parent, submit).open()

    def new_recovery(parent):
        pending = {"header": None}   # vorbereiteter Header, bis der Code notiert ist

        def prepare(password):
            try:
                pending["header"], code = prepare_new_recovery(session["header"], password)
            except WrongPassword:
                return None, "Das Passwort ist falsch."
            return code, None

        def confirm():
            try:
                save_header(api, pending["header"])
            except ServiceUnavailable:
                return "Der Speicherdienst antwortet nicht. Der alte Schlüssel bleibt gültig."
            except ApiError as error:
                return f"Speichern fehlgeschlagen ({error.status}). Der alte Schlüssel bleibt gültig."
            session["header"] = pending["header"]
            return None

        NewRecoveryDialog(parent, prepare, confirm).open()

    def open_settings():
        if vm.locked:
            return
        SettingsDialog(window, settings, on_change=set_setting, on_lock_now=lock_app, version=APP_VERSION,
                       on_change_password=change_password, on_new_recovery=new_recovery).open()

    window.settings_requested.connect(open_settings)

    def on_closing():
        try:
            save_settings(settings)
        except OSError as error:
            print(f"Einstellungen konnten nicht gespeichert werden: {error}")

    window.closing.connect(on_closing)
    window.restore_state()
    window.show_login(LoginView(header, on_unlocked))   # header None: Tresor anlegen
    window.show()

    lock_watcher = LockWatcher(TimerHost(), lock_app, settings)
    lock_watcher.start()

    threading.Thread(target=service.start, daemon=True).start()
    code = app.exec()

    # aufräumen: Dienst beenden, Klartext und Schlüssel überschreiben
    service_runner.stop()
    try:
        if session["repository"] is not None:
            session["repository"].close()
    except Exception as error:
        print(f"Aufräumen fehlgeschlagen: {error}")
    return code


if __name__ == "__main__":
    sys.exit(main())
