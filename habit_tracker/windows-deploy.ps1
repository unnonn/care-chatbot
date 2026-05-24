<#
.SYNOPSIS
  習慣化アプリを Fly.io に自動デプロイする Windows 用ワンショットスクリプト。

.DESCRIPTION
  flyctl が無ければ自動インストール。Git が無くてもOK（ZIPで取得）。
  Fly.io ログイン → アプリ作成 → 東京リージョンに永続ボリューム作成
  → Resend APIキー登録 → ビルド & デプロイ → 完了後ブラウザでURLを開く。

.EXAMPLE
  iex (iwr https://raw.githubusercontent.com/unnonn/care-chatbot/claude/habit-tracking-app-qVdZm/habit_tracker/windows-deploy.ps1 -UseBasicParsing).Content
#>

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Note([string]$msg) { Write-Host "   $msg" -ForegroundColor Gray }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  習慣化アプリ - Fly.io 自動デプロイ" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. flyctl をインストール（必要なら） ---
Write-Step "flyctl の確認"
if (-not (Get-Command fly -ErrorAction SilentlyContinue)) {
    Write-Note "flyctl がインストールされていません。自動インストールします..."
    try {
        Invoke-WebRequest https://fly.io/install.ps1 -UseBasicParsing | Invoke-Expression
    } catch {
        Write-Host "❌ flyctl のインストールに失敗しました: $_" -ForegroundColor Red
        exit 1
    }
    $env:FLYCTL_INSTALL = "$HOME\.fly"
    $env:Path = "$env:FLYCTL_INSTALL\bin;$env:Path"
}

if (-not (Get-Command fly -ErrorAction SilentlyContinue)) {
    Write-Host "❌ flyctl をPATHに追加できませんでした。PowerShellを開き直して再実行してください。" -ForegroundColor Red
    exit 1
}
Write-Ok "flyctl: $(fly version)"

# --- 2. Fly.io ログイン ---
Write-Step "Fly.io ログイン状態の確認"
$user = $null
try { $user = (fly auth whoami 2>$null) } catch {}

if (-not $user) {
    Write-Note "ブラウザが開きます。Fly.io にログインしてください..."
    Write-Note "（アカウント未作成なら https://fly.io/app/sign-up で先に登録）"
    Read-Host "準備ができたら Enter を押してください"
    fly auth login
    $user = (fly auth whoami 2>$null)
}

if (-not $user) {
    Write-Host "❌ Fly.io ログインに失敗しました。" -ForegroundColor Red
    exit 1
}
Write-Ok "ログイン中: $user"

# --- 3. ソースコード取得（Git 不要・ZIPで） ---
Write-Step "アプリのソースコードを取得"
$workdir = Join-Path $env:USERPROFILE "habit-tracker"
$branch = "claude/habit-tracking-app-qVdZm"
$branchUrl = $branch -replace "/", "-"

if (-not (Test-Path "$workdir\fly.toml")) {
    if (Test-Path $workdir) { Remove-Item $workdir -Recurse -Force }
    $zip = Join-Path $env:TEMP "habit-tracker-source.zip"
    $extractDir = Join-Path $env:TEMP "habit-tracker-extract"
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }

    $url = "https://github.com/unnonn/care-chatbot/archive/refs/heads/$branch.zip"
    Write-Note "ダウンロード: $url"
    Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $extractDir -Force
    $srcDir = Get-ChildItem $extractDir -Directory | Select-Object -First 1
    Move-Item (Join-Path $srcDir.FullName "habit_tracker") $workdir
    Remove-Item $zip -Force
    Remove-Item $extractDir -Recurse -Force
}
Set-Location $workdir
Write-Ok "作業ディレクトリ: $workdir"

# --- 4. アプリ名 ---
Write-Step "Fly.io アプリの設定"
$flyConfig = Get-Content "fly.toml" -Raw
$currentApp = ([regex]'(?m)^app *= *"([^"]+)"').Match($flyConfig).Groups[1].Value

