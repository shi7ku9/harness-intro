# Grok intro

Run from the repository root:

```sh
./grok-intro/start.sh
```

The intro reveals the ring clockwise, draws the slash from lower left to upper
right, briefly brightens the logo, and types **Grok Build** above the current
directory. Playback lasts about 1.8 seconds at normal speed, plus frame
preparation. Any key skips to Grok; Ctrl-C cancels startup.

```sh
GROK_NO_INTRO=1 ./grok-intro/start.sh       # Launch immediately
GROK_INTRO_SPEED=2 ./grok-intro/start.sh    # Play at twice the speed
./grok-intro/start.sh --resume            # Pass arguments through to Grok
./grok-intro/grok-intro                   # Preview without launching Grok
```

The 14 × 7 Unicode Braille mark is embedded verbatim from the local
**Grok 1.0.77 (50ca579fa996)** executable. The animation separates its ring and
slash at the dot level, including the cell where they meet, and finishes on
the unchanged native artwork. It centers the logo, title, directory, and skip
hint as one group; it does not reproduce Grok's own startup layout. No binary
extraction, network request, or image protocol is needed during playback.

The animation needs Bash 4 or later, `awk`, GNU `wc`, `stty`, a UTF-8 locale,
and a terminal with at least 30 columns and 14 rows. The launcher needs Zsh
and `grok` on `PATH`. Colors use a gray/white palette with truecolor and
256-color support; `NO_COLOR=1` uses the terminal's default foreground.
Invalid or zero speed values fall back to 1, and frame delays never drop
below one millisecond.

Resizing recenters the current frame without restarting. Shrinking below the
minimum ends the intro and continues startup. Long directories are truncated
using their display width; control characters are removed. Terminal settings,
cursor visibility, colors, and the original screen are restored on completion,
skip, interruption, and resize exit. Navigation-key sequences are consumed so
they do not leak into Grok.

The launcher prefers the executable beside it, with `~/.local/bin/grok-intro`
as a fallback. It plays for interactive launches, initial prompts, and
continue/resume sessions. It skips all subcommands, help/version requests,
single-turn and structured-output options, `--minimal`, `--no-alt-screen`, and
unknown flags. Option values and `--` are respected, and the original argument
list is passed unchanged to `grok`. Non-TTY input/output, a missing or `dumb`
`TERM`, a non-UTF-8 locale, or `GROK_NO_INTRO` also skip playback.

An ordinary animation error does not prevent Grok from starting. Cancellation
statuses 129 (HUP), 130 (INT), and 143 (TERM) stop the launcher. This directory
does not install anything or change shell configuration. Logo and option
compatibility are pinned to Grok 1.0.77; review them when updating Grok.

Run the syntax and regression checks from the repository root:

```sh
bash -n grok-intro/grok-intro
zsh -n grok-intro/start.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s grok-intro/tests -v
```

Tests use Python's standard library, real pseudo-terminals, and temporary
launcher stubs. They cover native dots and reveal order, centering, resizing,
skip/cancellation, input cleanup, terminal restoration, colors, speed settings,
Unicode directory widths, argument preservation, bypass rules, and executable
fallbacks. They do not start a real Grok session or require a GUI.
