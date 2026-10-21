#!/bin/bash
input=$(cat)
# Already continuing because of this hook — don't loop (Claude Code force-stops after 8 blocks anyway)
[ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
cd "$(printf '%s' "$input" | jq -r '.cwd')" || exit 0

# Files with uncommitted changes, excluding STATE.md itself
changed=$(git status --porcelain 2>/dev/null | cut -c4- | grep -vx 'STATE.md')
[ -z "$changed" ] && exit 0

# If STATE.md is at least as new as every changed file, the handoff note is current
state_mtime=$(stat -f %m STATE.md 2>/dev/null || echo 0)
newest=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  m=$(stat -f %m "$f" 2>/dev/null || echo 0)
  [ "$m" -gt "$newest" ] && newest="$m"
done <<< "$changed"
[ "$state_mtime" -ge "$newest" ] && exit 0

printf '%s\n' '{"decision":"block","reason":"Session-continuity contract: work happened since STATE.md was last updated. Refresh STATE.md (current focus, last completed, next step, gotchas — including any open question you are about to ask the user) before finishing. Do NOT create a commit just for this; commits happen at natural chunk boundaries per CLAUDE.md."}'
