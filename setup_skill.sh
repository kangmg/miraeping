#!/usr/bin/env bash
# Copy the complete skill to both agents. Never install symbolic links.
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    printf 'Usage: bash setup_skill.sh\nCopies slack-notify into ~/.claude/skills and ${CODEX_HOME:-~/.codex}/skills.\nExisting copies/links are backed up before replacement. No credentials are changed.\n'
    exit 0
fi
(( $# == 0 )) || { printf 'Unknown argument: %s\n' "$1" >&2; exit 2; }
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source_dir="$script_dir/skills/slack-notify"
[[ -f "$source_dir/SKILL.md" && -f "$source_dir/scripts/miraeping-doctor" ]] || { printf 'Missing slack-notify skill files.\n' >&2; exit 1; }

copy_skill() {
    local parent="$1" target backup='' backup_dir
    mkdir -p -- "$parent"
    parent="$(cd -- "$parent" && pwd -P)"
    target="$parent/slack-notify"
    # Only this exact skill entry is moved; its parent is never a move target.
    [[ "$target" != "$source_dir" ]] || { printf 'Refusing to overwrite the source skill.\n' >&2; return 1; }
    if [[ -e "$target" || -L "$target" ]]; then
        backup_dir="$(dirname -- "$parent")/skill-backups"
        mkdir -p -- "$backup_dir"
        backup="$backup_dir/slack-notify.$(date +%Y%m%d-%H%M%S).$$"
        [[ ! -e "$backup" && ! -L "$backup" ]] || { printf 'Backup path already exists.\n' >&2; return 1; }
        mv -- "$target" "$backup"
        printf 'Previous installation preserved: %s\n' "$backup"
    fi
    mkdir -- "$target"
    cp -rL -- "$source_dir/." "$target/"
    chmod +x "$target/scripts/miraeping-doctor"
    printf 'Installed copy: %s\n' "$target"
}

copy_skill "${HOME:?HOME is required}/.claude/skills"
copy_skill "${CODEX_HOME:-$HOME/.codex}/skills"
printf '\nInstalled for Claude and Codex. Invoke $slack-notify.\nRun the bundled doctor with bash after activating your job environment.\n'
