param(
    [switch]$Html,
    [switch]$EnforceGates,
    [ValidateSet("Critical", "AllNonLive", "Live")]
    [string]$Scope = "Critical",
    [int]$FailUnder = 0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$python = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python virtual environment was not found at $python"
}

& $python -m coverage --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "coverage is not installed. Run: venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

$criticalModules = @(
    "test.test_versement_backend_managers",
    "test.test_versement_numbering_policy",
    "test.pos.test_inventory_loader",
    "test.pos.test_pos_ui_builder",
    "test.pos.test_payment_logic",
    "test.pos.test_payment_dialogs",
    "test.sales.test_daily_activity",
    "test.sales.test_views_and_dialogs",
    "test.sales.test_documents",
    "test.sales.test_processing",
    "test.application.test_security_and_permissions",
    "test.application.test_facades_and_logging",
    "test.interface.test_settings",
    "test.interface.test_settings_tab_widget",
    "test.interface.test_pdf_printer_tab_widget",
    "test.interface.test_thermal_printer_tab_widget",
    "test.interface.test_users_management_view"
)

$criticalReportInclude = @(
    "database/client_payment_manager/versements.py",
    "database/sales_manager/*",
    "database/system_logger.py",
    "ui/tools/invoice_generator.py",
    "ui/tools/print_functions.py",
    "ui/ui_customization.py",
    "ui/widgets/sales/POS/*",
    "ui/widgets/sales/multi_currency_dialog/*",
    "ui/widgets/sales/sales/*",
    "ui/widgets/settings/settings_tab.py",
    "ui/widgets/settings/pdf_printer_tab.py",
    "ui/widgets/settings/thermal_printer_tab.py",
    "ui/widgets/settings/users_view.py",
    "ui/widgets/settings/web_access_settings.py",
    "web/security.py"
)

function Invoke-CoverageGates {
    param(
        [string]$JsonPath
    )

    $jsonArgs = @("-m", "coverage", "json", "-o", $JsonPath)
    if ($Scope -eq "Critical") {
        $jsonArgs += "--include=$($criticalReportInclude -join ',')"
    }

    $jsonOutput = & $python @jsonArgs
    $jsonExit = $LASTEXITCODE
    $jsonOutput | ForEach-Object { Write-Host $_ }
    if ($jsonExit -ne 0) {
        return $jsonExit
    }

    $gateChecker = Join-Path $scriptDir "check_coverage_gates.py"
    $gateOutput = & $python $gateChecker $JsonPath
    $checkerExit = $LASTEXITCODE
    $gateOutput | ForEach-Object { Write-Host $_ }
    return $checkerExit
}

function Get-TestModules {
    param([string]$SelectedScope)

    if ($SelectedScope -eq "Critical") {
        return $criticalModules
    }

    $testRoot = Join-Path $repoRoot "test"
    $testFiles = Get-ChildItem -Path $testRoot -Recurse -Filter "test_*.py" |
        Where-Object {
            if ($SelectedScope -eq "Live") {
                return $_.FullName -match "\\test\\data_layer\\test_live_"
            }
            return $_.FullName -notmatch "\\test\\data_layer\\test_live_"
        } |
        Sort-Object FullName

    foreach ($file in $testFiles) {
        $relative = Resolve-Path -Path $file.FullName -Relative
        $relative = $relative -replace "^[.][\\/]", ""
        ($relative -replace "[\\/]", ".") -replace "\.py$", ""
    }
}

$modules = @(Get-TestModules -SelectedScope $Scope)

if (-not $modules) {
    throw "No test modules were found."
}

Write-Host "Running coverage scope '$Scope' for $($modules.Count) test modules."
if ($Scope -ne "Live") {
    Write-Host "Live tests are excluded: test\data_layer\test_live_*"
}

& $python -m coverage erase

$runArgs = @("-m", "coverage", "run", "-m", "unittest", "-b") + $modules
& $python @runArgs
$testExit = $LASTEXITCODE

$reportArgs = @("-m", "coverage", "report")
if ($Scope -eq "Critical") {
    $reportArgs += "--include=$($criticalReportInclude -join ',')"
}
if ($FailUnder -gt 0) {
    $reportArgs += "--fail-under=$FailUnder"
}
& $python @reportArgs
$reportExit = $LASTEXITCODE

$gateExit = 0
if ($EnforceGates -and $testExit -eq 0 -and $reportExit -eq 0) {
    $runtimeDir = Join-Path $repoRoot "runtime"
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $gateJsonPath = Join-Path $runtimeDir "coverage-gates-$Scope.json"
    $gateExit = Invoke-CoverageGates -JsonPath $gateJsonPath
}

if ($Html) {
    & $python -m coverage html
    if ($LASTEXITCODE -eq 0) {
        Write-Host "HTML report written to htmlcov\index.html"
    }
}

if ($testExit -ne 0) {
    exit $testExit
}
if ($reportExit -ne 0) {
    exit $reportExit
}
exit $gateExit
