<#
.SYNOPSIS
    Resolve UE engine root from a .uproject EngineAssociation via Windows registry.

.DESCRIPTION
    Windows only. Designed to be invoked by AI / users to obtain the engine source
    path without manually inspecting the registry.

    EngineAssociation form -> registry location:
      - Version (e.g. "5.7")          -> HKLM\SOFTWARE\EpicGames\Unreal Engine\<Version>\InstalledDirectory
      - GUID    (e.g. "{A20C...}")    -> HKCU\SOFTWARE\Epic Games\Unreal Engine\Builds\<GUID>

.PARAMETER UProject
    Path to a .uproject file. Defaults to the first .uproject in the script directory.

.PARAMETER Json
    Emit JSON output (recommended for AI consumption).

.EXAMPLE
    # Human readable
    pwsh ./get_engine_root.ps1

    # JSON
    pwsh ./get_engine_root.ps1 -Json

    # Specify a project
    pwsh ./get_engine_root.ps1 -UProject "F:\Projects\MyGame\MyGame.uproject"
#>

[CmdletBinding()]
param(
    [string]$UProject,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

function Write-Result {
    param([hashtable]$Data, [bool]$AsJson)
    if ($AsJson) {
        $Data | ConvertTo-Json -Depth 4
    } else {
        Write-Host ("EngineAssociation : {0}" -f $Data.engineAssociation)
        Write-Host ("Association Type  : {0}" -f $Data.associationType)
        Write-Host ("Engine Root       : {0}" -f $Data.engineRoot)
        Write-Host ("Engine Source     : {0}" -f $Data.engineSource)
        Write-Host ("Engine Plugins    : {0}" -f $Data.enginePlugins)
    }
}

function Fail-Exit {
    param([string]$Message, [bool]$AsJson)
    if ($AsJson) {
        @{ ok = $false; error = $Message } | ConvertTo-Json
    } else {
        Write-Error $Message
    }
    exit 1
}

# ---- 1. Locate .uproject ----
if (-not $UProject) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $found = Get-ChildItem -Path $scriptDir -Filter '*.uproject' -File | Select-Object -First 1
    if (-not $found) {
        Fail-Exit "No .uproject found in script directory. Pass -UProject to specify." $Json
    }
    $UProject = $found.FullName
}

if (-not (Test-Path $UProject)) {
    Fail-Exit ".uproject not found: $UProject" $Json
}

# ---- 2. Read EngineAssociation ----
try {
    $proj = Get-Content -Raw -Path $UProject | ConvertFrom-Json
} catch {
    Fail-Exit "Failed to parse .uproject as JSON: $_" $Json
}

$assoc = $proj.EngineAssociation
if ([string]::IsNullOrWhiteSpace($assoc)) {
    Fail-Exit "EngineAssociation is empty in .uproject (project may sit beside an in-tree Engine/ folder)." $Json
}

# ---- 3. Look up registry ----
$engineRoot = $null
$assocType  = $null

if ($assoc -match '^\{[0-9A-Fa-f-]+\}$') {
    # Source build (GUID)
    $assocType = 'source-build'
    $key = 'HKCU:\SOFTWARE\Epic Games\Unreal Engine\Builds'
    if (-not (Test-Path $key)) {
        Fail-Exit "Registry key not found: $key (no source-built UE registered)." $Json
    }
    $props = Get-ItemProperty -Path $key
    if ($null -eq $props.$assoc) {
        Fail-Exit "GUID $assoc not registered. Run: reg query `"HKCU\SOFTWARE\Epic Games\Unreal Engine\Builds`"" $Json
    }
    $engineRoot = $props.$assoc
} else {
    # Installed (version number)
    $assocType = 'installed'
    $key = "HKLM:\SOFTWARE\EpicGames\Unreal Engine\$assoc"
    if (-not (Test-Path $key)) {
        Fail-Exit "Registry key not found: $key (UE $assoc not installed, or EngineAssociation is wrong)." $Json
    }
    $props = Get-ItemProperty -Path $key
    if (-not $props.InstalledDirectory) {
        Fail-Exit "Registry key $key has no InstalledDirectory value." $Json
    }
    $engineRoot = $props.InstalledDirectory
}

# ---- 4. Build result ----
$engineRoot    = $engineRoot.TrimEnd('\','/')
$engineSource  = Join-Path $engineRoot 'Engine\Source'
$enginePlugins = Join-Path $engineRoot 'Engine\Plugins'

$result = @{
    ok                = $true
    uproject          = $UProject
    engineAssociation = $assoc
    associationType   = $assocType   # 'installed' | 'source-build'
    engineRoot        = $engineRoot
    engineSource      = $engineSource
    enginePlugins     = $enginePlugins
}

Write-Result -Data $result -AsJson:$Json
