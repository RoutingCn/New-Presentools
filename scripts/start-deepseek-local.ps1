param(
    [int]$Port = 4173
)

$secureKey = Read-Host "Enter a new DeepSeek API key" -AsSecureString
$apiKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "DEEPSEEK_API_KEY is required. Local simulation is disabled."
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already in use. Stop the existing server first."
}

$env:DEEPSEEK_API_KEY = $apiKey
$env:DEEPSEEK_MODEL = "deepseek-v4-flash"
$env:REQUIRE_DEEPSEEK = "1"

Write-Host "Starting real DeepSeek + local aesthetic HTML server on http://127.0.0.1:$Port ..."
Write-Host "Content provider fallback is disabled for this process. HTML output uses the local aesthetic Markdown engine."

& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
    -m app.server --port $Port
