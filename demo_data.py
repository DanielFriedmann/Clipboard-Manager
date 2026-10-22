from datetime import datetime, timedelta

# Testdaten für die Entwicklung, alle Inhalte sind ausgedacht

DEMO_GROUPS = [
    ("Arbeit", "#e57373"),
    ("Privat", "#81c784"),
    ("Kundenprojekte Süd", "#64b5f6"),
    ("Ideen", "#fff176"),
]

LONG_TEXT = (
    "Dies ist ein absichtlich sehr langer Testeintrag, der zeigen soll, wie die Vorschau "
    "mit Texten umgeht, die deutlich länger sind als der verfügbare Platz in einer Kachel "
    "oder in der Tabelle. Er enthält mehrere Sätze und sollte sauber gekürzt werden."
)

MULTILINE_TEXT = "Erste Zeile der Notiz\nZweite Zeile mit Details\nDritte Zeile zum Abschluss"

# (Inhalt, Gruppe oder None, Favorit, Alter in Tagen), vom ältesten zum neuesten
DEMO_ITEMS = [
    ("Umlaute-Test: äöü ÄÖÜ ß", None, False, 20),
    ("Dunkelmodus automatisch nach Uhrzeit wechseln?", "Ideen", False, 14),
    ("Ansprechpartnerin Süd: Frau Beispiel, Tel. 0123 456789", "Kundenprojekte Süd", False, 10),
    ("Geburtstag Oma am 3. November", "Privat", True, 5),
    ("Angebot Nr. 2026-0815 an Muster GmbH senden", "Kundenprojekte Süd", True, 3),
    ("SELECT name, email FROM kunden WHERE ort = 'Berlin';", "Arbeit", False, 1),
    ("Zugverbindung 17:42 ab Hauptbahnhof", "Privat", False, 1),
    (MULTILINE_TEXT, None, False, 1),
    ("Meeting mit Team Vertrieb, Donnerstag 14:00, Raum 2.14", "Arbeit", False, 0),
    ("https://example.com/projekte/clipboard-manager", "Arbeit", True, 0),
    ("Einkaufsliste: Milch, Brot, Äpfel, Käse", "Privat", False, 0),
    ("Tooltips für die eingeklappte Seitenleiste", "Ideen", False, 0),
    (LONG_TEXT, None, False, 0),
    ("apfel, klein geschrieben", None, False, 0),
]


def load_demo_data(history):
    groups = {name: history.add_group(name, color) for name, color in DEMO_GROUPS}
    now = datetime.now()

    for index, (text, group_name, is_favorite, days_ago) in enumerate(DEMO_ITEMS):
        history.add_item(text)
        item = history.history[0]   # add_item fügt neue Einträge oben ein

        if group_name:
            history.assign_item_to_group(item, groups[group_name])
        if is_favorite:
            history.toggle_favorite(item)

        # Minuten-Versatz, damit auch Einträge vom selben Tag eine feste Reihenfolge haben
        item.created_at = now - timedelta(days=days_ago, minutes=len(DEMO_ITEMS) - index)