# Testumgebung für den Zwischenablagen Manager
# Sichert die echten Daten, startet die App mit Testdaten in einem eigenen Ordner
# und räumt nach dem Schließen alles wieder auf.
#
# Aufruf im Projektordner:  .\testumgebung.ps1
# Mit Optionen:             .\testumgebung.ps1 -Anzahl 500 -Passwort "meintest" -Behalten

param(
    [int]$Anzahl = 120,
    [string]$Passwort = "testtest",
    [switch]$Behalten,          # Testordner nach dem Schließen nicht löschen
    [switch]$Exe               # gebaute .exe statt gui.py starten
)

$ErrorActionPreference = "Stop"

$projekt = $PSScriptRoot
$python = Join-Path $projekt ".venv\Scripts\python.exe"
$echterOrdner = Join-Path $env:APPDATA "ClipboardManager"
$testOrdner = "C:\Temp\cm-testumgebung"
$sicherungen = Join-Path $env:USERPROFILE "ClipboardManager-Sicherungen"
$behalteSicherungen = 5
$originalAppData = $env:APPDATA
$exePfad = Join-Path $projekt "dist\Zwischenablagen-Manager\Zwischenablagen-Manager.exe"


function Stop-Speicherdienste {
    # beendet alle laufenden Speicherdienste (Entwicklung und .exe)
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='Zwischenablagen-Manager.exe'" |
        Where-Object { $_.CommandLine -like '*-m service*' -or $_.CommandLine -like '*--service*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}


function Test-AppLaeuft {
    # läuft der Zwischenablagen Manager gerade (als Skript oder als .exe)?
    $prozesse = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='Zwischenablagen-Manager.exe'" |
        Where-Object {
            $_.CommandLine -like '*gui.py*' -or
            ($_.Name -eq 'Zwischenablagen-Manager.exe' -and $_.CommandLine -notlike '*--service*')
        }
    return [bool]$prozesse
}


# Vorab prüfen

if (-not (Test-Path $python)) {
    Write-Host "Virtuelle Umgebung nicht gefunden: $python" -ForegroundColor Red
    exit 1
}
if (Test-AppLaeuft) {
    Write-Host "Der Zwischenablagen Manager läuft noch. Bitte zuerst schließen." -ForegroundColor Yellow
    exit 1
}

Push-Location $projekt
try {
    # 1. echte Daten sichern
    if (Test-Path $echterOrdner) {
        $ziel = Join-Path $sicherungen (Get-Date -Format "yyyyMMdd-HHmmss")
        New-Item -ItemType Directory -Path $ziel -Force | Out-Null
        Copy-Item "$echterOrdner\*" $ziel -Recurse
        Write-Host "Echte Daten gesichert: $ziel"

        # nur die neuesten Sicherungen behalten
        Get-ChildItem $sicherungen -Directory | Sort-Object Name -Descending |
            Select-Object -Skip $behalteSicherungen | Remove-Item -Recurse -Force
    }

    # 2. alte Dienste beenden, Testordner frisch anlegen
    Stop-Speicherdienste
    if (Test-Path $testOrdner) {
        Remove-Item $testOrdner -Recurse -Force
    }

    # 3. auf den Testordner umstellen (gilt für alles, was dieses Skript startet)
    $env:APPDATA = $testOrdner

    # 4. Testdaten erzeugen
    & $python -m manual.make_test_data (Join-Path $testOrdner "ClipboardManager") $Anzahl $Passwort
    if ($LASTEXITCODE -ne 0) {
        throw "Testdaten konnten nicht erzeugt werden."
    }

    # 5. App starten und warten, bis sie geschlossen wird
    Write-Host ""
    Write-Host "Testumgebung läuft. Anmelden mit: $Passwort" -ForegroundColor Green
    Write-Host "Zum Beenden einfach die App schließen."
    if ($Exe) {
        if (-not (Test-Path $exePfad)) {
            throw "Keine .exe gefunden: $exePfad (vorher bauen)"
        }
        # -Wait: ein Fensterprogramm würde sonst sofort zurückkehren
        Start-Process -FilePath $exePfad -Wait
    }
    else {
        & $python gui.py
    }
}
finally {
    # 6. aufräumen, auch nach Fehlern oder Strg+C
    Stop-Speicherdienste
    $env:APPDATA = $originalAppData
    Pop-Location

    if ($Behalten) {
        Write-Host "Testordner bleibt erhalten: $testOrdner"
    }
    elseif (Test-Path $testOrdner) {
        Start-Sleep -Milliseconds 500   # Windows kurz Zeit geben, die Dateien freizugeben
        Remove-Item $testOrdner -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Testumgebung aufgeräumt."
    }
    Write-Host "APPDATA wieder: $env:APPDATA"
}