param(
    [int]$Port = 4173
)

$secureKey = Read-Host "Enter a new DeepSeek API key" -AsSecureString
$apiKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "DEEPSEEK_API_KEY is required. Local simulation is disabled."
}

$secureArkKey = Read-Host "Enter a Volcengine Ark API key for HTML generation" -AsSecureString
$arkApiKey = [System.Net.NetworkCredential]::new("", $secureArkKey).Password
if ([string]::IsNullOrWhiteSpace($arkApiKey)) {
    throw "ARK_API_KEY is required. HTML generation must use Ark."
}
$arkModel = Read-Host "Enter a Volcengine Ark model or endpoint id [doubao-seed-1-6]"
if ([string]::IsNullOrWhiteSpace($arkModel)) {
    $arkModel = "doubao-seed-1-6"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already in use. Stop the existing server first."
}

$env:DEEPSEEK_API_KEY = $apiKey
$env:DEEPSEEK_MODEL = "deepseek-v4-flash"
$env:REQUIRE_DEEPSEEK = "1"
$env:ARK_API_KEY = $arkApiKey
$env:ARK_MODEL = $arkModel
$env:ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
$env:REQUIRE_ARK_HTML = "1"

Write-Host "Starting real DeepSeek + Ark server on http://127.0.0.1:$Port ..."
Write-Host "Content provider fallback and HTML template fallback are disabled for this process."

& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
    -m app.server --port $Port
