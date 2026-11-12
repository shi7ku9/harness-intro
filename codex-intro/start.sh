#!/usr/bin/env zsh
# start.sh — Launch OpenAI Codex after playing the woven-logo intro animation.
#   Uses ./codex-intro next to this script, falling back to ~/.local/bin/codex-intro.
#   Press any key to skip; CODEX_NO_INTRO=1 ./start.sh disables the animation.
#   CODEX_INTRO_SPEED=2 ./start.sh plays at 2x speed.

SCRIPT_DIR=${0:A:h}

main() {
  emulate -L zsh
  local play=1 i=1 first=1 kind=start arg intro_rc=0 intro_bin
  local -a intro_argv=("$@")

  if [[ -f $SCRIPT_DIR/codex-intro && -x $SCRIPT_DIR/codex-intro ]]; then
    intro_bin=$SCRIPT_DIR/codex-intro
  else
    intro_bin=~/.local/bin/codex-intro
  fi

  if [[ -z ${CODEX_NO_INTRO:-} && -t 0 && -t 1 && -n ${TERM:-} && $TERM != dumb && -f $intro_bin && -x $intro_bin ]]; then
    # Inspect launch arguments to decide whether to play, without mutating args passed to Codex.
    while (( i <= ${#intro_argv} )); do
      arg=${intro_argv[i]}
      case "$arg" in
        --)
          # Everything after `--` is a positional prompt/argument, not a flag or subcommand.
          break ;;
        -h|-V|--help|--version|--no-alt-screen)
          play=0
          break ;;
        -c|-m|-p|-s|-C|-a|--config|--model|--profile|--sandbox|--cd|--ask-for-approval|--enable|--disable|--remote|--remote-auth-token-env|--local-provider|--add-dir)
          (( i < ${#intro_argv} )) || { play=0; break; }
          (( i += 2 ))
          continue ;;
        -c?*|-m?*|-p?*|-s?*|-C?*|-a?*|--config=*|--model=*|--profile=*|--sandbox=*|--cd=*|--ask-for-approval=*|--enable=*|--disable=*|--remote=*|--remote-auth-token-env=*|--local-provider=*|--add-dir=*|-i?*|--image=*)
          ;; # Inline option values cannot be subcommands.
        -i|--image)
          # Space-separated `--image` consumes all subsequent non-option args; `--image=` consumes one.
          (( ++i ))
          if (( i > ${#intro_argv} )) || [[ ${intro_argv[i]} == -* ]]; then
            play=0
            break
          fi
          while (( i <= ${#intro_argv} )) && [[ ${intro_argv[i]} != -* ]]; do
            (( ++i ))
          done
          continue ;;
        --strict-config|--oss|--approve-for-me|--dangerously-bypass-approvals-and-sandbox|--dangerously-bypass-hook-trust|--worktree|--search|--no-daemon)
          ;;
        --last|--all)
          [[ $kind == resume || $kind == fork ]] || { play=0; break; } ;;
        --include-non-interactive)
          [[ $kind == resume ]] || { play=0; break; } ;;
        -*)
          # Let unknown flags pass straight through to Codex without playing.
          play=0
          break ;;
        *)
          if (( first )); then
            first=0
            case "$arg" in
              resume|fork|agents)
                kind=$arg ;;
              exec|e|review|login|logout|mcp|plugin|app-server|remote-control|completion|update|doctor|sandbox|debug|apply|a|queue|archive|delete|migrate-rollouts|migrate-nfs-db|unarchive|cloud|exec-server|features|help)
                play=0
                break ;;
            esac
          fi ;;
      esac
      (( ++i ))
    done

    if (( play )); then
      "$intro_bin" || intro_rc=$?
      # Cancel launch on Ctrl-C / termination signals; ignore non-signal intro errors.
      (( intro_rc == 129 || intro_rc == 130 || intro_rc == 143 )) && return "$intro_rc"
    fi
  fi

  exec codex "$@"
}

main "$@"
