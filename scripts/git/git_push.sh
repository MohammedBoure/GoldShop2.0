#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMIT_MSG="$PROJECT_DIR/docs/dev/commit_msg"
COMMIT_LOG="$PROJECT_DIR/docs/dev/commit_msgs"

cd "$PROJECT_DIR"

# 1. Append the content of commit_msg to commit_msgs
echo -e "\n-----\n" >> "$COMMIT_LOG"
cat "$COMMIT_MSG" >> "$COMMIT_LOG"

# 2. Stage all files
git add .

# 3. Remove all __pycache__ and ProjectLens directories from staging (without deleting actual files)
find . -type d -name "__pycache__" -exec git rm -r --cached {} +
git rm -r --cached ProjectLens

# 4. Commit using the content of commit_msg as the commit message
git commit -F "$COMMIT_MSG"

# 5. Get the current branch name dynamically
current_branch=$(git symbolic-ref --short HEAD)

# 6. Push to the current branch (to avoid branch name mismatch issues)
git push origin "$current_branch"
