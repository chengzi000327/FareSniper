#!/usr/bin/env bash
set -euo pipefail

# 旧文件存在则删除
for f in backend/services/search_service.py backend/llm/client.py; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    git rm "$f"
  elif [ -f "$f" ]; then
    rm "$f"
  fi
done

# 扫描残留 import
grep -rn -E \
  "from backend\.services\.search_service|from backend\.llm\.client|import backend\.services\.search_service|import backend\.llm\.client" \
  backend/ \
  || echo "no residual legacy imports"
