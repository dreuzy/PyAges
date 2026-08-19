namespace TracerLpmRunner;

public sealed record RunnerConfig
{
    public required string WorkbookPath { get; init; }
    public required string WorkbookSha256 { get; init; }
    public required string XllPath { get; init; }
    public required string XllSha256 { get; init; }
    public required string WorkbookMapPath { get; init; }
    public required string WorkRoot { get; init; }
    public required string OutputRoot { get; init; }
    public bool ExcelVisible { get; init; } = true;
    public bool ReuseExcelSession { get; init; } = false;
    public int TimeoutSeconds { get; init; } = 180;
}

public sealed record WorkbookMap
{
    public required string WorkbookSha256 { get; init; }
    public required string GraphSheet { get; init; }
    public required string GraphSheetCodeName { get; init; }
    public required string GraphObservationYearCell { get; init; }
    public required string GraphModel1ParameterCell { get; init; }
    public required string GraphModel2ParameterCell { get; init; }
    public required string OutputSheet { get; init; }
    public required string SampleSheet { get; init; }
    public required string InputSheet { get; init; }
    public required string InputDateRange { get; init; }
    public required Dictionary<string, string> InputValueColumns { get; init; }
    public required int InputUnsaturatedTimeRow { get; init; }
    public required int InputHalfLifeRow { get; init; }
    public required int InputDecayRateRow { get; init; }
    public required int InputScalingFactorRow { get; init; }
    public required ControlMap Controls { get; init; }
    public required string[] EventMacros { get; init; }
    public required OutputRangeMap OutputRanges { get; init; }
    public FitMap? Fit { get; init; }
}

public sealed record FitMap
{
    public required string Sheet { get; init; }
    public required string SheetCodeName { get; init; }
    public required string SampleControl { get; init; }
    public required string ModelControl { get; init; }
    public required string TracerControl { get; init; }
    public required string ObservationYearCell { get; init; }
    public required Dictionary<string, string> ObservationCells { get; init; }
    public required string AgeCell { get; init; }
    public required string AgeLowerCell { get; init; }
    public required string AgeUpperCell { get; init; }
    public required string ModelParameterCell { get; init; }
    public required string ModelParameterLowerCell { get; init; }
    public required string ModelParameterUpperCell { get; init; }
    public required string ResultAgeCell { get; init; }
    public required string ResultObjectiveCell { get; init; }
    public required string TracerSelectionLabelCell { get; init; }
    public required Dictionary<string, string> CalculatedCells { get; init; }
    public required Dictionary<string, string> DecayRateCells { get; init; }
}

public sealed record ControlMap
{
    public required string SamplesToGraph { get; init; }
    public required string SampleToModel { get; init; }
    public required string Model1 { get; init; }
    public required string Model2 { get; init; }
    public required string XAxis { get; init; }
    public required string YAxis { get; init; }
}

public sealed record OutputRangeMap
{
    public required string Model1 { get; init; }
    public required string Model2 { get; init; }
    public required string Model1Block { get; init; }
    public required string Model2Block { get; init; }
    public required int ModelHeaderRow { get; init; }
    public required int ModelFirstDataRow { get; init; }
    public required int ModelLastDataRow { get; init; }
    public required string Sample { get; init; }
    public required string ModelAges { get; init; }
}

public sealed record CaseDefinition
{
    public required string CaseId { get; init; }
    public required string Sample { get; init; }
    public double? ObservationYear { get; init; }
    public double? TracerlpmEffectiveObservationYear { get; init; }
    public double? ModelParameter { get; init; }
    public required string Model1 { get; init; }
    public required string Model2 { get; init; }
    public required string XAxis { get; init; }
    public required string YAxis { get; init; }
    public string? ExpectedModel1Sha256 { get; init; }
    public string? ExpectedModel2Sha256 { get; init; }
    public InputHistoryDefinition? InputHistory { get; init; }
    public FitDefinition? Fit { get; init; }
}

public sealed record FitDefinition
{
    public required string Sample { get; init; }
    public required string Model { get; init; }
    public required Dictionary<string, double> Observations { get; init; }
    public required double[] InitialAges { get; init; }
    public double[]? InitialModelParameters { get; init; }
    public required double AgeLower { get; init; }
    public required double AgeUpper { get; init; }
    public double? ModelParameterLower { get; init; }
    public double? ModelParameterUpper { get; init; }
}

public sealed record InputHistoryDefinition
{
    public required string Path { get; init; }
    public required string Sha256 { get; init; }
    public required string[] TargetTracers { get; init; }
    public Dictionary<string, string>? SourceColumns { get; init; }
    public double Before { get; init; } = 0.0;
    public string After { get; init; } = "hold_last";
}

public sealed record RunResult
{
    public required string Status { get; init; }
    public required string CaseId { get; init; }
    public required string RunId { get; init; }
    public required DateTimeOffset StartedAt { get; init; }
    public required double DurationSeconds { get; init; }
    public required string WorkbookSha256 { get; init; }
    public required string XllSha256 { get; init; }
    public required string WorkingWorkbook { get; init; }
    public string? InputHistoryPath { get; init; }
    public string? InputHistorySha256 { get; init; }
    public required string Sample { get; init; }
    public double? ObservationYear { get; init; }
    public double? TracerlpmEffectiveObservationYear { get; init; }
    public double? ModelParameter { get; init; }
    public required string Model1 { get; init; }
    public required string Model2 { get; init; }
    public required string XAxis { get; init; }
    public required string YAxis { get; init; }
    public required int Model1PointCount { get; init; }
    public required int Model2PointCount { get; init; }
    public required string Model1Sha256 { get; init; }
    public required string Model2Sha256 { get; init; }
    public string? ExpectedModel1Sha256 { get; init; }
    public string? ExpectedModel2Sha256 { get; init; }
    public required bool Model1MatchesExpected { get; init; }
    public required bool Model2MatchesExpected { get; init; }
    public required double SampleX { get; init; }
    public required double SampleY { get; init; }
    public required int ExcelProcessId { get; init; }
    public required IReadOnlyList<SeriesPoint> Model1Points { get; init; }
    public required IReadOnlyList<SeriesPoint> Model2Points { get; init; }
    public required IReadOnlyList<double> ModelAges { get; init; }
    public FitResult? Fit { get; init; }
}

public sealed record FitResult
{
    public required string Model { get; init; }
    public required Dictionary<string, double> Observations { get; init; }
    public required double EstimatedAge { get; init; }
    public required double Objective { get; init; }
    public double? EstimatedModelParameter { get; init; }
    public required IReadOnlyList<FitAttempt> Attempts { get; init; }
    public required string ObjectiveFormula { get; init; }
    public required string TracerSelectionLabel { get; init; }
}

public sealed record FitAttempt
{
    public required double InitialAge { get; init; }
    public double? InitialModelParameter { get; init; }
    public required double InitialObjective { get; init; }
    public int? SolverStatus { get; init; }
    public double? SolverEstimatedAge { get; init; }
    public double? SolverEstimatedModelParameter { get; init; }
    public double? SolverObjective { get; init; }
    public required double EstimatedAge { get; init; }
    public double? EstimatedModelParameter { get; init; }
    public required double Objective { get; init; }
    public required Dictionary<string, double> InitialCalculatedConcentrations { get; init; }
    public Dictionary<string, double>? SolverCalculatedConcentrations { get; init; }
    public required Dictionary<string, double> CalculatedConcentrations { get; init; }
}

public sealed record SeriesPoint
{
    public required int Index { get; init; }
    public required double X { get; init; }
    public required double Y { get; init; }
}
