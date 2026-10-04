# Auto-sync: 抓成绩 + 提交 + 推送
# 稳定版(2026-10-04): 云端 GitHub Actions 和本机都抓成绩, 以前会同时改 auto_results.json 撞车把文件写坏。
# 现在: ① 抓之前先把云端最新拉下来当底 ② 万一还冲突, auto_results.json 一律以云端为准 ③ 永不留下半截 rebase
Set-Location "C:\Users\DELL\OneDrive\Desktop\Lottery"
$ErrorActionPreference = "Continue"

function Clear-StuckRebase {
    # OneDrive 锁文件会让 rebase 收尾失败,残留目录会挡住之后所有 git 操作
    if ((Test-Path ".git\rebase-merge") -or (Test-Path ".git\rebase-apply")) {
        git rebase --abort 2>$null | Out-Null
        Remove-Item ".git\rebase-merge" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item ".git\rebase-apply" -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Sync-FromCloud {
    Clear-StuckRebase
    git fetch origin main 2>$null | Out-Null
    # auto_results.json 本机只是「加料」,底以云端为准 → 先把它重置成云端版本,再抓
    git checkout origin/main -- auto_results.json 2>$null | Out-Null
}

Clear-StuckRebase
Sync-FromCloud

# 0) 先抓最新成绩，再自动补「最新一期缺的特别奖」（补齐了下一期主打才会更新）
python auto_fetch_results.py
python auto_fetch_results.py --sp-only

git add -A
$status = git status --porcelain
if ($status) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "auto-sync: $ts"
}

# 先拉取云端更新（rebase 保持历史干净），再推送
git pull --rebase origin main 2>&1 | Out-Null
$tries = 0
while ((Test-Path ".git\rebase-merge") -or (Test-Path ".git\rebase-apply")) {
    $tries++
    if ($tries -gt 8) { break }
    # 冲突只可能是 auto_results.json: 以云端(ours=rebase 底)为准
    $conf = git diff --name-only --diff-filter=U
    foreach ($f in $conf) {
        if ($f -eq "auto_results.json") { git checkout --ours -- $f 2>$null | Out-Null; git add $f | Out-Null }
        else { git checkout --theirs -- $f 2>$null | Out-Null; git add $f | Out-Null }
    }
    $env:GIT_EDITOR = "true"
    git rebase --continue 2>&1 | Out-Null
}
Clear-StuckRebase

# 最后保险:成绩文件必须是合法 JSON,否则不要推上去
$ok = $true
try { Get-Content "auto_results.json" -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null } catch { $ok = $false }
if (-not $ok) {
    git checkout origin/main -- auto_results.json 2>$null | Out-Null
    git add auto_results.json | Out-Null
    git commit -m "auto-sync: 恢复 auto_results.json (本机版本损坏)" 2>&1 | Out-Null
}
git push origin main
