import os
import subprocess
import sys
import time

from api_client import ServiceUnavailable

START_TIMEOUT = 15.0     # Sekunden, bis der Service antworten muss
POLL_INTERVAL = 0.2
STOP_TIMEOUT = 3.0
CREATE_NO_WINDOW = 0x08000000   # Windows: kein eigenes Konsolenfenster für den Service

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def service_command():
    if getattr(sys, "frozen", False):
        # in der .exe: dieselbe Datei, aber als Service
        return [sys.executable, "--service"]
    # beim Entwickeln: das Paket service mit demselben Python
    return [sys.executable, "-m", "service"]


class ServiceRunner:
    # Startet den Entry-Service bei Bedarf und beendet ihn wieder

    def __init__(self, client):
        self.client = client
        self.process = None   # nur gesetzt, wenn WIR ihn gestartet haben

    def ensure_running(self):
        if self.client.health():
            return   # läuft schon, z. B. noch von einem früheren Start

        flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(service_command(), cwd=PROJECT_DIR, creationflags=flags)

        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            if self.client.health():
                return
            if self.process.poll() is not None:
                # Prozess ist schon wieder beendet, z. B. weil der Port belegt ist
                code = self.process.returncode
                self.process = None
                raise ServiceUnavailable(f"Der Speicherdienst wurde unerwartet beendet (Code {code}).")
            time.sleep(POLL_INTERVAL)

        self.stop()
        raise ServiceUnavailable("Der Speicherdienst hat nicht rechtzeitig geantwortet.")

    def stop(self):
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process = None