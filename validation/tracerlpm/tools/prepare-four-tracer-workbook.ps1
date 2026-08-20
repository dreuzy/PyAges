param(
    [string]$Source = 'C:\TracerLPM-Test\working\TracerLPM_V_1_0_Example1_fr_solver.xlsm',
    [string]$Target = 'C:\TracerLPM-Test\working\TracerLPM_V_1_0_FourTracers_v5.xlsm',
    [string]$XllPath = 'C:\Users\dreuzy\AppData\Roaming\Microsoft\AddIns\TracerLPMfunctions_64_v_1.xll',
    [switch]$InspectOnly
)

$ErrorActionPreference = 'Stop'
$excel = $null
$workbook = $null
$solverWorkbook = $null
$sheet = $null

try {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Classeur source introuvable : $Source"
    }
    $openPath = $Source
    if (-not $InspectOnly) {
        if (Test-Path -LiteralPath $Target) {
            throw "La cible existe déjà : $Target"
        }
        Copy-Item -LiteralPath $Source -Destination $Target
        $openPath = $Target
    }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $true
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $true
    $excel.AutomationSecurity = 1
    $solverPath = 'C:\Program Files\Microsoft Office\Root\Office16\LIBRARY\SOLVER\SOLVER.XLAM'
    $solverWorkbook = $excel.Workbooks.Open($solverPath, 0, $true)
    if (-not $excel.RegisterXLL($XllPath)) {
        throw "Échec du chargement du XLL : $XllPath"
    }
    $workbook = $excel.Workbooks.Open($openPath, 0, [bool]$InspectOnly)
    $sheet = $workbook.Worksheets.Item('Samples')

    $controls = foreach ($ole in $sheet.OLEObjects()) {
        $name = [string]$ole.Name
        if ($name -notmatch '^Tracer([1-9]|10)$') { continue }
        $control = $ole.Object
        $values = for ($index = 0; $index -lt [int]$control.ListCount; $index++) {
            [string]$control.List($index)
        }
        [pscustomobject]@{
            Name = $name
            Value = [string]$control.Value
            Available = $values -join '|'
        }
    }
    $controls | Sort-Object Name | Format-Table -AutoSize

    if (-not $InspectOnly) {
        $selection = @('CFC-11', 'CFC-12', 'CFC-113', 'SF6')
        $excel.EnableEvents = $false
        for ($slot = 1; $slot -le 10; $slot++) {
            $control = $sheet.OLEObjects("Tracer$slot").Object
            $expected = if ($slot -le $selection.Count) { $selection[$slot - 1] } else { 'EMPTY' }
            $found = $false
            for ($index = 0; $index -lt [int]$control.ListCount; $index++) {
                if ([string]$control.List($index) -eq $expected) {
                    $control.ListIndex = $index
                    $found = $true
                    break
                }
            }
            if (-not $found) { throw "Traceur '$expected' absent du contrôle Tracer$slot" }
        }
        foreach ($macro in @('PopulateTracerColumns', 'RetrieveTracerData',
                              'UpdateTracersForCalcSheets', 'FillTracerCombos')) {
            Write-Output "MACRO_START=$macro"
            $excel.Run("'$($workbook.Name)'!$macro")
            Write-Output "MACRO_DONE=$macro"
        }
        $excel.EnableEvents = $true
        $workbook.Save()
        Write-Output "SAVED=$Target"
    }
}
finally {
    if ($workbook -ne $null) { try { $workbook.Close($false) } catch {} }
    if ($solverWorkbook -ne $null) { try { $solverWorkbook.Close($false) } catch {} }
    if ($excel -ne $null) { try { $excel.Quit() } catch {} }
    foreach ($value in @($sheet, $workbook, $solverWorkbook, $excel)) {
        if ($value -ne $null -and [Runtime.InteropServices.Marshal]::IsComObject($value)) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($value)
        }
    }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
