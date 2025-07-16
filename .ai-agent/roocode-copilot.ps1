param(
  [string]$File,
  [int]   $Cursor
)

# history and temp files
$history = "$PSScriptRoot\history.txt"
$tmp     = "$PSScriptRoot\tmp-prompt.txt"

# 1) Scaffold via Roo Code
roocode run --prompt-file $history | Out-Null

# 2) In-context Copilot fill (last 8 messages)
Get-Content -Tail 8 $history | Set-Content $tmp
github-copilot-cli complete `
  --file $File `
  --cursor $Cursor `
  --in-context 8 `
  --prompt-file $tmp | Add-Content $File

# 3) Tests & lint
npm test -- --silent 2>&1 > test.log; if ($LASTEXITCODE -ne 0) { pytest -q 2>&1 >> test.log }
flake8 . 2>$null; if ($LASTEXITCODE -ne 0) { eslint . }

# 4) On failure (once), auto-fix
if (Select-String -Pattern "FAIL" -Path test.log) {
  $failureMsg = Get-Content test.log | Select-Object -Last 15 | Out-String
  Add-Content $history "❗ Failure`n$failureMsg"
  $failureMsg | Out-File $tmp
  github-copilot-cli complete `
    --file $File `
    --cursor $Cursor `
    --prompt-file $tmp | Add-Content $File
}

# 5) Archive timestamp
"`n-- $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') --" | Add-Content $history
