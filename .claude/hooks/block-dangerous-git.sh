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
)

# Block `git commit --no-verify` / `git commit -n`, regardless of flag order.
# Strip quoted arguments first so a commit message that merely mentions the
# flag is not mistaken for its use.
COMMIT_ARGS=$(printf '%s' "$COMMAND" | sed -E "s/'[^']*'//g" | sed -E 's/"[^"]*"//g')
if printf '%s' "$COMMIT_ARGS" | grep -qE 'git[[:space:]]+commit' \
  && printf '%s' "$COMMIT_ARGS" | grep -qE -- '--no-verify|(^|[[:space:]])-[A-Za-z]*n[A-Za-z]*([[:space:]]|$)'; then
  echo "BLOCKED: '$COMMAND' uses --no-verify, which bypasses the pre-commit gate. Use \`make ratchet\` to update standards_report.md, then commit normally." >&2
  exit 2
fi

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE -e "$pattern"; then
    echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this." >&2
    exit 2
  fi
done

exit 0
