# Registers the daily github-trending pipeline with Windows Task Scheduler.
# Run from an elevated PowerShell:  ./tools/register-task.ps1  [-Time 3am] [-TaskName github-trending-daily]
param(
    [string]$Time = "3am",
    [string]$TaskName = "github-trending-daily"
)

$repo = (Resolve-Path "$PSScriptRoot\..").Path
$uv = (Get-Command uv -ErrorAction Stop).Source

$action = New-ScheduledTaskAction -Execute $uv `
    -Argument "run python -m github_trending.orchestrate" -WorkingDirectory $repo

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

# StartWhenAvailable = catch up after a missed start (sleeping/off laptop) — a late
# snapshot, not a gap. 6h limit comfortably covers the ~2-3h sweep. Never overlap runs.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Daily trending-GitHub-repos pipeline" -Force

Write-Host "Registered '$TaskName' to run daily at $Time."
Write-Host "Working dir: $repo"
Write-Host "Test it now with:  Start-ScheduledTask -TaskName $TaskName"
