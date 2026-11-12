#!/usr/bin/env zsh
# start.sh — Launch Antigravity CLI (agy) after playing the levitating-delta intro animation.
#   Uses ./agy-intro next to this script, falling back to ~/.local/bin/agy-intro.
#   Press any key to skip; AGY_NO_INTRO=1 ./start.sh disables the animation.
#   AGY_INTRO_SPEED=2 ./start.sh plays at 2x speed.

SCRIPT_DIR=${0:A:h}

main() {
  emulate -L zsh
  local play=1 i=1 first=1 arg intro_rc=0 intro_bin
  local -a intro_argv=("$@")

  if [[ -f $SCRIPT_DIR/agy-intro && -x $SCRIPT_DIR/agy-intro ]]; then
    intro_bin=$SCRIPT_DIR/agy-intro
  else
    intro_bin=~/.local/bin/agy-intro
  fi

  if [[ -z ${AGY_NO_INTRO:-} && -t 0 && -t 1 && -n ${TERM:-} && $TERM != dumb && -f $intro_bin && -x $intro_bin ]]; then
    # Inspect launch arguments to decide whether to play, without mutating args passed to agy.
    while (( i <= ${#intro_argv} )); do
      arg=${intro_argv[i]}
      case "$arg" in
        --)
          # Everything after `--` is positional, not a flag or subcommand.
          break ;;
        -h|--help|-v|--version|-p|--print|--prompt|--print=*|--prompt=*)
          play=0
          break ;;
        -i|--add-dir|--agent|--conversation|--effort|--input-format|--json-schema|--log-file|--mode|--model|--output-format|--print-timeout|--project|--prompt-interactive|--remote-agent|--settings)
          (( i < ${#intro_argv} )) || { play=0; break; }
          (( i += 2 ))
          continue ;;
        -i?*|--add-dir=*|--agent=*|--conversation=*|--effort=*|--input-format=*|--json-schema=*|--log-file=*|--mode=*|--model=*|--output-format=*|--print-timeout=*|--project=*|--prompt-interactive=*|--remote-agent=*|--settings=*)
          ;; # Inline option values cannot be subcommands.
        -c|--continue|--dangerously-skip-permissions|--disable-slash-commands|--new-project|--remote-control|--sandbox)
          ;;
        -*)
          # Let unknown flags pass straight through to agy without playing.
          play=0
          break ;;
        *)
          if (( first )); then
            first=0
            case "$arg" in
              acp|agent|agents|changelog|help|install|mcp|mic-serve|models|plugin|plugins|remote-control|update)
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

  exec agy "$@"
}

main "$@"
