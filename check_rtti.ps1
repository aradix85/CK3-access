# Does this executable ship MSVC RTTI, and does it hold a widget class tree?
# That single question decides whether this whole approach can work on a build at all, and it
# takes seconds without starting the game. Pass a path to check another Paradox executable.
# Without one it asks tools/paths.py where the game is, which finds it through the Steam library
# rather than through a path that only exists on one machine.
param([string]$Exe = '')

$ErrorActionPreference = 'Stop'

if (-not $Exe) {
    $Exe = (python (Join-Path $PSScriptRoot 'tools\paths.py') | Select-String '^EXE\s+(.+)$').Matches[0].Groups[1].Value.Trim()
}

$fi = Get-Item $Exe
Write-Output ("executable: " + $fi.Name + ", " + [math]::Round($fi.Length / 1MB, 1) + " MB")
Write-Output ""

$bytes = [System.IO.File]::ReadAllBytes($Exe)
$ascii = [System.Text.Encoding]::ASCII.GetString($bytes)

# MSVC RTTI type names look like .?AVClassName@@ or .?AUName@@
$rtti = [regex]::Matches($ascii, '\.\?A[VU][A-Za-z0-9_@?$]{2,120}@@')
Write-Output ("RTTI type descriptors found: " + $rtti.Count)

if ($rtti.Count -eq 0) {
    Write-Output "NO RTTI present - this approach cannot work on this build"
    exit
}

# Sort-Object -Unique compares case insensitively and merged 18 names that differ only in case:
# 47,988 instead of 48,006. Compare ordinally, the way the bytes sit in the executable.
# Measured 30 July 2026.
$names = [System.Collections.Generic.SortedSet[string]]::new(
    [string[]]($rtti | ForEach-Object { $_.Value }), [System.StringComparer]::Ordinal)
Write-Output ("unique types: " + $names.Count)
Write-Output ""

Write-Output "=== types with 'Widget' in the name ==="
$widget = @($names | Where-Object { $_ -match 'Widget' })
Write-Output ("  count: " + $widget.Count)
$widget | Select-Object -First 25 | ForEach-Object { Write-Output ("  " + $_) }

Write-Output ""
Write-Output "=== other interface types worth a look ==="
foreach ($needle in @('Button', 'TextBox', 'ListBox', 'Tooltip', 'Window', 'Container', 'DataModel', 'Scrollbar')) {
    $hits = @($names | Where-Object { $_ -match $needle })
    Write-Output ("  {0,-12} : {1}" -f $needle, $hits.Count)
}

$report = Join-Path $PSScriptRoot 'reports\rtti_typen.txt'
[System.IO.File]::WriteAllLines($report, $names)
Write-Output ""
Write-Output "full list written to: $report"
