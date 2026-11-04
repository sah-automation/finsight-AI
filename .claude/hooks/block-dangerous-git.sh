#!/bin/bash

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

DANGEROUS_PATTERNS=(
  "git push"
  "git reset --hard"
  "git clean -fd"
  "git clean -f"
  "git branch -D"
  "git checkout \."
  "git restore \."
  "push --force"
  "reset --hard"
  "git commit .*--no-verify"
  "--no-verify"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE -e "$pattern"; then
    if echo "$COMMAND" | grep -qE -e "--no-verify"; then
      echo "BLOCKED: '$COMMAND' uses --no-verify, which bypasses the pre-commit gate. Use \`make ratchet\` to update standards_report.md, then commit normally." >&2
    else
      echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this." >&2
    fi
    exit 2
  fi
done

exit 0
