#!/usr/bin/env bash
set -euo pipefail

if (( $# > 1 )); then
  printf 'Usage: %s [repository-root]\n' "$0" >&2
  exit 1
fi

repository_root="${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
changes_dir="$repository_root/openspec/changes"

if [[ ! -d "$changes_dir" || ! -r "$changes_dir" || ! -x "$changes_dir" ]]; then
  printf 'Cannot inspect OpenSpec changes directory: %s (missing or unreadable).\n' "$changes_dir" >&2
  exit 1
fi

shopt -s dotglob nullglob
active_changes=()
for entry in "$changes_dir"/*; do
  if [[ -d "$entry" && "${entry##*/}" != archive ]]; then
    active_changes+=("${entry##*/}")
  fi
done

if (( ${#active_changes[@]} > 0 )); then
  printf 'OpenSpec closure failed. Active changes:\n' >&2
  while IFS= read -r -d '' change; do
    printf '  - %s\n' "$change" >&2
  done < <(printf '%s\0' "${active_changes[@]}" | LC_ALL=C sort -z)
  printf 'Complete and validate implementation, synchronize specifications, and archive each change locally before merging.\n' >&2
  exit 1
fi

printf 'OpenSpec closure passed: no active changes.\n'
