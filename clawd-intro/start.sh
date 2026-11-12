#!/usr/bin/env bash
# start.sh — Launch Claude Code after playing the Clawd intro animation.
#   Uses ./clawd-intro next to this script, falling back to ~/.local/bin/clawd-intro.
#   Press any key to skip; CLAWD_NO_INTRO=1 ./start.sh disables the animation.
#   CLAWD_INTRO_SPEED=2 ./start.sh plays at 2x speed.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

main() {
  local play=1 a intro_rc=0 intro_bin

  if [[ -f $SCRIPT_DIR/clawd-intro && -x $SCRIPT_DIR/clawd-intro ]]; then
    intro_bin=$SCRIPT_DIR/clawd-intro
  else
    intro_bin=$HOME/.local/bin/clawd-intro
  fi

  if [[ -z ${CLAWD_NO_INTRO:-} && -t 0 && -t 1 && -n ${TERM:-} && $TERM != dumb && -f $intro_bin && -x $intro_bin ]]; then
    # Skip intro for subcommands (mcp, update, doctor, ...).
    case "${1:-}" in
      agents|attach|auth|auto-mode|doctor|gateway|import|install|logs|mcp|plugin|plugins|purge|respawn|rm|setup-token|stop|kill|ultrareview|update|upgrade)
        play=0 ;;
    esac

    # Skip intro for non-interactive flags (-p, --version, --help, --bg).
    for a in "$@"; do
      case "$a" in
        -p|--print|-v|--version|-h|--help|--bg)
          play=0
          break ;;
      esac
    done

    if (( play )); then
      "$intro_bin" || intro_rc=$?
      # Cancel launch on Ctrl-C / termination signals; ignore non-signal intro errors.
      (( intro_rc == 129 || intro_rc == 130 || intro_rc == 143 )) && return "$intro_rc"
    fi
  fi

  exec claude "$@"
}

main "$@"
