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

$configDirectory = Split-Path -Parent $configPath
$configStem = [System.IO.Path]::GetFileNameWithoutExtension($configPath)
$generatedYaml = if ([string]::IsNullOrEmpty($configDirectory)) {
    "$configStem-generated.yaml"
}
else {
    Join-Path $configDirectory "$configStem-generated.yaml"
}

$builtHtml = [System.IO.Path]::ChangeExtension($generatedYaml, '.html')

$generateArgs = @(
    '--from', 'git+https://github.com/gordonwatts/time-page.git',
    'committee', 'indico', 'generate',
    $Config,
    '--from', $fromDateIso,
    '--to', $toDateIso
)

$buildArgs = @(
    '--from', 'git+https://github.com/gordonwatts/time-page.git',
    'committee', 'build',
    $generatedYaml
)

$generateCmd = "uvx $($generateArgs -join ' ')"
$buildCmd = "uvx $($buildArgs -join ' ')"

$null = Get-Command uvx -ErrorAction Stop

if ($PSCmdlet.ShouldProcess($generateCmd, "Invoke")) {
    & uvx @generateArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Generate command failed with exit code $LASTEXITCODE"
    }
}

if ($PSCmdlet.ShouldProcess($buildCmd, "Invoke")) {
    & uvx @buildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code $LASTEXITCODE"
    }
}
