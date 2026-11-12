# Codex intro

Run `./start.sh` to play the woven-logo animation and launch Codex. Press any
key to skip, or Ctrl-C to cancel launch. `CODEX_NO_INTRO=1` disables the intro;
`CODEX_INTRO_SPEED=2` plays it at twice the speed.

The logo matches the empty-screen background in **Codex 0.167.2**, including
the native Braille glyphs and their position. It uses the full terminal as
its reference, so the title and skip hint do not move the logo upward.

| Terminal size (columns × rows) | Behavior |
| --- | --- |
| 205 × 57, 120 × 36, 80 × 32 | Same 33 × 17 logo, centered native stage |
| 60 × 30 | Smaller 30 × 15 logo |
| 44 × 25 | Smallest supported 22 × 12 logo |
| 80 × 31, 80 × 24, 43 × 60 | Intro skipped, matching the hidden background |

Codex uses a stage of `min(columns - 4, 60)` columns and
`floor(stage_width * 21 / 60)` rows, centered with integer rounding. Its
visible mark has asymmetric blank margins inside that stage; the intro
preserves those offsets. Widths 44–63 each have their own native glyphs;
wider terminals keep the largest size. Height only controls visibility.

The visibility threshold matches the normal empty composer with the status
line enabled: three header rows and six rows for the composer, footer and
gap. Custom status-line settings or startup notices can change when Codex
itself hides the mark. The geometry is pinned to 0.167.2 and may need updating
when Codex changes its background.

Resizing during playback clears and redraws the current animation at its new
position and size. If the background no longer fits, the intro exits cleanly
and the launcher proceeds to Codex. Terminal settings and cursor visibility
are restored on completion, skip, cancellation, and resize exit.

The 21 glyph variants were captured from the local Codex terminal output.
The upstream rules are in
[empty_state_animation.rs](https://github.com/openai/codex/blob/rust-v0.167.2/codex-rs/tui/src/empty_state_animation.rs)
and its
[renderer](https://github.com/openai/codex/blob/rust-v0.167.2/codex-rs/tui/src/empty_state_animation/renderer.rs).

Run the terminal regression checks with Python's standard library:

```sh
bash -n codex-intro/codex-intro
python3 -m unittest discover -s codex-intro/tests -v
```

The checks use real pseudo-terminals, without starting Codex or requiring a
GUI. They cover reference coordinates, visibility thresholds, live resizing,
key skipping, interruption, color settings, and terminal restoration.
