# Auto-sync: commit and push all changes in the Lottery repo
Set-Location "C:\Users\DELL\OneDrive\Desktop\Lottery"

# 0) 先抓最新成绩，再自动补「最新一期缺的特别奖」（补齐了下一期主打才会更新）
python auto_fetch_results.py
python auto_fetch_results.py --sp-only

git add -A
$status = git status --porcelain
if ($status) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "auto-sync: $ts"
}
# 先拉取云端更新（rebase 保持历史干净），再推送，避免云端有新提交时 push 被拒
git pull --rebase origin main
git push origin main
