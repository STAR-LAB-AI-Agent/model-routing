param([string]$Url='http://127.0.0.1:8765', [string]$BrowserExe='agent-browser', [string]$Output='artifacts/raw/live-recording.mp4')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:AGENT_BROWSER_SESSION='routelab-live-recording'
$videoPath=Join-Path $PWD $Output
if (Test-Path -LiteralPath $videoPath) { throw 'Output exists. Choose a new -Output path.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $videoPath) | Out-Null
& $BrowserExe open $Url
if ($LASTEXITCODE -ne 0) { throw 'Start app.py before recording.' }
& $BrowserExe set viewport 1440 1080
$tourSource=[System.IO.File]::ReadAllText((Join-Path $PWD 'scripts\demo-tour.js'), [System.Text.Encoding]::UTF8)
# Let the long tour run in-page while each CLI request stays short.
$backgroundSource="window.__routerTourState='running'; window.__routerTourPromise="+$tourSource.Trim().TrimEnd(';')+"; window.__routerTourPromise.then(()=>window.__routerTourState='done').catch(e=>window.__routerTourState='error: '+e.message); 'started';"
$tourScript=[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($backgroundSource))
& $BrowserExe record start $videoPath --fps 25
if ($LASTEXITCODE -ne 0) { throw 'Recording failed. Run agent-browser doctor and check ffmpeg.' }
try {
    & $BrowserExe eval -b $tourScript
    if ($LASTEXITCODE -ne 0) { throw 'Tour failed to start.' }
    $stateScript=[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes('window.__routerTourState'))
    $done=$false
    for($i=0;$i -lt 180;$i++) {
        Start-Sleep -Seconds 2
        $state=& $BrowserExe eval -b $stateScript
        if($state -match 'done') { $done=$true; break }
        if($state -match 'error:') { throw $state }
    }
    if(-not $done) { throw 'Tour timed out.' }
} finally {
    & $BrowserExe record stop
}
$evidenceScript=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('window.__recordedEvidence'))
& $BrowserExe eval -b $evidenceScript --json | Set-Content -Encoding utf8 artifacts/recorded-live-calls.json
& $BrowserExe screenshot (Join-Path $PWD 'artifacts/demo-result.png')
& $BrowserExe close
Write-Host $videoPath
