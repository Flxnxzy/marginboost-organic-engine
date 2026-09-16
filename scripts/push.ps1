$ErrorActionPreference = "Stop"

$repo = "https://github.com/Flxnxzy/marginboost-organic-engine.git"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not in PATH. Install Git for Windows, then run this script again."
}

if (-not (Test-Path ".git")) {
    git init
}

git branch -M main

$remotes = git remote 2>$null
if ($remotes -contains "origin") {
    git remote set-url origin $repo
} else {
    git remote add origin $repo
}

git add .
git commit -m "Build MarginBoost organic acquisition engine"

Write-Host ""
Write-Host "Pushing the completed engine to GitHub."
Write-Host "If Git asks you to sign in, approve the browser sign-in."
git push -u origin main --force

Write-Host ""
Write-Host "DONE"
Write-Host "https://github.com/Flxnxzy/marginboost-organic-engine/actions"
