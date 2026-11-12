#!/usr/bin/env python3
"""Exercise real terminal output without Codex, a GUI, or third-party modules."""
import codecs
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import termios
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "codex-intro"
ENTER = b"\x1b[?1049h"
LEAVE = b"\x1b[?1049l"


class Screen:
    """Track the cursor and Braille cells emitted by the intro's ANSI subset."""

    def __init__(self, rows, cols):
        self.rows, self.cols = rows, cols
        self.row = self.col = 0
        self.cells = {}
        self.frames = []
        self.violations = []
        self.pending = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")()

    def resize(self, rows, cols):
        self.rows, self.cols = rows, cols
        self.cells = {pos: ch for pos, ch in self.cells.items()
                      if pos[0] < rows and pos[1] < cols}

    def snapshot(self):
        points = [(r, c) for (r, c), ch in self.cells.items()
                  if "\u2801" <= ch <= "\u28ff"]
        bounds = None if not points else (
            min(c for r, c in points), min(r for r, c in points),
            max(c for r, c in points) + 1, max(r for r, c in points) + 1)
        self.frames.append(((self.rows, self.cols), bounds))

    def feed(self, data):
        self.pending += self.decoder.decode(data)
        while self.pending:
            text = self.pending
            if text.startswith("\x1b"):
                match = re.match(r"\x1b\[([0-?]*)([ -/]*)([@-~])", text)
                if not match:
                    return
                params, _, op = match.groups()
                self.pending = text[match.end():]
                if op == "H":
                    row, col = (int(n) for n in params.split(";"))
                    self.row, self.col = row - 1, col - 1
                    if not (0 <= self.row < self.rows and 0 <= self.col < self.cols):
                        self.violations.append((self.rows, self.cols, row, col))
                elif op == "J" and params == "2":
                    self.cells.clear()
                elif op == "l" and params in ("?2026", "?1049"):
                    self.snapshot()
                continue
            self.pending = text[1:]
            ch = text[0]
            if ch == "\r":
                self.col = 0
            elif ch == "\n":
                self.row += 1
            elif ord(ch) >= 32:
                if not (0 <= self.row < self.rows and 0 <= self.col < self.cols):
                    self.violations.append((self.rows, self.cols, self.row + 1, self.col + 1))
                self.cells[self.row, self.col] = ch
                self.col += 1


def capture(rows=57, cols=205, *, env=None, actions=(), timeout=4):
    """Actions are (elapsed seconds, 'input'|'resize', bytes|(rows, cols))."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    before = termios.tcgetattr(slave)
    child_env = dict(os.environ, TERM="xterm-256color", LANG="C.UTF-8",
                     LC_ALL="C.UTF-8", COLORTERM="truecolor", CODEX_INTRO_SPEED="30")
    for key in ("CODEX_NO_INTRO", "NO_COLOR"):
        child_env.pop(key, None)
    child_env.update(env or {})

    def setup():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    proc = subprocess.Popen([str(SCRIPT)], stdin=slave, stdout=slave, stderr=slave,
                            env=child_env, preexec_fn=setup)
    screen = Screen(rows, cols)
    output = bytearray()
    pending = list(actions)
    start = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise AssertionError("Intro did not finish before timeout")
            while pending and pending[0][0] <= elapsed:
                _, kind, value = pending.pop(0)
                if proc.poll() is not None:
                    raise AssertionError("Intro exited before the requested action")
                if kind == "resize":
                    screen.resize(*value)
                    fcntl.ioctl(slave, termios.TIOCSWINSZ,
                                struct.pack("HHHH", *value, 0, 0))
                else:
                    os.write(master, value)
            if select.select([master], [], [], .01)[0]:
                data = os.read(master, 65536)
                output.extend(data)
                screen.feed(data)
            if proc.poll() is not None:
                while select.select([master], [], [], 0)[0]:
                    data = os.read(master, 65536)
                    output.extend(data)
                    screen.feed(data)
                break
        return proc.returncode, bytes(output), screen, before == termios.tcgetattr(slave)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(master)
        os.close(slave)


class IntroTests(unittest.TestCase):
    def check_capture(self, *args, expected_code=0, **kwargs):
        code, raw, screen, restored = capture(*args, **kwargs)
        self.assertEqual(code, expected_code)
        self.assertTrue(restored, "Terminal settings were not restored")
        self.assertEqual(screen.violations, [], "Rendering exceeded the terminal")
        if ENTER in raw:
            self.assertTrue(raw.endswith(b"\x1b[?2026l\x1b[0m\x1b[?25h" + LEAVE))
        return raw, screen

    def test_native_background_geometry(self):
        # Bounds were measured from native Codex's welcome screen, not this script.
        for rows, cols, expected in (
            (57, 205, (86, 20, 119, 37)),
            (36, 120, (44, 9, 77, 26)),
            (32, 80, (24, 7, 57, 24)),
        ):
            with self.subTest(rows=rows, cols=cols):
                raw, screen = self.check_capture(rows, cols)
                self.assertIn(b"OpenAI Codex", raw)
                self.assertEqual(screen.frames[-1][1], expected)

    def test_native_visibility_boundaries(self):
        for rows, cols in ((31, 80), (60, 43)):
            with self.subTest(rows=rows, cols=cols):
                raw, _ = self.check_capture(rows, cols)
                self.assertEqual(raw, b"")
        raw, screen = self.check_capture(25, 44)
        self.assertIn(ENTER, raw)
        self.assertIsNotNone(screen.frames[-1][1])

    def test_resize_recenters_and_keeps_playing(self):
        raw, screen = self.check_capture(
            env={"CODEX_INTRO_SPEED": "0.5"},
            actions=((2.3, "resize", (36, 120)), (2.6, "input", b"x")))
        bounds = [bounds for size, bounds in screen.frames if size == (36, 120) and bounds]
        self.assertTrue(bounds, "No frame was redrawn after resizing")
        self.assertEqual(bounds[-1], (44, 9, 77, 26))

    def test_shrink_below_minimum_exits_cleanly(self):
        self.check_capture(env={"CODEX_INTRO_SPEED": "0.5"},
                           actions=((.3, "resize", (8, 20)),))

    def test_skip_and_interrupt_restore_terminal(self):
        for key, code in ((b"x", 0), (b"\x1b[A", 0), (b"\x03", 130)):
            with self.subTest(key=key):
                self.check_capture(env={"CODEX_INTRO_SPEED": "0.5"},
                                   actions=((.3, "input", key),), expected_code=code)

    def test_no_color(self):
        raw, screen = self.check_capture(env={"NO_COLOR": "1"})
        self.assertNotRegex(raw, rb"\x1b\[38;")
        self.assertEqual(screen.frames[-1][1], (86, 20, 119, 37))

    def test_unsupported_terminal_skips(self):
        for env in ({"CODEX_NO_INTRO": "1"}, {"TERM": "dumb"}, {"LC_ALL": "C"}):
            with self.subTest(env=env):
                raw, _ = self.check_capture(env=env)
                self.assertEqual(raw, b"")
        result = subprocess.run([str(SCRIPT)], capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))


if __name__ == "__main__":
    unittest.main()
