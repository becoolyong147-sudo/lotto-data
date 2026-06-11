# Auto-sync: commit and push all changes in the Lottery repo
Set-Location "C:\Users\DELL\OneDrive\Desktop\Lottery"
git add -A
$status = git status --porcelain
if ($status) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "auto-sync: $ts"
}
git push origin main
