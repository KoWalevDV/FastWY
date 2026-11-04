param([string]$Compiler = 'g++')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    New-Item -Force -ItemType Directory build | Out-Null
    $version = & $Compiler --version
    if ($LASTEXITCODE -ne 0) { throw 'Cannot query the C++ compiler' }
    $version[0]
    $program = 'build/fastwy-check.exe'
    & $Compiler -std=c++14 -O2 src/main.cpp src/fastwy.cpp -o $program
    if ($LASTEXITCODE -ne 0) { throw 'C++14 compilation failed' }
    $actual = & ./$program data/sample_item.csv data/sample_expression_over1.csv --exact
    $expected = Get-Content tests/toy_expected.tsv
    if ($LASTEXITCODE -ne 0 -or ($actual -join [char]10) -cne ($expected -join [char]10)) {
        throw 'Toy output differs from the reference'
    }
    "Computer: $env:COMPUTERNAME"
    "OS: $([Environment]::OSVersion.VersionString)"
    'PASS: C++14 build and exact toy fixture'
} finally {
    Pop-Location
}
