<#
.SYNOPSIS
  Validate representative exported FHIR resources with the official HL7 FHIR validator (R4 4.0.1).
.DESCRIPTION
  1. scripts/export_fhir_samples.py writes one representative resource per implemented type
     (from the running source services) plus a searchset Bundle and an approved package Bundle
     to contracts/fhir-samples/.
  2. This script runs validator_cli.jar in a Java container against those files.
  3. scripts/summarize_fhir_report.py groups the findings.
  Structural checks in the importer are NOT a conformance claim; this is.
  -Terminology "n/a" (default) runs offline: code-system membership (MIME, LOINC, SNOMED) is then
  reported as "cannot be checked". Pass -Terminology "https://tx.fhir.org/r4" for a full terminology check.
#>
param([string]$ValidatorVersion = "6.3.4", [string]$Terminology = "n/a")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "tools"
New-Item -ItemType Directory -Force $tools | Out-Null
$jar = Join-Path $tools "validator_cli.jar"
if (-not (Test-Path $jar)) {
    Write-Host "Downloading HL7 validator $ValidatorVersion ..."
    Invoke-WebRequest "https://github.com/hapifhir/org.hl7.fhir.core/releases/download/$ValidatorVersion/validator_cli.jar" -OutFile $jar
}
$samples = Join-Path $root "contracts/fhir-samples"
Get-ChildItem $samples -Filter *.json -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -LiteralPath $_.FullName }
& (Join-Path $root ".venv/Scripts/python.exe") (Join-Path $PSScriptRoot "export_fhir_samples.py")
docker run --rm -m 1600m -v "${tools}:/tools" -v "${samples}:/samples" -v referral-fhir-cache:/root/.fhir eclipse-temurin:21-jre `
    sh -c "java -Xmx1g -jar /tools/validator_cli.jar /samples/*.json -version 4.0.1 -tx $Terminology -output /samples/validation-report.html > /samples/validator-output.txt 2>&1; tail -n 1 /samples/validator-output.txt"
& (Join-Path $root ".venv/Scripts/python.exe") (Join-Path $PSScriptRoot "summarize_fhir_report.py") (Join-Path $samples "validation-report.html")
Write-Host "Report: contracts/fhir-samples/validation-report.html"
