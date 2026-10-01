<#
.SYNOPSIS
  Validate representative exported FHIR resources with the official HL7 FHIR validator (R4 4.0.1).
.DESCRIPTION
  1. scripts/export_fhir_samples.py writes one representative resource per implemented type
     (from the running source services) to contracts/fhir-samples/.
  2. This script runs validator_cli.jar in a Java container against those files.
  Pydantic/structural checks in the importer are NOT a conformance claim; this is.
#>
param([string]$ValidatorVersion = "6.3.4")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "tools"
New-Item -ItemType Directory -Force $tools | Out-Null
$jar = Join-Path $tools "validator_cli.jar"
if (-not (Test-Path $jar)) {
    Write-Host "Downloading HL7 validator $ValidatorVersion ..."
    Invoke-WebRequest "https://github.com/hapifhir/org.hl7.fhir.core/releases/download/$ValidatorVersion/validator_cli.jar" -OutFile $jar
}
& (Join-Path $root ".venv/Scripts/python.exe") (Join-Path $PSScriptRoot "export_fhir_samples.py")
$samples = Join-Path $root "contracts/fhir-samples"
docker run --rm -v "${tools}:/tools" -v "${samples}:/samples" eclipse-temurin:21-jre `
    sh -c "java -jar /tools/validator_cli.jar /samples/*.json -version 4.0.1 -output /samples/validation-report.html 2>&1 | tail -n 60"
Write-Host "Report: contracts/fhir-samples/validation-report.html"
