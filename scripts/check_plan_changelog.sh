#!/usr/bin/env bash
set -euo pipefail
file="docs/superpowers/plans/CHANGELOG.md"
test -f "$file" || { echo "missing $file"; exit 1; }
grep -q "^| 时间 | 作者 | 更新说明 |" "$file" || { echo "header row missing"; exit 1; }
echo "OK"
