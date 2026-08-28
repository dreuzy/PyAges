// Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
// Contributor: Jean-Raynald de Dreuzy
// SPDX-License-Identifier: CECILL-2.1

using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace TracerLpmRunner;

internal static class Program
{
    // A batch may intentionally run several isolated Excel instances in
    // parallel. Each runner therefore needs its own trace file; a shared file
    // made concurrent File.WriteAllText/File.AppendAllText calls fail randomly.
    private static readonly string DiagnosticTracePath = Path.Combine(
        Path.GetTempPath(), $"tracerlpm-runner-diagnostic-{Environment.ProcessId}.log");
    private const int MsoAutomationSecurityLow = 1;
    private const int XlCalculationStateDone = 0;
    private const int XlSheetVisible = -1;
    private const int RpcECallRejected = unchecked((int)0x80010001);
    private const int RpcEServerCallRetryLater = unchecked((int)0x8001010A);
    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint hWnd, out uint processId);

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            File.WriteAllText(DiagnosticTracePath, $"{DateTimeOffset.Now:O} runner start{Environment.NewLine}");
            if (args.Length == 4 && args.Any(item => item.Equals("--target", StringComparison.OrdinalIgnoreCase)))
            {
                var preparation = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                for (var index = 0; index < args.Length; index += 2)
                    preparation[args[index][2..]] = Path.GetFullPath(args[index + 1]);
                var preparationConfig = LoadYaml<RunnerConfig>(preparation["config"]);
                PrepareFourTracerWorkbook(preparationConfig, preparation["target"]);
                return 0;
            }
            var options = ParseArguments(args);
            var config = LoadYaml<RunnerConfig>(options["config"]);
            var map = LoadYaml<WorkbookMap>(Path.GetFullPath(config.WorkbookMapPath));
            var cases = ResolveCasePaths(
                LoadYaml<List<CaseDefinition>>(options["cases"]),
                Path.GetDirectoryName(options["cases"])!);
            var requestedCase = Environment.GetEnvironmentVariable("TRACERLPM_CASE_ID");
            if (!string.IsNullOrWhiteSpace(requestedCase))
                cases = cases.Where(item => string.Equals(item.CaseId, requestedCase,
                    StringComparison.OrdinalIgnoreCase)).ToList();
            var requestedLimit = Environment.GetEnvironmentVariable("TRACERLPM_CASE_LIMIT");
            if (int.TryParse(requestedLimit, out var caseLimit) && caseLimit > 0)
                cases = cases.Take(caseLimit).ToList();
            ValidateInputs(config, map, cases);

            Directory.CreateDirectory(config.OutputRoot);
            var results = new List<RunResult>();
            void Publish(RunResult result)
            {
                results.Add(result);
                WriteCaseReports(config.OutputRoot, result);
                Console.WriteLine(
                    $"{result.CaseId}: {result.Status}; {result.Model1}={result.Model1PointCount} points; {result.Model2}={result.Model2PointCount} points");
            }
            if (config.ReuseExcelSession)
                RunSession(config, map, cases, Publish);
            else
                foreach (var definition in cases)
                    Publish(Run(config, map, definition));

            WriteBatchReports(config.OutputRoot, results);

            return results.All(result => result.Status == "success") ? 0 : 1;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            return 1;
        }
    }

    private static void PrepareFourTracerWorkbook(RunnerConfig config, string targetPath)
    {
        var preparationLog = Path.Combine(config.OutputRoot, "four-tracer-preparation.log");
        Directory.CreateDirectory(config.OutputRoot);
        File.WriteAllText(preparationLog, $"{DateTimeOffset.Now:O} start{Environment.NewLine}");
        void Log(string message) => File.AppendAllText(preparationLog,
            $"{DateTimeOffset.Now:O} {message}{Environment.NewLine}");
        if (File.Exists(targetPath))
            throw new IOException($"La cible existe déjà : {targetPath}");
        File.Copy(Path.GetFullPath(config.WorkbookPath), targetPath, false);
        dynamic? excel = null;
        dynamic? workbook = null;
        dynamic? sheet = null;
        var excelProcessId = 0;
        try
        {
            var excelType = Type.GetTypeFromProgID("Excel.Application", true)
                ?? throw new InvalidOperationException("Excel.Application indisponible.");
            excel = Activator.CreateInstance(excelType)
                ?? throw new InvalidOperationException("Impossible de créer Excel.");
            excel.Visible = true;
            excel.DisplayAlerts = false;
            excel.EnableEvents = false;
            excel.AutomationSecurity = MsoAutomationSecurityLow;
            excelProcessId = ProcessIdFromExcelWindow((nint)excel.Hwnd);
            if (!(bool)excel.RegisterXLL(config.XllPath))
                throw new InvalidOperationException($"XLL non chargeable : {config.XllPath}");
            Log("XLL registered");
            workbook = excel.Workbooks.Open(targetPath, 0, false);
            Log("workbook open");
            sheet = workbook.Worksheets["Samples"];
            Log("Samples sheet acquired");
            dynamic tracerDefinitions = workbook.Worksheets["Tracers"];
            var tracers = new[] { "CFC-11", "CFC-12", "CFC-113", "SF6" };
            var northernHemisphereColumns = new[] { 6, 5, 7, 9 };
            for (var slot = 1; slot <= 10; slot++)
            {
                sheet.Cells[3, slot + 3].Value2 = slot <= tracers.Length ? tracers[slot - 1] : "EMPTY";
                Log($"linked cell row 3, column {slot + 3} written");
            }
            Log("tracer linked cells written");
            for (var slot = 1; slot <= 10; slot++)
            {
                var tracer = slot <= tracers.Length ? tracers[slot - 1] : "EMPTY";
                var sampleColumn = slot + 3;
                var tracerRow = 11;
                if (tracer == "EMPTY")
                {
                    sheet.Range[sheet.Cells[4, sampleColumn], sheet.Cells[5, sampleColumn]].ClearContents();
                    dynamic tracerInput = workbook.Worksheets["TracerInput"];
                    tracerInput.Range[tracerInput.Cells[2, slot + 2], tracerInput.Cells[6000, slot + 2]]
                        .ClearContents();
                    Log($"empty tracer slot {slot} cleared");
                    continue;
                }
                else
                {
                    while (!string.IsNullOrEmpty(Convert.ToString(tracerDefinitions.Cells[tracerRow, 1].Value2,
                               CultureInfo.InvariantCulture)) &&
                           !string.Equals(Convert.ToString(tracerDefinitions.Cells[tracerRow, 2].Value2,
                               CultureInfo.InvariantCulture), tracer, StringComparison.OrdinalIgnoreCase))
                        tracerRow++;
                    if (string.IsNullOrEmpty(Convert.ToString(tracerDefinitions.Cells[tracerRow, 1].Value2,
                            CultureInfo.InvariantCulture)))
                        throw new InvalidDataException($"Traceur absent de la feuille Tracers : {tracer}");
                    sheet.Cells[4, sampleColumn].Value2 = tracerDefinitions.Cells[tracerRow, 3].Value2;
                    sheet.Cells[5, sampleColumn].Value2 = tracerDefinitions.Cells[tracerRow, 4].Value2;
                }
                Log($"sample metadata slot {slot} written");
                dynamic inputSheet = workbook.Worksheets["TracerInput"];
                var cutoffRow = 19;
                while (cutoffRow <= 6000 &&
                       Convert.ToDouble(inputSheet.Cells[cutoffRow, 1].Value2 ?? 0,
                           CultureInfo.InvariantCulture) >= 1800.0)
                    cutoffRow++;
                inputSheet.Range[inputSheet.Cells[cutoffRow, 1], inputSheet.Cells[6000, 12]].ClearContents();
                Log($"TracerInput truncated below 1800 at row {cutoffRow}");
                var inputColumn = slot + 2;
                inputSheet.Cells[2, inputColumn].Value2 = tracer;
                inputSheet.Cells[3, inputColumn].Value2 = tracerDefinitions.Cells[tracerRow, 3].Value2;
                inputSheet.Cells[4, inputColumn].Value2 = "Northern Hemisphere";
                inputSheet.Cells[6, inputColumn].Value2 = "Unsaturated";
                inputSheet.Cells[7, inputColumn].Value2 = "travel time";
                inputSheet.Cells[8, inputColumn].Value2 = tracerDefinitions.Cells[tracerRow, 5].Value2;
                inputSheet.Cells[9, inputColumn].Value2 = 0;
                inputSheet.Cells[11, inputColumn].Value2 = "Half-life";
                inputSheet.Cells[12, inputColumn].Value2 = tracerDefinitions.Cells[tracerRow, 4].Value2;
                inputSheet.Cells[13, inputColumn].Value2 = "Decay rate";
                var halfLife = Convert.ToDouble(tracerDefinitions.Cells[tracerRow, 4].Value2 ?? 0,
                    CultureInfo.InvariantCulture);
                inputSheet.Cells[14, inputColumn].Value2 = halfLife == 0 ? 0 : Math.Log(2) / halfLife;
                inputSheet.Cells[16, inputColumn].Value2 = "Scaling Factor";
                inputSheet.Cells[17, inputColumn].Value2 = 1;
                dynamic dates = inputSheet.Range[inputSheet.Cells[19, 1], inputSheet.Cells[cutoffRow - 1, 1]];
                dynamic values = inputSheet.Range[inputSheet.Cells[19, inputColumn],
                                                   inputSheet.Cells[cutoffRow - 1, inputColumn]];
                Log($"macro RetrieveTracerData slot {slot} start");
                excel.Run($"'{workbook.Name}'!RetrieveTracerData", dates, values,
                    northernHemisphereColumns[slot - 1]);
                Log($"macro RetrieveTracerData slot {slot} done");
            }
            Log("macro UpdateTracersForCalcSheets start");
            excel.Run($"'{workbook.Name}'!UpdateTracersForCalcSheets");
            Log("macro UpdateTracersForCalcSheets done");
            // Workbook_Open displays a false "Solver not found" warning when
            // Solver was loaded by opening the XLAM directly. The runner then
            // explicitly replays every event on which it depends.
            excel.EnableEvents = false;
            workbook.Save();
            Console.WriteLine($"Four-tracer workbook saved: {targetPath}");
        }
        finally
        {
            if (workbook is not null) { try { workbook.Close(false); } catch { } ReleaseCom(workbook); }
            if (excel is not null) { try { excel.Quit(); } catch { } ReleaseCom(excel); }
            ReleaseCom(sheet);
            GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect(); GC.WaitForPendingFinalizers();
            if (excelProcessId > 0) WaitForOwnedExcelExit(excelProcessId, TimeSpan.FromSeconds(2));
        }
    }

    private static Dictionary<string, string> ParseArguments(string[] args)
    {
        if (args.Length != 4)
        {
            throw new ArgumentException(
                "Usage: TracerLpmRunner --config <runner-config.yaml> --cases <cases.yaml>");
        }

        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < args.Length; index += 2)
        {
            if (!args[index].StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException($"Argument invalide : {args[index]}");
            result[args[index][2..]] = Path.GetFullPath(args[index + 1]);
        }

        if (!result.ContainsKey("config") || !result.ContainsKey("cases"))
            throw new ArgumentException("Les options --config et --cases sont obligatoires.");
        return result;
    }

    private static T LoadYaml<T>(string path)
    {
        if (Path.GetExtension(path).ToLowerInvariant() is not (".yaml" or ".yml"))
            throw new InvalidDataException($"Un fichier YAML est requis : {path}");
        return new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build()
            .Deserialize<T>(File.ReadAllText(path))
            ?? throw new InvalidDataException($"YAML vide : {path}");
    }

    private static List<CaseDefinition> ResolveCasePaths(
        IEnumerable<CaseDefinition> definitions, string casesDirectory)
    {
        return definitions.Select(definition => definition.InputHistory is null
            ? definition
            : definition with
            {
                InputHistory = definition.InputHistory with
                {
                    Path = Path.GetFullPath(definition.InputHistory.Path, casesDirectory)
                }
            }).ToList();
    }

    private static void ValidateInputs(RunnerConfig config, WorkbookMap map, IReadOnlyList<CaseDefinition> cases)
    {
        ValidateFileHash(config.WorkbookPath, config.WorkbookSha256, "classeur");
        ValidateFileHash(config.XllPath, config.XllSha256, "XLL");
        if (!EqualsHash(config.WorkbookSha256, map.WorkbookSha256))
            throw new InvalidDataException("La cartographie ne correspond pas au hash du classeur configuré.");
        if (cases.Count == 0) throw new InvalidDataException("Aucun cas à exécuter.");
        var duplicate = cases.GroupBy(item => item.CaseId, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault(group => group.Count() > 1);
        if (duplicate is not null) throw new InvalidDataException($"caseId dupliqué : {duplicate.Key}");
        foreach (var definition in cases.Where(item => item.InputHistory is not null))
        {
            var input = definition.InputHistory!;
            ValidateFileHash(Path.GetFullPath(input.Path), input.Sha256, $"chronique du cas {definition.CaseId}");
            if (!string.Equals(input.After, "hold_last", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Seule la politique after=hold_last est qualifiée.");
            if (input.TargetTracers.Length == 0)
                throw new InvalidDataException($"Aucun traceur cible pour {definition.CaseId}.");
            foreach (var tracer in input.TargetTracers)
                if (!map.InputValueColumns.ContainsKey(tracer))
                    throw new InvalidDataException($"Colonne d'entrée non cartographiée pour '{tracer}'.");
        }
        foreach (var definition in cases.Where(item => item.Model1 is "EPM" or "DM" || item.Model2 is "EPM" or "DM"))
        {
            if (definition.ModelParameter is null || definition.ModelParameter <= 0)
                throw new InvalidDataException($"Paramètre de modèle positif requis pour {definition.CaseId}.");
            if ((definition.Model1 == "EPM" || definition.Model2 == "EPM") && definition.ModelParameter < 0)
                throw new InvalidDataException($"Le ratio EPM piston/exponentiel doit être positif ou nul pour {definition.CaseId}.");
        }
        foreach (var definition in cases.Where(item => item.Fit is not null))
        {
            var fit = definition.Fit!;
            if (map.Fit is null) throw new InvalidDataException("Cartographie fit absente.");
            if (fit.InitialAges.Length == 0 || fit.AgeLower >= fit.AgeUpper)
                throw new InvalidDataException($"Bornes ou initialisations d'inversion invalides pour {definition.CaseId}.");
            if (fit.Observations.Count == 0)
                throw new InvalidDataException($"Aucune observation d'inversion pour {definition.CaseId}.");
            if (fit.InitialAges.Any(value => value < fit.AgeLower || value > fit.AgeUpper))
                throw new InvalidDataException($"Initialisation hors bornes pour {definition.CaseId}.");
            if (fit.InitialModelParameters is not null)
            {
                if (fit.InitialModelParameters.Length != fit.InitialAges.Length
                    || fit.ModelParameterLower is null || fit.ModelParameterUpper is null
                    || fit.ModelParameterLower >= fit.ModelParameterUpper)
                    throw new InvalidDataException($"Paramètres secondaires invalides pour {definition.CaseId}.");
                if (fit.InitialModelParameters.Any(value => value < fit.ModelParameterLower || value > fit.ModelParameterUpper))
                    throw new InvalidDataException($"Paramètre secondaire initial hors bornes pour {definition.CaseId}.");
            }
        }
    }

    private static RunResult Run(RunnerConfig config, WorkbookMap map, CaseDefinition definition)
    {
        var startedAt = DateTimeOffset.Now;
        var stopwatch = Stopwatch.StartNew();
        var safeId = string.Concat(definition.CaseId.Select(c => char.IsLetterOrDigit(c) || c is '-' or '_' ? c : '-'));
        if (string.IsNullOrWhiteSpace(safeId)) safeId = "case";
        var runId = $"{safeId}-{startedAt:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}";
        var workbookPath = Path.GetFullPath(config.WorkbookPath);
        var xllPath = Path.GetFullPath(config.XllPath);
        var runDirectory = Path.Combine(Path.GetFullPath(config.WorkRoot), runId);
        Directory.CreateDirectory(runDirectory);
        var workingWorkbook = Path.Combine(runDirectory, Path.GetFileName(workbookPath));
        File.Copy(workbookPath, workingWorkbook, false);

        dynamic? excel = null;
        dynamic? workbook = null;
        var excelProcessId = 0;
        try
        {
            DiagnosticTrace("creating Excel");
            var excelType = Type.GetTypeFromProgID("Excel.Application", true)
                ?? throw new InvalidOperationException("Excel.Application indisponible.");
            excel = Activator.CreateInstance(excelType)
                ?? throw new InvalidOperationException("Impossible de créer Excel.");
            DiagnosticTrace("Excel created");
            excel.Visible = config.ExcelVisible;
            excel.DisplayAlerts = false;
            // The runner replays every required sheet event explicitly. Disabling
            // events during Open avoids TracerLPM's misleading Solver startup box
            // when SOLVER.XLAM was loaded directly in this Excel instance.
            excel.EnableEvents = false;
            excel.AutomationSecurity = MsoAutomationSecurityLow;
            excelProcessId = ProcessIdFromExcelWindow((nint)excel.Hwnd);
            DiagnosticTrace($"Excel configured; pid={excelProcessId}");
            EnsureAddInInstalled(excel, "SOLVER.XLAM", null);
            DiagnosticTrace("Solver add-in ready");
            EnsureAddInInstalled(excel, Path.GetFileName(xllPath), xllPath);
            DiagnosticTrace("TracerLPM XLL ready");
            workbook = excel.Workbooks.Open(workingWorkbook, 0, false);
            DiagnosticTrace("workbook open");
            excel.EnableEvents = true;
            excel.Run($"'{workbook.Name}'!FillSampleBoxes");
            DiagnosticTrace("sample controls initialized");
            ConfigureCase(excel, workbook, map, definition);
            DiagnosticTrace("case configured");
            if (definition.ObservationYear is not null)
            {
                dynamic graphSheet = workbook.Worksheets[map.GraphSheet];
                try { WriteCell(graphSheet, map.GraphObservationYearCell, definition.ObservationYear.Value); }
                finally { ReleaseCom(graphSheet); }
                RunWorkbookMacro(excel, workbook, map, "ModelCombo1_Change");
                RunWorkbookMacro(excel, workbook, map, "ModelCombo2_Change");
            }
            if (definition.ModelParameter is not null)
            {
                dynamic graphSheet = workbook.Worksheets[map.GraphSheet];
                try
                {
                    // The model-selection macros initialise these cells with their
                    // defaults. Set the requested parameter afterwards while Excel
                    // events are enabled: the sheet Change event propagates it to
                    // the hidden calculation sheet. Do not replay ModelCombo here,
                    // because that would restore the default.
                    WriteCell(graphSheet, map.GraphModel1ParameterCell, definition.ModelParameter.Value);
                    WriteCell(graphSheet, map.GraphModel2ParameterCell, definition.ModelParameter.Value);
                }
                finally { ReleaseCom(graphSheet); }
                VerifyModelParameter(workbook, map, definition.ModelParameter.Value);
            }
            if (definition.InputHistory is not null)
            {
                ImportInputHistory(excel, workbook, map, definition.InputHistory);
                VerifyInputHistory(workbook, map, definition.InputHistory);
                DiagnosticTrace("input history imported and verified");
            }
            CalculateAndWait(excel, TimeSpan.FromSeconds(config.TimeoutSeconds));
            DiagnosticTrace("pre-fit calculation complete");
            var fitResult = definition.Fit is null
                ? null
                : RunFit(excel, workbook, map, definition, definition.Fit,
                    TimeSpan.FromSeconds(config.TimeoutSeconds));
            DiagnosticTrace("fit complete");

            var model1 = RetryTransientCom(
                () => ReadModelSeries(workbook, map, map.OutputRanges.Model1Block,
                    definition.XAxis, definition.YAxis),
                $"{definition.CaseId}: lecture de la série du modèle 1");
            var model2 = RetryTransientCom(
                () => ReadModelSeries(workbook, map, map.OutputRanges.Model2Block,
                    definition.XAxis, definition.YAxis),
                $"{definition.CaseId}: lecture de la série du modèle 2");
            var sample = ReadNumericRange(workbook, map.SampleSheet, map.OutputRanges.Sample);
            var modelAges = ReadNumericRange(workbook, map.OutputSheet, map.OutputRanges.ModelAges);
            var model1Hash = HashNumbers(model1);
            var model2Hash = HashNumbers(model2);
            var model1Matches = MatchesOptionalHash(model1Hash, definition.ExpectedModel1Sha256);
            var model2Matches = MatchesOptionalHash(model2Hash, definition.ExpectedModel2Sha256);
            stopwatch.Stop();
            return new RunResult
            {
                Status = model1Matches && model2Matches ? "success" : "invalid_output",
                CaseId = definition.CaseId, RunId = runId, StartedAt = startedAt,
                DurationSeconds = stopwatch.Elapsed.TotalSeconds,
                WorkbookSha256 = HashFile(workbookPath), XllSha256 = HashFile(xllPath),
                WorkingWorkbook = workingWorkbook,
                InputHistoryPath = definition.InputHistory is null ? null : Path.GetFullPath(definition.InputHistory.Path),
                InputHistorySha256 = definition.InputHistory?.Sha256,
                Sample = definition.Sample,
                ObservationYear = definition.ObservationYear,
                TracerlpmEffectiveObservationYear = definition.TracerlpmEffectiveObservationYear,
                ModelParameter = definition.ModelParameter,
                Model1 = definition.Model1, Model2 = definition.Model2,
                XAxis = definition.XAxis, YAxis = definition.YAxis,
                Model1PointCount = model1.Count / 2, Model2PointCount = model2.Count / 2,
                Model1Sha256 = model1Hash, Model2Sha256 = model2Hash,
                ExpectedModel1Sha256 = definition.ExpectedModel1Sha256,
                ExpectedModel2Sha256 = definition.ExpectedModel2Sha256,
                Model1MatchesExpected = model1Matches, Model2MatchesExpected = model2Matches,
                SampleX = sample[0], SampleY = sample[1], ExcelProcessId = excelProcessId,
                Model1Points = ToPoints(model1), Model2Points = ToPoints(model2),
                ModelAges = modelAges,
                Fit = fitResult
            };
        }
        finally
        {
            if (workbook is not null) { try { workbook.Close(false); } catch { } ReleaseCom(workbook); }
            if (excel is not null) { try { excel.Quit(); } catch { } ReleaseCom(excel); }
            GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect(); GC.WaitForPendingFinalizers();
            if (excelProcessId > 0) WaitForOwnedExcelExit(excelProcessId, TimeSpan.FromSeconds(2));
        }
    }

    private static void RunSession(RunnerConfig config, WorkbookMap map,
        IReadOnlyList<CaseDefinition> cases, Action<RunResult> publish)
    {
        var sessionId = $"session-{DateTimeOffset.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}";
        var workbookPath = Path.GetFullPath(config.WorkbookPath);
        var xllPath = Path.GetFullPath(config.XllPath);
        var sessionDirectory = Path.Combine(Path.GetFullPath(config.WorkRoot), sessionId);
        Directory.CreateDirectory(sessionDirectory);
        var workingWorkbook = Path.Combine(sessionDirectory, Path.GetFileName(workbookPath));
        File.Copy(workbookPath, workingWorkbook, false);
        var workbookHash = HashFile(workbookPath);
        var xllHash = HashFile(xllPath);

        dynamic? excel = null;
        dynamic? workbook = null;
        var excelProcessId = 0;
        string? importedInputSignature = null;
        try
        {
            DiagnosticTrace("creating shared Excel session");
            var excelType = Type.GetTypeFromProgID("Excel.Application", true)
                ?? throw new InvalidOperationException("Excel.Application indisponible.");
            excel = Activator.CreateInstance(excelType)
                ?? throw new InvalidOperationException("Impossible de créer Excel.");
            DiagnosticTrace("shared Excel created");
            excel.Visible = config.ExcelVisible;
            excel.DisplayAlerts = false;
            excel.EnableEvents = false;
            excel.AutomationSecurity = MsoAutomationSecurityLow;
            excelProcessId = ProcessIdFromExcelWindow((nint)excel.Hwnd);
            DiagnosticTrace($"shared Excel configured; pid={excelProcessId}");
            EnsureAddInInstalled(excel, "SOLVER.XLAM", null);
            EnsureAddInInstalled(excel, Path.GetFileName(xllPath), xllPath);
            workbook = excel.Workbooks.Open(workingWorkbook, 0, false);
            DiagnosticTrace("shared workbook open");
            excel.EnableEvents = true;
            excel.Run($"'{workbook.Name}'!FillSampleBoxes");
            DiagnosticTrace("shared sample controls initialized");

            foreach (var definition in cases)
            {
                var signature = InputHistorySignature(definition.InputHistory);
                var importInput = signature is not null && signature != importedInputSignature;
                var result = RunInOpenWorkbook(
                    config, map, definition, excel, workbook, workingWorkbook,
                    excelProcessId, workbookHash, xllHash, importInput);
                if (importInput) importedInputSignature = signature;
                publish(result);
            }
        }
        finally
        {
            if (workbook is not null) { try { workbook.Close(false); } catch { } ReleaseCom(workbook); }
            if (excel is not null) { try { excel.Quit(); } catch { } ReleaseCom(excel); }
            GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect(); GC.WaitForPendingFinalizers();
            if (excelProcessId > 0) WaitForOwnedExcelExit(excelProcessId, TimeSpan.FromSeconds(2));
        }
    }

    private static string? InputHistorySignature(InputHistoryDefinition? input)
    {
        if (input is null) return null;
        var columns = input.SourceColumns is null
            ? ""
            : string.Join(";", input.SourceColumns.OrderBy(item => item.Key)
                .Select(item => $"{item.Key}={item.Value}"));
        return string.Join("|", Path.GetFullPath(input.Path), input.Sha256,
            string.Join(",", input.TargetTracers), columns,
            input.Before.ToString("R", CultureInfo.InvariantCulture), input.After);
    }

    private static RunResult RunInOpenWorkbook(RunnerConfig config, WorkbookMap map,
        CaseDefinition definition, dynamic excel, dynamic workbook, string workingWorkbook,
        int excelProcessId, string workbookHash, string xllHash, bool importInputHistory)
    {
        var startedAt = DateTimeOffset.Now;
        var stopwatch = Stopwatch.StartNew();
        var safeId = string.Concat(definition.CaseId.Select(
            c => char.IsLetterOrDigit(c) || c is '-' or '_' ? c : '-'));
        if (string.IsNullOrWhiteSpace(safeId)) safeId = "case";
        var runId = $"{safeId}-{startedAt:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}";

        ConfigureCase(excel, workbook, map, definition);
        DiagnosticTrace($"{definition.CaseId}: case configured in shared session");
        if (definition.ObservationYear is not null)
        {
            dynamic graphSheet = workbook.Worksheets[map.GraphSheet];
            try { WriteCell(graphSheet, map.GraphObservationYearCell, definition.ObservationYear.Value); }
            finally { ReleaseCom(graphSheet); }
            RunWorkbookMacro(excel, workbook, map, "ModelCombo1_Change");
            RunWorkbookMacro(excel, workbook, map, "ModelCombo2_Change");
        }
        if (definition.ModelParameter is not null)
        {
            dynamic graphSheet = workbook.Worksheets[map.GraphSheet];
            try
            {
                WriteCell(graphSheet, map.GraphModel1ParameterCell, definition.ModelParameter.Value);
                WriteCell(graphSheet, map.GraphModel2ParameterCell, definition.ModelParameter.Value);
            }
            finally { ReleaseCom(graphSheet); }
            VerifyModelParameter(workbook, map, definition.ModelParameter.Value);
        }
        if (importInputHistory && definition.InputHistory is not null)
        {
            ImportInputHistory(excel, workbook, map, definition.InputHistory);
            VerifyInputHistory(workbook, map, definition.InputHistory);
            DiagnosticTrace($"{definition.CaseId}: input history imported and verified");
        }
        CalculateAndWait(excel, TimeSpan.FromSeconds(config.TimeoutSeconds));
        var fitResult = definition.Fit is null
            ? null
            : RunFit(excel, workbook, map, definition, definition.Fit,
                TimeSpan.FromSeconds(config.TimeoutSeconds));
        DiagnosticTrace($"{definition.CaseId}: shared-session fit complete");

        var model1 = RetryTransientCom(
            () => ReadModelSeries(workbook, map, map.OutputRanges.Model1Block,
                definition.XAxis, definition.YAxis),
            $"{definition.CaseId}: lecture de la série du modèle 1");
        var model2 = RetryTransientCom(
            () => ReadModelSeries(workbook, map, map.OutputRanges.Model2Block,
                definition.XAxis, definition.YAxis),
            $"{definition.CaseId}: lecture de la série du modèle 2");
        var sample = ReadNumericRange(workbook, map.SampleSheet, map.OutputRanges.Sample);
        var modelAges = ReadNumericRange(workbook, map.OutputSheet, map.OutputRanges.ModelAges);
        var model1Hash = HashNumbers(model1);
        var model2Hash = HashNumbers(model2);
        var model1Matches = MatchesOptionalHash(model1Hash, definition.ExpectedModel1Sha256);
        var model2Matches = MatchesOptionalHash(model2Hash, definition.ExpectedModel2Sha256);
        stopwatch.Stop();
        return new RunResult
        {
            Status = model1Matches && model2Matches ? "success" : "invalid_output",
            CaseId = definition.CaseId, RunId = runId, StartedAt = startedAt,
            DurationSeconds = stopwatch.Elapsed.TotalSeconds,
            WorkbookSha256 = workbookHash, XllSha256 = xllHash,
            WorkingWorkbook = workingWorkbook,
            InputHistoryPath = definition.InputHistory is null
                ? null : Path.GetFullPath(definition.InputHistory.Path),
            InputHistorySha256 = definition.InputHistory?.Sha256,
            Sample = definition.Sample,
            ObservationYear = definition.ObservationYear,
            TracerlpmEffectiveObservationYear = definition.TracerlpmEffectiveObservationYear,
            ModelParameter = definition.ModelParameter,
            Model1 = definition.Model1, Model2 = definition.Model2,
            XAxis = definition.XAxis, YAxis = definition.YAxis,
            Model1PointCount = model1.Count / 2, Model2PointCount = model2.Count / 2,
            Model1Sha256 = model1Hash, Model2Sha256 = model2Hash,
            ExpectedModel1Sha256 = definition.ExpectedModel1Sha256,
            ExpectedModel2Sha256 = definition.ExpectedModel2Sha256,
            Model1MatchesExpected = model1Matches, Model2MatchesExpected = model2Matches,
            SampleX = sample[0], SampleY = sample[1], ExcelProcessId = excelProcessId,
            Model1Points = ToPoints(model1), Model2Points = ToPoints(model2),
            ModelAges = modelAges,
            Fit = fitResult
        };
    }

    private static IReadOnlyList<SeriesPoint> ToPoints(IReadOnlyList<double> values)
    {
        var points = new List<SeriesPoint>(values.Count / 2);
        for (var index = 0; index < values.Count; index += 2)
            points.Add(new SeriesPoint { Index = index / 2, X = values[index], Y = values[index + 1] });
        return points;
    }

    private static void WriteCaseReports(string outputRoot, RunResult result)
    {
        File.WriteAllText(Path.Combine(outputRoot, $"{result.RunId}.json"),
            JsonSerializer.Serialize(result, Json));
        var csv = new StringBuilder("case_id,model,point_index,x,y\n");
        AppendSeries(csv, result.CaseId, result.Model1, result.Model1Points);
        AppendSeries(csv, result.CaseId, result.Model2, result.Model2Points);
        File.WriteAllText(Path.Combine(outputRoot, $"{result.RunId}-series.csv"), csv.ToString(),
            new UTF8Encoding(true));
    }

    private static void AppendSeries(StringBuilder csv, string caseId, string model,
        IReadOnlyList<SeriesPoint> points)
    {
        foreach (var point in points)
        {
            csv.Append(Csv(caseId)).Append(',').Append(Csv(model)).Append(',')
                .Append(point.Index).Append(',')
                .Append(point.X.ToString("R", CultureInfo.InvariantCulture)).Append(',')
                .AppendLine(point.Y.ToString("R", CultureInfo.InvariantCulture));
        }
    }

    private static void WriteBatchReports(string outputRoot, IReadOnlyList<RunResult> results)
    {
        var reportId = $"simulation-report-{DateTimeOffset.Now:yyyyMMdd-HHmmss}";
        File.WriteAllText(Path.Combine(outputRoot, $"{reportId}.json"),
            JsonSerializer.Serialize(results, Json));

        var csv = new StringBuilder(
            "case_id,status,sample,model1,model2,x_axis,y_axis,model1_points,model2_points,model1_sha256,model2_sha256,has_expected_hashes,model1_matches_expected,model2_matches_expected,duration_seconds\n");
        foreach (var result in results)
        {
            csv.Append(Csv(result.CaseId)).Append(',').Append(result.Status).Append(',')
                .Append(Csv(result.Sample)).Append(',').Append(Csv(result.Model1)).Append(',')
                .Append(Csv(result.Model2)).Append(',').Append(Csv(result.XAxis)).Append(',')
                .Append(Csv(result.YAxis)).Append(',').Append(result.Model1PointCount).Append(',')
                .Append(result.Model2PointCount).Append(',').Append(result.Model1Sha256).Append(',')
                .Append(result.Model2Sha256).Append(',').Append(HasExpectedHashes(result)).Append(',')
                .Append(result.Model1MatchesExpected).Append(',')
                .Append(result.Model2MatchesExpected).Append(',')
                .AppendLine(result.DurationSeconds.ToString("F3", CultureInfo.InvariantCulture));
        }
        File.WriteAllText(Path.Combine(outputRoot, $"{reportId}.csv"), csv.ToString(), new UTF8Encoding(true));

        var markdown = new StringBuilder();
        markdown.AppendLine("# Rapport de simulations TracerLPM").AppendLine()
            .AppendLine($"Généré le {DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss zzz}.").AppendLine()
            .AppendLine($"Cas exécutés : {results.Count}; succès : {results.Count(r => r.Status == "success")}; échecs : {results.Count(r => r.Status != "success")}.")
            .AppendLine().AppendLine("| Cas | Échantillon | Modèles | Axes | Points | Validation | Durée |").AppendLine("|---|---|---|---|---:|---|---:|");
        foreach (var result in results)
        {
            var validation = !HasExpectedHashes(result)
                ? "exécuté (sans référence)"
                : result.Model1MatchesExpected && result.Model2MatchesExpected ? "conforme" : "non conforme";
            markdown.AppendLine($"| {result.CaseId} | {result.Sample} | {result.Model1} / {result.Model2} | {result.XAxis} / {result.YAxis} | {result.Model1PointCount} + {result.Model2PointCount} | {validation} | {result.DurationSeconds:F1} s |");
        }
        markdown.AppendLine().AppendLine("## Empreintes numériques").AppendLine();
        foreach (var result in results)
        {
            markdown.AppendLine($"- `{result.CaseId}` — {result.Model1}: `{result.Model1Sha256}`; {result.Model2}: `{result.Model2Sha256}`");
        }
        markdown.AppendLine().AppendLine("Les cas sans empreinte attendue attestent une exécution réussie, mais pas encore une qualification scientifique indépendante.");
        File.WriteAllText(Path.Combine(outputRoot, $"{reportId}.md"), markdown.ToString(), new UTF8Encoding(false));
    }

    private static string Csv(string value) =>
        value.IndexOfAny([',', '"', '\r', '\n']) >= 0 ? $"\"{value.Replace("\"", "\"\"")}\"" : value;

    private static bool HasExpectedHashes(RunResult result) =>
        !string.IsNullOrWhiteSpace(result.ExpectedModel1Sha256)
        && !string.IsNullOrWhiteSpace(result.ExpectedModel2Sha256);

    private static void ConfigureCase(dynamic excel, dynamic workbook, WorkbookMap map, CaseDefinition definition)
    {
        dynamic sheet = workbook.Worksheets[map.GraphSheet];
        sheet.Visible = XlSheetVisible;
        sheet.Activate();
        SelectListValue(sheet.OLEObjects(map.Controls.SamplesToGraph).Object, definition.Sample);
        SelectComboValue(sheet.OLEObjects(map.Controls.SampleToModel).Object, definition.Sample);
        SelectComboValue(sheet.OLEObjects(map.Controls.Model1).Object, definition.Model1);
        SelectComboValue(sheet.OLEObjects(map.Controls.Model2).Object, definition.Model2);
        SelectComboValue(sheet.OLEObjects(map.Controls.XAxis).Object, definition.XAxis);
        SelectComboValue(sheet.OLEObjects(map.Controls.YAxis).Object, definition.YAxis);
        foreach (var macro in map.EventMacros)
            RunWorkbookMacro(excel, workbook, map, macro);
    }

    private static void RunWorkbookMacro(dynamic excel, dynamic workbook, WorkbookMap map, string macro)
    {
        var fullName = $"'{workbook.Name}'!{map.GraphSheetCodeName}.{macro}";
        try { excel.Run(fullName); }
        catch (Exception exception)
        {
            throw new InvalidOperationException($"Échec de l'événement VBA {fullName}.", exception);
        }
    }

    private static void RunSheetMacro(dynamic excel, dynamic workbook, string sheetCodeName, string macro)
    {
        var fullName = $"'{workbook.Name}'!{sheetCodeName}.{macro}";
        try { excel.Run(fullName); }
        catch (Exception exception)
        {
            throw new InvalidOperationException($"Échec de l'événement VBA {fullName}.", exception);
        }
    }

    private static void RunFirstAvailableSheetMacro(dynamic excel, dynamic workbook,
        string sheetCodeName, params string[] candidates)
    {
        var failures = new List<Exception>();
        foreach (var candidate in candidates)
        {
            try { RunSheetMacro(excel, workbook, sheetCodeName, candidate); return; }
            catch (Exception exception) { failures.Add(exception); }
        }
        throw new AggregateException(
            $"Aucun événement VBA disponible parmi: {string.Join(", ", candidates)}", failures);
    }

    private static FitResult RunFit(dynamic excel, dynamic workbook, WorkbookMap map,
        CaseDefinition definition, FitDefinition fit, TimeSpan timeout)
    {
        var fitMap = map.Fit ?? throw new InvalidDataException("Cartographie fit absente.");
        foreach (var tracer in fit.Observations.Keys)
            if (!fitMap.ObservationCells.ContainsKey(tracer))
                throw new InvalidDataException($"Cellule d'observation non cartographiée pour {tracer}.");
        dynamic sheet = workbook.Worksheets[fitMap.Sheet];
        try
        {
            sheet.Visible = XlSheetVisible;
            sheet.Activate();
            SelectComboValue(sheet.OLEObjects(fitMap.SampleControl).Object, fit.Sample);
            RunFirstAvailableSheetMacro(excel, workbook, fitMap.SheetCodeName,
                "SampleList_Change", "SampleList_Click");
            SelectComboValue(sheet.OLEObjects(fitMap.ModelControl).Object, fit.Model);
            RunSheetMacro(excel, workbook, fitMap.SheetCodeName, "ModelListCombo_Change");
            WriteCell(sheet, fitMap.ObservationYearCell,
                definition.ObservationYear ?? throw new InvalidDataException("Date d'inversion absente."));
            foreach (var observation in fit.Observations)
            {
                WriteCell(sheet, fitMap.ObservationCells[observation.Key], observation.Value);
                if (fitMap.DecayRateCells.TryGetValue(observation.Key, out var decayCell))
                    WriteCell(sheet, decayCell, 0.0);
            }
            WriteCell(sheet, fitMap.AgeLowerCell, fit.AgeLower);
            WriteCell(sheet, fitMap.AgeUpperCell, fit.AgeUpper);
            if (fit.InitialModelParameters is not null)
            {
                WriteCell(sheet, fitMap.ModelParameterLowerCell, fit.ModelParameterLower!.Value);
                WriteCell(sheet, fitMap.ModelParameterUpperCell, fit.ModelParameterUpper!.Value);
            }
            SelectListValues(sheet.OLEObjects(fitMap.TracerControl).Object, fit.Observations.Keys);
            RunSheetMacro(excel, workbook, fitMap.SheetCodeName, "TracerList_Change");
            var attempts = new List<FitAttempt>();
            for (var attemptIndex = 0; attemptIndex < fit.InitialAges.Length; attemptIndex++)
            {
                var initialAge = fit.InitialAges[attemptIndex];
                if (attemptIndex > 0)
                {
                    sheet = workbook.Worksheets[fitMap.Sheet];
                    sheet.Activate();
                }
                WriteCell(sheet, fitMap.AgeCell, initialAge);
                var initialModelParameter = fit.InitialModelParameters?[attemptIndex];
                if (initialModelParameter is not null)
                    WriteCell(sheet, fitMap.ModelParameterCell, initialModelParameter.Value);
                CalculateAndWait(excel, timeout);
                var initialObjective = ReadNumericCell(workbook, fitMap.Sheet, fitMap.ResultObjectiveCell);
                var calculated = fit.Observations.Keys.ToDictionary(
                    tracer => tracer,
                    tracer => (double)ReadNumericCell(workbook, fitMap.Sheet, fitMap.CalculatedCells[tracer]),
                    StringComparer.OrdinalIgnoreCase);
                attempts.Add(new FitAttempt
                {
                    InitialAge = initialAge,
                    InitialModelParameter = initialModelParameter,
                    InitialObjective = initialObjective,
                    EstimatedAge = initialAge,
                    EstimatedModelParameter = initialModelParameter,
                    Objective = initialObjective,
                    InitialCalculatedConcentrations = calculated,
                    CalculatedConcentrations = calculated
                });
            }
            var bestIndex = attempts.IndexOf(attempts.MinBy(item => item.InitialObjective)
                ?? throw new InvalidDataException("Aucune initialisation Solver."));
            var bestStart = attempts[bestIndex];
            sheet = workbook.Worksheets[fitMap.Sheet];
            sheet.Activate();
            WriteCell(sheet, fitMap.AgeCell, bestStart.InitialAge);
            if (bestStart.InitialModelParameter is not null)
                WriteCell(sheet, fitMap.ModelParameterCell, bestStart.InitialModelParameter.Value);
            CalculateAndWait(excel, timeout);
            var solverStatus = RunSolver(excel, sheet, fitMap, fit.InitialModelParameters is not null);
            CalculateAndWait(excel, timeout);
            var solverAge = ReadNumericCell(workbook, fitMap.Sheet, fitMap.ResultAgeCell);
            var solverModelParameter = fit.InitialModelParameters is null ? null
                : ReadNumericCell(workbook, fitMap.Sheet, fitMap.ModelParameterCell);
            var solverObjective = ReadNumericCell(workbook, fitMap.Sheet, fitMap.ResultObjectiveCell);
            var keepInitial = bestStart.InitialObjective <= solverObjective;
            var solverCalculated = fit.Observations.Keys.ToDictionary(
                tracer => tracer,
                tracer => (double)ReadNumericCell(workbook, fitMap.Sheet, fitMap.CalculatedCells[tracer]),
                StringComparer.OrdinalIgnoreCase);
            attempts[bestIndex] = bestStart with
            {
                SolverStatus = solverStatus,
                SolverEstimatedAge = solverAge,
                SolverEstimatedModelParameter = solverModelParameter,
                SolverObjective = solverObjective,
                SolverCalculatedConcentrations = solverCalculated,
                EstimatedAge = keepInitial ? bestStart.InitialAge : solverAge,
                EstimatedModelParameter = keepInitial ? bestStart.InitialModelParameter : solverModelParameter,
                Objective = keepInitial ? bestStart.InitialObjective : solverObjective,
                CalculatedConcentrations = keepInitial
                    ? bestStart.InitialCalculatedConcentrations : solverCalculated
            };
            var best = attempts.MinBy(item => item.Objective)!;
            return new FitResult
            {
                Model = fit.Model,
                Observations = fit.Observations,
                EstimatedAge = best.EstimatedAge,
                EstimatedModelParameter = best.EstimatedModelParameter,
                Objective = best.Objective,
                Attempts = attempts,
                ObjectiveFormula = ReadCellFormula(workbook, fitMap.Sheet, fitMap.ResultObjectiveCell),
                TracerSelectionLabel = ReadCellText(workbook, fitMap.Sheet, fitMap.TracerSelectionLabelCell)
            };
        }
        finally { ReleaseCom(sheet); }
    }

    private static int RunSolver(dynamic excel, dynamic sheet, FitMap map, bool includeModelParameter)
    {
        dynamic objectiveCell = sheet.Range[map.ResultObjectiveCell];
        dynamic ageCell = sheet.Range[map.AgeCell];
        // Do not release these two range proxies here: Solver can return an RCW
        // shared with the active sheet, which would invalidate the next start.
        // The owned Excel process and final GC release them after the case.
        var objective = (string)objectiveCell.Address[true, true, 1, true];
        var ageAddress = (string)ageCell.Address[true, true, 1, true];
        var changing = ageAddress;
        if (includeModelParameter)
        {
            dynamic parameterCell = sheet.Range[map.ModelParameterCell];
            changing += "," + (string)parameterCell.Address[true, true, 1, true];
        }
        SolverTrace("SolverReset: start");
        excel.Run("SOLVER.XLAM!SolverReset");
        SolverTrace("SolverReset: done");
        // Bound pathological noisy fits. Solver otherwise may keep the hidden
        // Excel instance alive indefinitely on a shallow objective valley.
        excel.Run("SOLVER.XLAM!SolverOptions", 30, 1000);
        SolverTrace("SolverOptions: done (MaxTime=30, Iterations=1000)");
        excel.Run("SOLVER.XLAM!SolverOk", objective, 2, 0, changing, 1, "GRG Nonlinear");
        SolverTrace($"SolverOk: done; objective={objective}; changing={changing}");
        excel.Run("SOLVER.XLAM!SolverAdd", ageAddress, 3, map.AgeLowerCell);
        excel.Run("SOLVER.XLAM!SolverAdd", ageAddress, 1, map.AgeUpperCell);
        if (includeModelParameter)
        {
            dynamic parameterCell = sheet.Range[map.ModelParameterCell];
            var parameter = (string)parameterCell.Address[true, true, 1, true];
            excel.Run("SOLVER.XLAM!SolverAdd", parameter, 3, map.ModelParameterLowerCell);
            excel.Run("SOLVER.XLAM!SolverAdd", parameter, 1, map.ModelParameterUpperCell);
        }
        SolverTrace("SolverSolve: start");
        var status = Convert.ToInt32(excel.Run("SOLVER.XLAM!SolverSolve", true), CultureInfo.InvariantCulture);
        SolverTrace($"SolverSolve: done; status={status}");
        if (status is < 0 or > 4)
            throw new InvalidOperationException($"Solver n'a pas convergé (code {status}).");
        return status;
    }

    private static void SolverTrace(string message)
    {
        Console.WriteLine($"{DateTimeOffset.Now:O} [solver] {message}");
        Console.Out.Flush();
        DiagnosticTrace($"solver: {message}");
    }

    private static void DiagnosticTrace(string message) => File.AppendAllText(
        DiagnosticTracePath, $"{DateTimeOffset.Now:O} {message}{Environment.NewLine}");

    private static void ImportInputHistory(dynamic excel, dynamic workbook, WorkbookMap map, InputHistoryDefinition definition)
    {
        dynamic sheet = workbook.Worksheets[map.InputSheet];
        var workbookDates = ReadNumericRange(workbook, map.InputSheet, map.InputDateRange);
        var eventsWereEnabled = (bool)excel.EnableEvents;
        excel.EnableEvents = false;
        try
        {
            foreach (var tracer in definition.TargetTracers)
            {
                var source = ReadInputCsv(Path.GetFullPath(definition.Path), SourceColumn(definition, tracer));
                var column = map.InputValueColumns[tracer];
                dynamic header = sheet.Range[$"{column}2"];
                try
                {
                    var actual = Convert.ToString(header.Value2, CultureInfo.InvariantCulture) ?? "";
                    if (!string.Equals(actual, tracer, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException($"Colonne {column}: traceur attendu '{tracer}', trouvé '{actual}'.");
                }
                finally { ReleaseCom(header); }

                var values = new object[workbookDates.Count, 1];
                for (var index = 0; index < workbookDates.Count; index++)
                    values[index, 0] = Interpolate(source, workbookDates[index], definition.Before);
                var startRow = ParseFirstRow(map.InputDateRange);
                var endRow = startRow + workbookDates.Count - 1;
                dynamic target = sheet.Range[$"{column}{startRow}:{column}{endRow}"];
                try { target.Value2 = values; }
                finally { ReleaseCom(target); }

                WriteCell(sheet, $"{column}{map.InputUnsaturatedTimeRow}", 0.0);
                WriteCell(sheet, $"{column}{map.InputHalfLifeRow}", 0.0);
                WriteCell(sheet, $"{column}{map.InputDecayRateRow}", 0.0);
                WriteCell(sheet, $"{column}{map.InputScalingFactorRow}", 1.0);
            }
        }
        finally { excel.EnableEvents = eventsWereEnabled; }
        ReleaseCom(sheet);
    }

    private static void WriteCell(dynamic sheet, string address, double value)
    {
        dynamic cell = sheet.Range[address];
        try { cell.Value2 = value; }
        finally { ReleaseCom(cell); }
    }

    private static void VerifyModelParameter(dynamic workbook, WorkbookMap map, double expected)
    {
        var model1 = ReadNumericCell(workbook, map.GraphSheet, map.GraphModel1ParameterCell);
        var model2 = ReadNumericCell(workbook, map.GraphSheet, map.GraphModel2ParameterCell);
        if (Math.Abs(model1 - expected) > 1e-12 ||
            Math.Abs(model2 - expected) > 1e-12)
        {
            throw new InvalidDataException(
                $"Paramètre de modèle non conservé dans Excel: attendu={expected:R}, " +
                $"modèle1={model1:R}, modèle2={model2:R}.");
        }
    }

    private static double ReadNumericCell(dynamic workbook, string sheetName, string address)
    {
        dynamic sheet = workbook.Worksheets[sheetName];
        dynamic cell = sheet.Range[address];
        try { return Convert.ToDouble(cell.Value2, CultureInfo.InvariantCulture); }
        finally
        {
            ReleaseCom(cell);
            ReleaseCom(sheet);
        }
    }

    private static string ReadCellText(dynamic workbook, string sheetName, string address)
    {
        dynamic sheet = workbook.Worksheets[sheetName];
        dynamic cell = sheet.Range[address];
        try { return Convert.ToString(cell.Value2, CultureInfo.InvariantCulture) ?? ""; }
        finally { ReleaseCom(cell); ReleaseCom(sheet); }
    }

    private static string ReadCellFormula(dynamic workbook, string sheetName, string address)
    {
        dynamic sheet = workbook.Worksheets[sheetName];
        dynamic cell = sheet.Range[address];
        try { return Convert.ToString(cell.Formula, CultureInfo.InvariantCulture) ?? ""; }
        finally { ReleaseCom(cell); ReleaseCom(sheet); }
    }

    private static void VerifyInputHistory(dynamic workbook, WorkbookMap map, InputHistoryDefinition definition)
    {
        var dates = ReadNumericRange(workbook, map.InputSheet, map.InputDateRange);
        var startRow = ParseFirstRow(map.InputDateRange);
        foreach (var tracer in definition.TargetTracers)
        {
            var source = ReadInputCsv(Path.GetFullPath(definition.Path), SourceColumn(definition, tracer));
            var column = map.InputValueColumns[tracer];
            var actual = ReadNumericRange(workbook, map.InputSheet,
                $"{column}{startRow}:{column}{startRow + dates.Count - 1}");
            for (var index = 0; index < dates.Count; index++)
            {
                var expected = Interpolate(source, dates[index], definition.Before);
                if (Math.Abs(actual[index] - expected) > 1e-10)
                    throw new InvalidDataException(
                        $"Chronique '{tracer}' écrasée après import à la ligne {startRow + index}: " +
                        $"attendu={expected:R}, obtenu={actual[index]:R}.");
            }
        }
    }

    private static string SourceColumn(InputHistoryDefinition definition, string tracer) =>
        definition.SourceColumns is not null && definition.SourceColumns.TryGetValue(tracer, out var column)
            ? column : "concentration";

    private static List<(double Date, double Concentration)> ReadInputCsv(
        string path, string valueColumn = "concentration")
    {
        var lines = File.ReadAllLines(path);
        if (lines.Length < 2) throw new InvalidDataException($"CSV vide : {path}");
        var headers = lines[0].Split(',').Select(value => value.Trim()).ToArray();
        var dateIndex = Array.FindIndex(headers,
            value => string.Equals(value, "date", StringComparison.OrdinalIgnoreCase));
        var valueIndex = Array.FindIndex(headers,
            value => string.Equals(value, valueColumn, StringComparison.OrdinalIgnoreCase));
        if (dateIndex < 0 || valueIndex < 0)
            throw new InvalidDataException($"Colonnes date,{valueColumn} attendues : {path}");
        var result = new List<(double Date, double Concentration)>();
        foreach (var line in lines.Skip(1))
        {
            var fields = line.Split(',');
            if (fields.Length != headers.Length
                || !double.TryParse(fields[dateIndex], NumberStyles.Float, CultureInfo.InvariantCulture, out var date)
                || !double.TryParse(fields[valueIndex], NumberStyles.Float, CultureInfo.InvariantCulture, out var concentration))
                throw new InvalidDataException($"Ligne CSV invalide : {line}");
            result.Add((date, concentration));
        }
        if (result.Count < 2 || result.Zip(result.Skip(1)).Any(pair => pair.First.Date >= pair.Second.Date))
            throw new InvalidDataException("Les dates de la chronique doivent être strictement croissantes.");
        return result;
    }

    private static double Interpolate(IReadOnlyList<(double Date, double Concentration)> source, double date, double before)
    {
        if (date < source[0].Date) return before;
        if (date >= source[^1].Date) return source[^1].Concentration;
        var lower = 0;
        var upper = source.Count - 1;
        while (upper - lower > 1)
        {
            var middle = (lower + upper) / 2;
            if (source[middle].Date <= date) lower = middle; else upper = middle;
        }
        var fraction = (date - source[lower].Date) / (source[upper].Date - source[lower].Date);
        return source[lower].Concentration + fraction * (source[upper].Concentration - source[lower].Concentration);
    }

    private static int ParseFirstRow(string range)
    {
        var first = range.Split(':', 2)[0];
        var digits = new string(first.Where(char.IsDigit).ToArray());
        return int.Parse(digits, CultureInfo.InvariantCulture);
    }

    private static void SelectListValue(dynamic control, string expected)
    {
        var found = -1;
        for (var index = 0; index < (int)control.ListCount; index++)
        {
            if (string.Equals(Convert.ToString(control.List[index], CultureInfo.InvariantCulture), expected,
                    StringComparison.OrdinalIgnoreCase)) found = index;
        }
        if (found < 0) throw MissingValue(expected, control);
        for (var index = 0; index < (int)control.ListCount; index++) control.Selected[index] = index == found;
    }

    private static void SelectListValues(dynamic control, IEnumerable<string> expectedValues)
    {
        var expected = new HashSet<string>(expectedValues, StringComparer.OrdinalIgnoreCase);
        var found = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < (int)control.ListCount; index++)
        {
            var value = Convert.ToString(control.List[index], CultureInfo.InvariantCulture) ?? "";
            var selected = expected.Contains(value);
            control.Selected[index] = selected;
            if (selected) found.Add(value);
        }
        var missing = expected.Except(found, StringComparer.OrdinalIgnoreCase).ToArray();
        if (missing.Length > 0)
            throw new InvalidDataException($"Traceurs Excel introuvables : {string.Join(", ", missing)}");
    }

    private static void SelectComboValue(dynamic control, string expected)
    {
        for (var index = 0; index < (int)control.ListCount; index++)
        {
            if (!string.Equals(Convert.ToString(control.List[index], CultureInfo.InvariantCulture), expected,
                    StringComparison.OrdinalIgnoreCase)) continue;
            control.ListIndex = index;
            return;
        }
        throw MissingValue(expected, control);
    }

    private static InvalidDataException MissingValue(string expected, dynamic control)
    {
        var available = new List<string>();
        for (var index = 0; index < (int)control.ListCount; index++)
            available.Add(Convert.ToString(control.List[index], CultureInfo.InvariantCulture) ?? "");
        return new InvalidDataException($"Valeur Excel introuvable : '{expected}'. Valeurs : {string.Join(", ", available)}");
    }

    private static void EnsureAddInInstalled(dynamic excel, string addInName, string? fallbackXllPath)
    {
        for (var index = 1; index <= (int)excel.AddIns.Count; index++)
        {
            dynamic addIn = excel.AddIns[index];
            try
            {
                if (!string.Equals((string)addIn.Name, addInName, StringComparison.OrdinalIgnoreCase)) continue;
                if ((bool)addIn.Installed) return;
                try
                {
                    addIn.Installed = true;
                }
                catch (COMException)
                {
                    // Some Microsoft 365 installations reject switching Installed
                    // through COM while allowing the XLAM to be opened directly.
                    // This loads the same macros into this instance.
                    var fullName = Convert.ToString(addIn.FullName, CultureInfo.InvariantCulture);
                    if (string.IsNullOrWhiteSpace(fullName) || !File.Exists(fullName)) throw;
                    excel.Workbooks.Open(fullName, 0, true);
                }
                return;
            }
            finally { ReleaseCom(addIn); }
        }
        if (fallbackXllPath is not null && (bool)excel.RegisterXLL(fallbackXllPath)) return;
        throw new InvalidOperationException($"Complément Excel introuvable ou non chargeable : {addInName}");
    }

    private static void CalculateAndWait(dynamic excel, TimeSpan timeout)
    {
        excel.CalculateFullRebuild();
        var deadline = DateTime.UtcNow + timeout;
        while ((int)excel.CalculationState != XlCalculationStateDone)
        {
            if (DateTime.UtcNow >= deadline)
                throw new TimeoutException($"Recalcul Excel non terminé après {timeout.TotalSeconds} secondes.");
            Thread.Sleep(250);
        }
    }

    private static List<double> ReadNumericRange(dynamic workbook, string sheetName, string address)
    {
        dynamic range = workbook.Worksheets[sheetName].Range[address];
        try
        {
            var values = (object[,])range.Value2;
            var result = new List<double>(values.Length);
            foreach (var value in values)
                result.Add(Convert.ToDouble(value, CultureInfo.InvariantCulture));
            return result;
        }
        finally { ReleaseCom(range); }
    }

    private static List<double> ReadModelSeries(dynamic workbook, WorkbookMap map, string block,
        string xAxis, string yAxis)
    {
        dynamic sheet = workbook.Worksheets[map.OutputSheet];
        try
        {
            var columns = block.Split(':', 2);
            var xColumn = FindHeaderColumn(sheet, columns[0], columns[1], map.OutputRanges.ModelHeaderRow, xAxis);
            var yColumn = FindHeaderColumn(sheet, columns[0], columns[1], map.OutputRanges.ModelHeaderRow, yAxis);
            var xValues = ReadNumericRange(workbook, map.OutputSheet,
                $"{xColumn}{map.OutputRanges.ModelFirstDataRow}:{xColumn}{map.OutputRanges.ModelLastDataRow}");
            var yValues = ReadNumericRange(workbook, map.OutputSheet,
                $"{yColumn}{map.OutputRanges.ModelFirstDataRow}:{yColumn}{map.OutputRanges.ModelLastDataRow}");
            if (xValues.Count != yValues.Count) throw new InvalidDataException("Longueurs X/Y incohérentes.");
            var result = new List<double>(2 * xValues.Count);
            for (var index = 0; index < xValues.Count; index++)
            {
                result.Add(xValues[index]);
                result.Add(yValues[index]);
            }
            return result;
        }
        finally { ReleaseCom(sheet); }
    }

    private static T RetryTransientCom<T>(Func<T> operation, string description,
        int maxAttempts = 8, int initialDelayMilliseconds = 250)
    {
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                return operation();
            }
            catch (COMException exception) when (
                (exception.HResult == RpcECallRejected ||
                 exception.HResult == RpcEServerCallRetryLater) &&
                attempt < maxAttempts)
            {
                var delay = initialDelayMilliseconds * attempt;
                DiagnosticTrace(
                    $"{description}: appel COM temporairement rejeté " +
                    $"(0x{exception.HResult:X8}), tentative {attempt}/{maxAttempts}; " +
                    $"nouvel essai dans {delay} ms");
                Thread.Sleep(delay);
            }
        }
    }

    private static string FindHeaderColumn(dynamic sheet, string firstColumn, string lastColumn,
        int headerRow, string expected)
    {
        dynamic range = sheet.Range[$"{firstColumn}{headerRow}:{lastColumn}{headerRow}"];
        try
        {
            for (var index = 1; index <= (int)range.Columns.Count; index++)
            {
                dynamic cell = range.Cells[1, index];
                try
                {
                    var value = Convert.ToString(cell.Value2, CultureInfo.InvariantCulture) ?? "";
                    if (string.Equals(value, expected, StringComparison.OrdinalIgnoreCase))
                    {
                        string address = Convert.ToString(
                            cell.Address[false, false], CultureInfo.InvariantCulture)!;
                        return new string(address.TakeWhile(character => char.IsLetter(character)).ToArray());
                    }
                }
                finally { ReleaseCom(cell); }
            }
        }
        finally { ReleaseCom(range); }
        throw new InvalidDataException($"Axe '{expected}' introuvable dans le bloc {firstColumn}:{lastColumn}.");
    }

    private static string HashNumbers(IEnumerable<double> values)
    {
        var canonical = string.Join('|', values.Select(value => value.ToString("R", CultureInfo.InvariantCulture)));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(canonical)));
    }

    private static bool MatchesOptionalHash(string actual, string? expected) =>
        string.IsNullOrWhiteSpace(expected) || EqualsHash(actual, expected);

    private static void ValidateFileHash(string path, string expectedHash, string label)
    {
        if (!File.Exists(path)) throw new FileNotFoundException($"{label} introuvable.", path);
        var actualHash = HashFile(path);
        if (!EqualsHash(actualHash, expectedHash))
            throw new InvalidDataException($"Hash SHA-256 inattendu pour {label}. Attendu={expectedHash}, obtenu={actualHash}");
    }

    private static string HashFile(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path)));
    private static bool EqualsHash(string left, string right) =>
        string.Equals(left, right, StringComparison.OrdinalIgnoreCase);

    private static int ProcessIdFromExcelWindow(nint hwnd)
    { _ = GetWindowThreadProcessId(hwnd, out var processId); return checked((int)processId); }

    private static void WaitForOwnedExcelExit(int processId, TimeSpan timeout)
    {
        try
        {
            using var process = Process.GetProcessById(processId);
            if (process.WaitForExit((int)timeout.TotalMilliseconds)) return;
            Console.Error.WriteLine($"Excel n'a pas quitté; nettoyage de l'instance possédée (PID {processId}).");
            process.Kill(true);
            if (!process.WaitForExit(5_000))
                Console.Error.WriteLine(
                    $"Avertissement : confirmation de fin d'Excel non reçue pour le PID {processId}; arrêt demandé.");
        }
        catch (ArgumentException) { }
    }

    private static void ReleaseCom(object? value)
    {
        if (value is not null && Marshal.IsComObject(value)) Marshal.FinalReleaseComObject(value);
    }
}
