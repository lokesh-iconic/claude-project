<#
.SYNOPSIS
    Run Claude Code in headless mode (-p) and capture output programmatically.

.DESCRIPTION
    Demonstrates Claude Code's non-interactive mode for use in scripts,
    pipelines, and automation. The -p flag sends a single prompt and
    prints the result to stdout without starting an interactive session.

.EXAMPLE
    .\claude_code\scripts\headless_summary.ps1
#>

$ErrorActionPreference = "Stop"

# --- Configuration ---
$Prompt = "List the Python files in this project and give a one-sentence description of what each file does. Format as a markdown table."
$OutputDir = Join-Path $PSScriptRoot "output"

# --- Load .env if ANTHROPIC_API_KEY is not already in environment ---
$EnvFile = $null
$CurrentDir = $PSScriptRoot
while ($CurrentDir) {
    $Candidate = Join-Path $CurrentDir ".env"
    if (Test-Path $Candidate) {
        $EnvFile = $Candidate
        break
    }
    $Parent = Split-Path -Parent $CurrentDir
    if ($Parent -eq $CurrentDir) { break }
    $CurrentDir = $Parent
}

if ($EnvFile -and (Test-Path $EnvFile)) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^ANTHROPIC_API_KEY=(.*)$") {
            $val = $matches[1].Trim('"', "'").Trim()
            if ($val -and -not $env:ANTHROPIC_API_KEY) {
                $env:ANTHROPIC_API_KEY = $val
            }
        }
    }
}

# --- Ensure output directory exists ---
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# --- Run Claude Code in headless mode ---
$KeyStatus = if ($env:ANTHROPIC_API_KEY) { "Configured ($($env:ANTHROPIC_API_KEY.Substring(0, [Math]::Min(8, $env:ANTHROPIC_API_KEY.Length)))...)" } else { "Not found in .env" }
Write-Host ("=" * 60)
Write-Host "Claude Code - Headless Mode Demo (PowerShell)"
Write-Host "API Key: $KeyStatus"
Write-Host ("=" * 60)
Write-Host ""
Write-Host "Prompt: $Prompt"
Write-Host ""
Write-Host "Running claude -p ... (this may take a moment)"
Write-Host ""

try {
    $Output = & claude -p $Prompt 2>&1
    $ExitCode = $LASTEXITCODE
}
catch {
    Write-Error "Failed to run 'claude'. Is it installed and on PATH? Error: $_"
    exit 1
}

if ($ExitCode -ne 0) {
    Write-Warning "Claude Code exited with code $ExitCode"
}

# --- Save output ---
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputFile = Join-Path $OutputDir "headless_result_$Timestamp.txt"
$Output | Out-File -FilePath $OutputFile -Encoding utf8

# --- Display results ---
Write-Host ("-" * 60)
Write-Host "OUTPUT:"
Write-Host ("-" * 60)
Write-Host $Output
Write-Host ("-" * 60)
Write-Host ""
Write-Host "Saved to: $OutputFile"
Write-Host "Output length: $($Output.Length) characters"

# --- Demonstrate JSON output format ---
Write-Host ""
Write-Host "Now running with --output-format json ..."

try {
    $JsonOutput = & claude -p "What is the project name and Python version from pyproject.toml?" --output-format json 2>&1
    $JsonFile = Join-Path $OutputDir "headless_json_$Timestamp.json"
    $JsonOutput | Out-File -FilePath $JsonFile -Encoding utf8
    Write-Host "JSON output saved to: $JsonFile"
}
catch {
    Write-Warning "JSON output run failed: $_"
}

Write-Host ""
Write-Host "Done. Both text and JSON outputs demonstrate headless (-p) mode."
