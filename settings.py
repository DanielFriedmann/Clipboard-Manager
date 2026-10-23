import json
import os

from storage import APP_DIR

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
SETTINGS_VERSION = 1

# Standardwerte für alles, was in der Datei fehlt
DEFAULTS = {
    "window_geometry": None,
    "window_maximized": False,
    "sidebar_collapsed": False,
    "view": "Kacheln",
    "selected_group": None,   # ID der Gruppe, None = "Alle Einträge"
}


def load_settings(path=SETTINGS_FILE):
    settings = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            # nur bekannte Schlüssel übernehmen
            settings.update({key: data[key] for key in DEFAULTS if key in data})
    except FileNotFoundError:
        pass   # erster Start
    except (json.JSONDecodeError, OSError) as error:
        print(f"Einstellungen konnten nicht gelesen werden: {error}")
    return settings


def save_settings(settings, path=SETTINGS_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump({"version": SETTINGS_VERSION, **settings}, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)