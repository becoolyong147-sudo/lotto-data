# Auto-sync: commit and push all changes in the Lottery repo
Set-Location "C:\Users\DELL\OneDrive\Desktop\Lottery"
git add -A
$status = git status --porcelain
if ($status) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "auto-sync: $ts"
}
# 先拉取云端更新（rebase 保持历史干净），再推送，避免云端有新提交时 push 被拒
git pull --rebase origin main
git push origin main
