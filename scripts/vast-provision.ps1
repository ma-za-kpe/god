# Provision a Vast.ai GPU instance for the GOD full stack.
# No Python / pip required — calls the Vast.ai REST API directly.
#
# Usage (PowerShell):
#   $env:VAST_API_KEY = "your_key_here"
#   .\scripts\vast-provision.ps1
#
# Overrides (optional):
#   $env:VAST_GPU      = "RTX_4090"   (default)
#   $env:VAST_MIN_RAM  = "32"         GB
#   $env:VAST_MIN_DISK = "120"        GB
#   $env:VAST_MAX_DHR  = "0.55"       USD/hr ceiling

param(
    [string]$ApiKey   = $env:VAST_API_KEY,
    [string]$GpuName  = ($env:VAST_GPU      ?? "RTX_4090"),
    [int]   $MinRam   = ([int]($env:VAST_MIN_RAM  ?? "32")),
    [int]   $MinDisk  = ([int]($env:VAST_MIN_DISK ?? "120")),
    [double]$MaxPrice = ([double]($env:VAST_MAX_DHR ?? "0.55")),
    [int]   $DiskGb   = 120
)

if (-not $ApiKey) { throw "Set `$env:VAST_API_KEY before running." }

$Headers = @{ Authorization = "Bearer $ApiKey" }
$Base    = "https://console.vast.ai/api/v0"

function Vast-Get($Path) {
    Invoke-RestMethod -Uri "$Base$Path" -Headers $Headers -Method Get
}
function Vast-Put($Path, $Body) {
    Invoke-RestMethod -Uri "$Base$Path" -Headers $Headers -Method Put `
        -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
}

# ── Search for the cheapest matching offer ────────────────────────────────────
Write-Host "Searching for $GpuName  RAM>=${MinRam}GB  disk>=${MinDisk}GB  price<`$$MaxPrice/hr..."

$Query = @{
    verified       = @{ eq = $true }
    external       = @{ eq = $false }
    rentable       = @{ eq = $true }
    gpu_name       = @{ eq = $GpuName }
    num_gpus       = @{ eq = 1 }
    cpu_ram        = @{ gte = $MinRam }
    disk_space     = @{ gte = $MinDisk }
    dph_total      = @{ lt  = $MaxPrice }
    inet_up        = @{ gte = 100 }
    cuda_max_good  = @{ gte = 12.0 }
} | ConvertTo-Json -Compress

$SearchResult = Invoke-RestMethod `
    -Uri "$Base/bundles/?q=$([uri]::EscapeDataString($Query))&order_by=dph_total&type=on-demand" `
    -Headers $Headers -Method Get

$Offers = $SearchResult.offers | Sort-Object dph_total

if (-not $Offers -or $Offers.Count -eq 0) {
    Write-Warning "No $GpuName offers found. Trying RTX_4080..."
    $Query2 = $Query -replace '"RTX_4090"', '"RTX_4080"'
    $SearchResult = Invoke-RestMethod `
        -Uri "$Base/bundles/?q=$([uri]::EscapeDataString($Query2))&order_by=dph_total&type=on-demand" `
        -Headers $Headers -Method Get
    $Offers = $SearchResult.offers | Sort-Object dph_total
}

if (-not $Offers -or $Offers.Count -eq 0) {
    Write-Error "No suitable GPU offers found. Check https://cloud.vast.ai manually."
    exit 1
}

$Best = $Offers[0]
Write-Host ("Best offer: id={0}  GPU={1}  VRAM={2}GB  RAM={3}GB  price=`${4:F3}/hr" -f `
    $Best.id, $Best.gpu_name, [int]($Best.gpu_totalram/1024), [int]$Best.cpu_ram, $Best.dph_total)

# ── Launch the instance ───────────────────────────────────────────────────────
Write-Host "Launching instance (disk=${DiskGb}GB, Ubuntu 22.04 + CUDA 12.4)..."

$CreateBody = @{
    client_id    = "me"
    image        = "nvidia/cuda:12.4.1-runtime-ubuntu22.04"
    disk          = $DiskGb
    onstart      = ""
    runtype      = "ssh"
    use_jupyter_lab = $false
    env          = "-e CUDA_VISIBLE_DEVICES=0"
    label        = "god-stack"
}

$Created = Vast-Put "/asks/$($Best.id)/" $CreateBody

if (-not $Created.new_contract) {
    Write-Error "Failed to create instance: $($Created | ConvertTo-Json)"
    exit 1
}

$InstanceId = $Created.new_contract
Write-Host "Instance $InstanceId created. Polling for SSH readiness..."

# ── Poll until running ────────────────────────────────────────────────────────
for ($i = 1; $i -le 40; $i++) {
    Start-Sleep -Seconds 15
    $Info = (Vast-Get "/instances/").instances | Where-Object { $_.id -eq $InstanceId }
    $Status = $Info.actual_status
    Write-Host ("  [{0}/40] status={1}" -f $i, ($Status ?? "unknown"))

    if ($Status -eq "running") {
        $SshHost = $Info.ssh_host
        $SshPort = $Info.ssh_port

        Write-Host ""
        Write-Host "✓ Instance $InstanceId is running" -ForegroundColor Green
        Write-Host ""
        Write-Host "SSH command:" -ForegroundColor Cyan
        Write-Host "  ssh -p $SshPort root@$SshHost -o StrictHostKeyChecking=no"
        Write-Host ""
        Write-Host "Deploy (copy + run setup script):" -ForegroundColor Cyan
        Write-Host "  scp -P $SshPort scripts/vast-setup.sh root@${SshHost}:/root/"
        Write-Host "  ssh -p $SshPort root@$SshHost 'bash /root/vast-setup.sh'"
        Write-Host ""
        Write-Host "Stop instance when done:" -ForegroundColor Yellow
        Write-Host "  vastai destroy instance $InstanceId"
        Write-Host "  # or via the console: https://cloud.vast.ai/instances/"
        exit 0
    }
}

Write-Error "Instance did not reach 'running' state after 10 minutes."
exit 1
