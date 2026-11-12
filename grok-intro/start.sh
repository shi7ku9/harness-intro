#!/usr/bin/env zsh
# Launch Grok after the terminal intro; press any key to skip.
# GROK_NO_INTRO=1 disables playback; GROK_INTRO_SPEED=2 doubles its speed.

SCRIPT_DIR=${0:A:h}

main() {
  emulate -L zsh
  local play=1 i=1 arg intro_rc=0 intro_bin
  local -a intro_argv=("$@")

  if [[ -f $SCRIPT_DIR/grok-intro && -x $SCRIPT_DIR/grok-intro ]]; then
    intro_bin=$SCRIPT_DIR/grok-intro
  else
    intro_bin=~/.local/bin/grok-intro
  fi

  if [[ -z ${GROK_NO_INTRO:-} && -t 0 && -t 1 && -n ${TERM:-} && $TERM != dumb && -f $intro_bin && -x $intro_bin ]]; then
    # Match Grok Build's options without changing the arguments it receives.
    while (( i <= ${#intro_argv} )); do
      arg=${intro_argv[i]}
      case "$arg" in
        --)
          # All remaining arguments are positional, even if they resemble flags.
          break ;;
        -h|--help|-v|--version|-p|-p?*|--single|--single=*|--prompt-file|--prompt-file=*|--prompt-json|--prompt-json=*|--output-format|--output-format=*|--include-partial-messages|--json-schema|--json-schema=*|--minimal|--no-alt-screen)
          play=0
          break ;;
        -m|-s|--add-dir|--agent|--agents|--allow|--allowedTools|--allowed-tools|--cwd|--debug-file|--deny|--disallowedTools|--disallowed-tools|--leader-socket|--model|--max-turns|--permission-mode|--reasoning-effort|--effort|--rules|--session-id|--sandbox|--system-prompt-override|--system-prompt|--tools|--worktree-ref|--ref)
          if (( i == ${#intro_argv} )) || [[ ${intro_argv[i+1]} == -* ]]; then
            play=0
            break
          fi
          (( i += 2 ))
          continue ;;
        -m?*|-s?*|--add-dir=*|--agent=*|--agents=*|--allow=*|--allowedTools=*|--allowed-tools=*|--cwd=*|--debug-file=*|--deny=*|--disallowedTools=*|--disallowed-tools=*|--leader-socket=*|--model=*|--max-turns=*|--permission-mode=*|--reasoning-effort=*|--effort=*|--rules=*|--session-id=*|--sandbox=*|--system-prompt-override=*|--system-prompt=*|--tools=*|--worktree-ref=*|--ref=*)
          ;; # An inline option value cannot be a subcommand.
        -r|--resume|-w|--worktree)
          # These accept an optional value, including a title named "models".
          if (( i < ${#intro_argv} )) && [[ ${intro_argv[i+1]} != -* ]]; then
            (( ++i ))
          fi ;;
        -r?*|-w?*|--resume=*|--worktree=*)
          ;;
        -c|--continue|--always-approve|--debug|--disable-web-search|--fork-session|--fullscreen|--no-plan|--no-subagents|--oauth|--restore-code|--verbatim)
          ;;
        -*)
          # Let Grok handle unknown flags without delaying diagnostics.
          play=0
          break ;;
        agent|clone|completions|dashboard|doctor|du|disk-usage|export|help|inspect|leader|login|logout|mcp|memory|models|plugin|sessions|setup|trace|update|usage|version|v|worker|worktree|wrap)
          play=0
          break ;;
      esac
      (( ++i ))
    done

    if (( play )); then
      "$intro_bin" || intro_rc=$?
      # Cancellation stops startup; a cosmetic intro failure does not.
      (( intro_rc == 129 || intro_rc == 130 || intro_rc == 143 )) && return "$intro_rc"
    fi
  fi

  exec grok "$@"
}

main "$@"
