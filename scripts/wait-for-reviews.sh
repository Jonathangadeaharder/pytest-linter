#!/usr/bin/env bash
set -euo pipefail

branch=$(git branch --show-current)
repo=$(git remote get-url origin 2>/dev/null | sed -E 's|git@github.com:||;s|https://github.com/||;s|\.git$||')
pr=$(gh pr list --repo "$repo" --head "$branch" --state open --json number -q '.[0].number' 2>/dev/null || echo "")

if [ -z "$pr" ]; then
    echo "No open PR found for branch $branch"
    exit 1
fi

echo "Waiting for new reviews from all 3 bots on PR #$pr..."
start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

seen_coderabbit=false
seen_gemini=false
seen_copilot=false

while true; do
    # Fetch reviews
    reviews=$(gh api "repos/$repo/pulls/$pr/reviews" -q ".[] | select(.submitted_at > \"$start_time\") | .user.login" 2>/dev/null || echo "")
    
    if echo "$reviews" | grep -q -E "coderabbitai"; then
        seen_coderabbit=true
    fi
    if echo "$reviews" | grep -q -E "gemini"; then
        seen_gemini=true
    fi
    if echo "$reviews" | grep -q -i "copilot"; then
        seen_copilot=true
    fi
    
    if [ "$seen_coderabbit" = true ] && [ "$seen_gemini" = true ] && [ "$seen_copilot" = true ]; then
        echo -e "\nAll 3 bot reviews detected!"
        exit 0
    fi
    
    echo -n "."
    sleep 30
done
