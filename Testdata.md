## Terminal Befehle

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