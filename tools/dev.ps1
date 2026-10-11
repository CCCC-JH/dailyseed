<#
.SYNOPSIS
  本地开发：一条命令起后端（+ 可选前端），起之前先把"配错了会白折腾"的地方挡掉。

.DESCRIPTION
  为什么需要这个脚本：本地起不来最常见的三个原因都不是代码问题——
    ① 数据库没起 / 连不上        ② 抽卡配额是 0 却没承认开发模式（StartupGuard 会拒绝启动）
    ③ 8080 已经被上一次没杀干净的进程占着
  手工排查这三样每次都要好几分钟。这个脚本在起服务之前先把它们验掉，
  起完再对着 /api/health 确认一次"真的能用"，而不是"进程还在"。

.EXAMPLE
  pwsh tools/dev.ps1
  pwsh tools/dev.ps1 -NoFrontend          # 只起后端
  pwsh tools/dev.ps1 -SkipChecks          # 跳过数据库探测，直接起
#>
[CmdletBinding()]
param(
    [switch]$NoFrontend,
    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

function Write-Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "  [ok]   $text" -ForegroundColor Green }
function Write-Warn2($text){ Write-Host "  [warn] $text" -ForegroundColor Yellow }
function Write-Bad($text)  { Write-Host "  [FAIL] $text" -ForegroundColor Red }

# ---------- 1. .env 存在吗 ----------
Write-Step '检查 backend/.env'
$envFile = Join-Path $backend '.env'
if (-not (Test-Path $envFile)) {
    Write-Bad 'backend/.env 不存在'
    Write-Host '   cp backend/.env.example backend/.env  然后改 DB_PASSWORD'
    Write-Host '   本地开发记得加一行：DAILYSEED_DEV_MODE=true'
    exit 1
}
$envText = Get-Content $envFile -Raw

# 抽卡配额和"开发模式"是一对：0 又不承认开发模式时应用会拒绝启动，所以提前说清楚
$drawMax = if ($envText -match '(?m)^\s*DAILYSEED_DRAW_MAX_PER_DAY\s*=\s*(\S+)') { $Matches[1] } else { '0(默认)' }
$devMode = $envText -match '(?m)^\s*DAILYSEED_DEV_MODE\s*=\s*true'
Write-Ok ".env 存在（抽卡配额=$drawMax，开发模式=$(if ($devMode) { '已承认' } else { '未承认' }）)"
if ($drawMax -eq '0' -and -not $devMode) {
    Write-Bad '配额是 0（无限重抽）但没承认开发模式 —— 应用会拒绝启动'
    Write-Host '   在 backend/.env 里加：DAILYSEED_DEV_MODE=true'
    exit 1
}

# ---------- 2. 数据库连得上吗 ----------
if (-not $SkipChecks) {
    Write-Step '检查 MySQL'
    $conn = $envText -match '(?m)^\s*DB_URL\s*=\s*jdbc:mysql://([^:/]+):(\d+)/(\w+)'
    $host_ = if ($conn) { $Matches[1] } else { 'localhost' }
    $port = if ($conn) { $Matches[2] } else { '3306' }
    $reachable = Test-NetConnection -ComputerName $host_ -Port ([int]$port) -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($reachable) {
        Write-Ok "MySQL 在 $host_`:$port 可达"
    } else {
        Write-Bad "连不上 MySQL（$host_`:$port）"
        Write-Host '   要么本机启动 MySQL，要么用 Docker 只起库：'
        Write-Host '     docker compose up -d mysql'
        exit 1
    }
}

# ---------- 3. 端口被占了吗（占着的很可能是上一次没杀干净的自己） ----------
Write-Step '检查端口'
foreach ($p in @(8080, 5173)) {
    $listening = netstat -ano | Select-String ":$p\s.*LISTENING"
    if ($listening) {
        Write-Warn2 "端口 $p 已被占用（很可能是上一次没停干净的服务）"
        $listening | ForEach-Object { Write-Host "         $($_.Line.Trim())" }
        if ($p -eq 8080) {
            Write-Bad '8080 被占用：先停掉它，否则新起的后端会绑不上端口却看起来"在跑"'
            Write-Host '   停：Get-Process java -ErrorAction SilentlyContinue | Stop-Process -Force'
            exit 1
        }
    } else {
        Write-Ok "端口 $p 空闲"
    }
}

# ---------- 4. 起后端 ----------
Write-Step '启动后端（8080）'
Write-Host '  mvn spring-boot:run  —— 新窗口里跑，关掉那个窗口就停'
Start-Process -FilePath 'pwsh' -WorkingDirectory $backend -ArgumentList @(
    '-NoExit', '-Command',
    'mvn "-Dmaven.repo.local=.m2repo" spring-boot:run'
)

# ---------- 5. 起前端 ----------
if (-not $NoFrontend) {
    if (Test-Path (Join-Path $frontend 'node_modules')) {
        Write-Step '启动前端（5173）'
        Start-Process -FilePath 'pwsh' -WorkingDirectory $frontend -ArgumentList @('-NoExit', '-Command', 'npm run dev')
    } else {
        Write-Warn2 'frontend/node_modules 不存在，跳过前端。先跑：cd frontend; npm install --ignore-scripts'
    }
}

# ---------- 6. 等它真的能用 ----------
Write-Step '等后端就绪（最多 90 秒）'
$deadline = (Get-Date).AddSeconds(90)
$ok = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest 'http://localhost:8080/api/health' -UseBasicParsing -TimeoutSec 4
        $body = $r.Content | ConvertFrom-Json
        Write-Ok "HTTP $($r.StatusCode) · ok=$($body.ok) · 迁移=$(( $body.checks | Where-Object name -eq 'flyway').detail)"
        $body.warnings | ForEach-Object { Write-Warn2 $_ }
        $ok = $true
        break
    } catch {
        # 503 也是"起来了，只是有探测项没过"——比超时更有信息量
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 503) {
            Write-Bad '服务起来了，但健康检查没过（503）'
            $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream(), [Text.Encoding]::UTF8)
            ($reader.ReadToEnd() | ConvertFrom-Json).checks |
                Where-Object { -not $_.ok } | ForEach-Object { Write-Host "         $($_.name) → $($_.detail)" }
            $ok = $true
            break
        }
    }
}
if (-not $ok) {
    Write-Bad '90 秒内没就绪，去看后端那个窗口的输出'
    exit 1
}

Write-Host ''
Write-Ok '前端 http://localhost:5173'
Write-Ok '后端 http://localhost:8080（健康检查 /api/health，不需要请求头）'
