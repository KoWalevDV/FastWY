param(
    [Parameter(Mandatory)][string]$Program,
    [Parameter(Mandatory)][string]$Experiment,
    [uint32]$Seed = 42,
    [int[]]$Counts = @(1000, 2500, 5000, 10000)
)

$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path -LiteralPath $Program).Path
$folder = (Resolve-Path -LiteralPath $Experiment).Path
$items = Join-Path $folder 'items.csv'
$labels = Join-Path $folder 'labels.csv'
$rows = foreach ($n in $Counts) {
    if ($n -lt 1 -or $n -gt 10000) {
        throw 'Permutation count must be in 1..10000'
    }
    $output = Join-Path $folder "cpp-$n.tsv"
    $timer = [Diagnostics.Stopwatch]::StartNew()
    & $exe $items $labels $n $Seed > $output
    if ($LASTEXITCODE -ne 0) {
        throw "FastWY failed for B=$n"
    }
    $timer.Stop()
    $header = Get-Content -LiteralPath $output -TotalCount 4
    [pscustomobject]@{
        permutations = $n
        seed = $Seed
        elapsed_ms = $timer.ElapsedMilliseconds
        threshold = $header[2].Split('=')[1]
        significant_patterns = $header[3].Split('=')[1]
    }
}
$rows | Export-Csv -NoTypeInformation -Encoding ascii (Join-Path $folder 'summary.csv')