$appExists = $false
$null = (fly status -a $currentApp 2>&1)
if ($LASTEXITCODE -eq 0) { $appExists = $true; $appName = $currentApp }

if (-not $appExists) {
    Write-Host ""
    Write-Host "  世界で一意な英数小文字+ハイフンのアプリ名を入力してください。" -ForegroundColor Yellow
    Write-Host "  例: habit-yourname-2026" -ForegroundColor Gray
    do {
        $appName = (Read-Host "  アプリ名").Trim().ToLower()
        if ($appName -notmatch '^[a-z0-9][a-z0-9-]{2,29}$') {
            Write-Host "  ❌ 3〜30文字、英小文字・数字・ハイフンのみで再入力してください。" -ForegroundColor Red
            $appName = ""
        }
    } while (-not $appName)

    $flyConfig = $flyConfig -replace '(?m)^app *=.*', "app = `"$appName`""
    Set-Content "fly.toml" $flyConfig -NoNewline

    Write-Note "アプリ作成中: $appName"
    fly apps create $appName 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ そのアプリ名は使用済みです。スクリプトを再実行して別の名前を試してください。" -ForegroundColor Red
        exit 1
    }
}
Write-Ok "アプリ: $appName"

# --- 5. 永続ボリューム（SQLite用） ---
Write-Step "東京リージョンの永続ボリュームを確認"
$volumes = (fly volumes list -a $appName 2>&1) -join "`n"
if ($volumes -notmatch "habit_data") {
    Write-Note "1GB ボリュームを nrt (Tokyo) に作成..."
    fly volumes create habit_data --region nrt --size 1 --yes -a $appName 2>&1 | Out-Host
}
Write-Ok "ボリューム OK"

# --- 6. Resend APIキー ---
Write-Step "Resend (メール通知) の設定"
$secrets = (fly secrets list -a $appName 2>&1) -join "`n"
if ($secrets -notmatch "RESEND_API_KEY") {
    Write-Host ""
    Write-Host "  Resend ダッシュボード → API Keys からコピーした key を貼り付けてください" -ForegroundColor Yellow
    Write-Host "  形式: re_xxxxxxxxxxxxxxxx" -ForegroundColor Gray
    Write-Host "  （未登録の場合は https://resend.com/api-keys で発行）" -ForegroundColor Gray
    Write-Host "  ※ 後から設定したい場合は Enter のみでスキップ可" -ForegroundColor Gray
    $resendKey = (Read-Host "  RESEND_API_KEY").Trim()
    if ($resendKey) {
        fly secrets set "RESEND_API_KEY=$resendKey" -a $appName 2>&1 | Out-Host
        Write-Ok "Resend キーを登録"
    } else {
        Write-Note "Resend キー未登録（メール通知は無効）"
    }
} else {
    Write-Ok "Resend キーは既に登録済み"
}

# --- 7. デプロイ ---
Write-Step "ビルド & デプロイ (2〜5分かかります)"
fly deploy -a $appName 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ デプロイに失敗しました。" -ForegroundColor Red
    Write-Host "   ログ確認:  fly logs -a $appName" -ForegroundColor Yellow
    exit 1
}

# --- 8. 完了 ---
$url = "https://$appName.fly.dev"
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✓ デプロイ完了！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  アプリ URL: " -NoNewline
Write-Host $url -ForegroundColor Cyan
Write-Host ""
Write-Host "  次の手順:" -ForegroundColor Yellow
Write-Host "    1. このURLを iPhone Safari で開く"
Write-Host "    2. 共有ボタン（□↑）→「ホーム画面に追加」"
Write-Host "    3. ホーム画面のアイコンから起動"
Write-Host ""
Write-Host "  PCのブラウザでも先にチェックできるよう自動で開きます..." -ForegroundColor Gray
Start-Sleep -Seconds 2
Start-Process $url
