## Terminal Befehle

## Automatisches Skript für Test


1 Prüfen, dass der Zwischenablagen Manager nicht gerade läuft. Sonst würde die Test-App wegen der Einzelinstanz-Sperre nur das echte Fenster nach vorne holen.
2 Deine echten Daten sichern in %USERPROFILE%\ClipboardManager-Sicherungen\<Datum>. Die letzten 5 Sicherungen werden behalten. Eigentlich fasst der Test deine echten Daten nicht an, aber so    hast du ein Sicherheitsnetz.
3 Testordner frisch anlegen und APPDATA nur für dieses Skript darauf umstellen
4 Testdaten direkt erzeugen, statt sie über die Zwischenablage einzuspielen. Das geht in einer Sekunde statt in 20, und du kannst währenddessen weiter kopieren. Es entstehen: 120 Texte, Gruppen, Favoriten, ein Link, ein langer mehrzeiliger Text, ein benannter und ein unbenannter Passwort-Eintrag und ein umbenannter Text. Das Passwort für die Anmeldung lautet testtest.
5 App starten und warten, bis du sie schließt
6 Aufräumen, auch bei Fehlern oder Strg+C: Services beenden, APPDATA zurücksetzen und den Testordner löschen

## Testumgebung anlegen
# Originalpfad merken, um später zurückzukehren
$originalAppData = $env:APPDATA

# Testordner für dieses Terminal setzen
$env:APPDATA = "C:\Temp\cm-test"

# Kontrolle
$env:APPDATA

# App starten

# Testdaten erzeugen
python -c "import time; from clipboard_service import ClipboardService; s = ClipboardService(None); [ (s.set_text(f'Testeintrag {i}'), time.sleep(0.15)) for i in range(120) ]"

# Passwort Eintrag
python -c "from clipboard_service import ClipboardService; ClipboardService(None).set_text('TestPasswort123', sensitive=True)"

# Service im Testordner starten
$env:APPDATA = "C:\Temp\cm-test"
python -m service

# Services beenden
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*-m service*' | ForEach-Object { Stop-Process -Id $_.ProcessId }

# Sicherung echter Daten
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
Copy-Item "$env:APPDATA\ClipboardManager" "$env:USERPROFILE\Desktop\ClipboardManager-Sicherung-$stamp" -Recurse

# Zurückholen
Remove-Item "$env:APPDATA\ClipboardManager" -Recurse
Copy-Item "$env:USERPROFILE\Desktop\ClipboardManager-Sicherung-<Datum>" "$env:APPDATA\ClipboardManager" -Recurse