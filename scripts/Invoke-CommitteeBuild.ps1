[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Config
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$today = Get-Date
$daysSinceSunday = [int]$today.DayOfWeek
$mostRecentSunday = $today.Date.AddDays(-$daysSinceSunday)
$fromDate = $mostRecentSunday.AddDays(-21)
$toDate = $mostRecentSunday.AddDays(14)

$fromDateIso = $fromDate.ToString('yyyy-MM-dd')
$toDateIso = $toDate.ToString('yyyy-MM-dd')

$configPath = if ([string]::IsNullOrWhiteSpace([System.IO.Path]::GetExtension($Config))) {
    [System.IO.Path]::ChangeExtension($Config, '.yaml')
}
else {
    $Config
}

$builtHtml = [System.IO.Path]::ChangeExtension($configPath, '.html')

$buildArgs = @(
    '--from', 'git+https://github.com/gordonwatts/time-page.git',
    'committee', 'build',
    $configPath,
    '--from', $fromDateIso,
    '--to', $toDateIso,
    '--overwrite'
)

$buildCmd = "uvx $($buildArgs -join ' ')"

$null = Get-Command uvx -ErrorAction Stop

if ($PSCmdlet.ShouldProcess($buildCmd, "Invoke")) {
    & uvx @buildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code $LASTEXITCODE"
    }
}

Write-Verbose "Built HTML: $builtHtml"
