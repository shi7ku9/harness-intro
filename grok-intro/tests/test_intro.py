"""Exercise the animation in real terminals without starting Grok or a GUI."""
import codecs
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unicodedata
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "grok-intro"
ENTER = b"\x1b[?1049h"
LEAVE = b"\x1b[?1049l"
# Reference extracted independently from the installed Grok 1.0.77 binary.
NATIVE = (
    "⠀⠀⠀⠀⠀⠀⣀⣀⡀⠀⠀⠀⢀⠄",
    "⠀⠀⠀⣠⣾⠿⠛⠛⠛⠛⢀⡴⠁⠀",
    "⠀⠀⣼⡟⠁⠀⠀⠀⢀⡴⠻⣿⡀⠀",
    "⠀⠀⣿⡇⠀⠀⠀⠔⠁⠀⠀⣿⡇⠀",
    "⠀⠀⢹⣷⠀⠀⠀⠀⠀⢀⣴⡿⠀⠀",
    "⠀⢀⠞⠁⠠⢶⣶⣶⣶⠿⠋⠀⠀⠀",
    "⠐⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
)


def width(char):
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in "WF" else 1


class Screen:
    """Minimal ANSI screen for this animation, including CJK character widths."""

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
                    row, col = map(int, params.split(";"))
                    self.row, self.col = row - 1, col - 1
                    if not (0 <= self.row < self.rows and 0 <= self.col < self.cols):
                        self.violations.append((self.rows, self.cols, row, col))
                elif op == "J" and params == "2":
                    self.cells.clear()
                elif op == "l" and params == "?2026":
                    self.frames.append(((self.rows, self.cols), dict(self.cells)))
                continue
            self.pending = text[1:]
            char = text[0]
            if char == "\r":
                self.col = 0
            elif char == "\n":
                self.row += 1
            elif ord(char) >= 32:
                size = width(char)
                if not (0 <= self.row < self.rows and 0 <= self.col <= self.cols - size):
                    self.violations.append((self.rows, self.cols, self.row + 1, self.col + 1))
                self.cells[self.row, self.col] = char
                self.col += size


def capture(rows=24, cols=80, *, env=None, actions=(), cwd=None, timeout=6, program=SCRIPT):
    """Actions: (seconds since alternate-screen entry, input/resize/signal, value)."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    before = termios.tcgetattr(slave)
    child_env = dict(os.environ, TERM="xterm-256color", LANG="C.UTF-8",
                     LC_ALL="C.UTF-8", COLORTERM="truecolor", GROK_INTRO_SPEED="30")
    for key in ("GROK_NO_INTRO", "NO_COLOR"):
        child_env.pop(key, None)
    child_env.update(env or {})

    def setup():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    proc = subprocess.Popen([str(program)], stdin=slave, stdout=slave, stderr=slave,
                            env=child_env, cwd=cwd, preexec_fn=setup)
    screen = Screen(rows, cols)
    output = bytearray()
    pending = list(actions)
    start = time.monotonic()
    entered = None

    def drain():
        nonlocal entered
        while select.select([master], [], [], 0)[0]:
            data = os.read(master, 65536)
            output.extend(data)
            screen.feed(data)
            if entered is None and ENTER in output:
                entered = time.monotonic()

    try:
        while True:
            drain()
            now = time.monotonic()
            if now - start > timeout:
                raise AssertionError("Intro did not finish before timeout")
            while entered is not None and pending and pending[0][0] <= now - entered:
                _, kind, value = pending.pop(0)
                if proc.poll() is not None:
                    raise AssertionError("Intro exited before the requested action")
                if kind == "resize":
                    screen.resize(*value)
                    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", *value, 0, 0))
                elif kind == "signal":
                    os.killpg(proc.pid, value)
                else:
                    os.write(master, value)
            if proc.poll() is not None:
                drain()
                break
            select.select([master], [], [], .005)
        if pending:
            raise AssertionError("Intro exited before all requested actions")
        restored = before == termios.tcgetattr(slave)
        # Inspect pending input after restoration, without waiting for a newline.
        probe = termios.tcgetattr(slave)
        probe[3] &= ~(termios.ICANON | termios.ECHO)
        probe[6][termios.VMIN] = 0
        probe[6][termios.VTIME] = 0
        termios.tcsetattr(slave, termios.TCSANOW, probe)
        remainder = os.read(slave, 1024)
        termios.tcsetattr(slave, termios.TCSANOW, before)
        return proc.returncode, bytes(output), screen, restored, remainder
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(master)
        os.close(slave)


def artwork(size, cells):
    rows, cols = size
    top, left = (rows - 12) // 2, (cols - 14) // 2
    return tuple("".join(cells.get((top + row, left + col), " ") for col in range(14))
                 for row in range(7))


def dots(art):
    offsets = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3))
    return {(col * 2 + x, row * 4 + y) for row, line in enumerate(art)
            for col, char in enumerate(line) if "\u2800" <= char <= "\u28ff"
            for bit, (x, y) in enumerate(offsets) if (ord(char) - 0x2800) & (1 << bit)}


class IntroTests(unittest.TestCase):
    def check_capture(self, *args, expected_code=0, **kwargs):
        code, raw, screen, restored, remainder = capture(*args, **kwargs)
        self.assertEqual(code, expected_code, raw.decode(errors="replace"))
        self.assertTrue(restored, "Terminal settings were not restored")
        self.assertEqual(remainder, b"", "Input leaked into the next application")
        self.assertEqual(screen.violations, [], "Rendering exceeded the terminal")
        self.assertEqual(screen.pending, "", "Incomplete or unsupported ANSI output")
        if ENTER in raw:
            self.assertTrue(raw.endswith(b"\x1b[?2026l\x1b[0m\x1b[?25h" + LEAVE))
        return raw, screen

    def test_native_logo_and_centering(self):
        for size in ((24, 80), (36, 120), (57, 205), (14, 30), (15, 31)):
            with self.subTest(size=size):
                raw, screen = self.check_capture(*size)
                self.assertEqual(artwork(size, screen.cells), NATIVE)
                self.assertIn(b"Grok Build", raw)
                self.assertIn(b"press any key to skip", raw)

    def test_ring_precedes_slash_and_preserves_native_dots(self):
        _, screen = self.check_capture()
        native = dots(NATIVE)
        frames = [dots(artwork(size, cells)) for size, cells in screen.frames]
        previous = set()
        for frame in frames:
            self.assertLessEqual(previous, frame, "Dots vanished during the reveal")
            self.assertLessEqual(frame, native, "Animation changed the logo's shape")
            previous = frame
        # Isolated slash dots must follow the ring's left and right edges.
        first = lambda point: next(i for i, frame in enumerate(frames) if point in frame)
        self.assertLess(first((14, 3)), first((24, 12)))  # top before right edge
        self.assertLess(first((24, 12)), first((14, 22)))  # then bottom
        self.assertLess(first((14, 22)), first((4, 12)))  # then left
        self.assertLess(first((4, 12)), first((1, 25)))  # slash begins afterward
        self.assertLess(first((1, 25)), first((14, 14)))  # lower left to center
        self.assertLess(first((14, 14)), first((26, 2)))  # center to upper right
        self.assertEqual(frames[-1], native)

    def test_too_small_is_silent(self):
        for size in ((13, 80), (30, 29), (8, 20)):
            with self.subTest(size=size):
                raw, _ = self.check_capture(*size)
                self.assertEqual(raw, b"")

    def test_resize_recenters_without_restarting(self):
        _, screen = self.check_capture(env={"GROK_INTRO_SPEED": "2"},
                                       actions=((.2, "resize", (36, 120)),))
        self.assertEqual(artwork((36, 120), screen.cells), NATIVE)
        resized = [(size, cells) for size, cells in screen.frames if size == (36, 120)]
        self.assertTrue(resized)
        self.assertGreater(len(dots(artwork(*resized[0]))), 10)

    def test_resize_during_title_and_hold(self):
        _, screen = self.check_capture(env={"GROK_INTRO_SPEED": "1"},
                                       actions=((1.3, "resize", (20, 40)),
                                                (1.6, "resize", (14, 30))))
        self.assertEqual(artwork((14, 30), screen.cells), NATIVE)
        title_row = (14 - 12) // 2 + 8
        line = "".join(screen.cells.get((title_row, col), " ") for col in range(30))
        self.assertIn("Grok Build", line)

    def test_shrink_exits_cleanly(self):
        self.check_capture(env={"GROK_INTRO_SPEED": "1"},
                           actions=((.1, "resize", (8, 20)),))

    def test_skip_and_signals_restore_terminal(self):
        for key in (b"x", b" ", b"\r", b"\x1b", b"\x1b[A", b"\x1b[1;5D", b"\x1bOP"):
            with self.subTest(key=key):
                self.check_capture(env={"GROK_INTRO_SPEED": "1"}, actions=((.05, "input", key),))
        self.check_capture(env={"GROK_INTRO_SPEED": "1"}, actions=((.05, "input", b"\x03"),),
                           expected_code=130)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=sig):
                self.check_capture(env={"GROK_INTRO_SPEED": "1"},
                                   actions=((.05, "signal", sig),), expected_code=128 + sig)

    def test_color_modes(self):
        raw, _ = self.check_capture(env={"NO_COLOR": "1"})
        self.assertNotRegex(raw, rb"\x1b\[38;")
        raw, _ = self.check_capture(env={"COLORTERM": ""})
        self.assertIn(b"\x1b[38;5;", raw)
        self.assertNotIn(b"\x1b[38;2;", raw)
        raw, _ = self.check_capture()
        self.assertIn(b"\x1b[38;2;", raw)

    def test_invalid_speed_defaults_and_extreme_speed_finishes(self):
        for speed in ("0", "garbage", "-2"):
            with self.subTest(speed=speed):
                # Normal playback is still running after 0.1s; a zero/invalid delay isn't.
                self.check_capture(env={"GROK_INTRO_SPEED": speed}, actions=((.1, "input", b"x"),))
        self.check_capture(env={"GROK_INTRO_SPEED": "99999999"})

    def test_unsupported_environment_is_silent(self):
        for env in ({"GROK_NO_INTRO": "1"}, {"TERM": "dumb"}, {"TERM": ""}, {"LC_ALL": "C"}):
            with self.subTest(env=env):
                raw, _ = self.check_capture(env=env)
                self.assertEqual(raw, b"")
        result = subprocess.run([str(SCRIPT)], capture_output=True, timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))

    def test_directory_abbreviation_sanitization_and_display_width(self):
        with tempfile.TemporaryDirectory(prefix="grok-intro-test-") as root:
            raw, screen = self.check_capture(cwd=root, env={"HOME": root})
            self.assertIn("~", screen.cells.values())
            path = Path(root) / ("資料夾" * 12 + "\x1b[31m\nend")
            path.mkdir()
            raw, screen = self.check_capture(14, 30, cwd=path)
            self.assertNotIn(b"\x1b[31m", raw)
            row = (14 - 12) // 2 + 9
            subtitle = "".join(ch for (r, c), ch in sorted(screen.cells.items()) if r == row)
            self.assertTrue(subtitle.startswith("…"))
            self.assertTrue(subtitle.endswith("[31mend"))
            self.assertLessEqual(sum(map(width, subtitle)), 24)

    def test_real_launcher_handoff_and_cancellation(self):
        with tempfile.TemporaryDirectory(prefix="grok-intro-handoff-") as directory:
            root = Path(directory)
            launcher = root / "start.sh"
            shutil.copy2(SCRIPT.parent / "start.sh", launcher)
            (root / "grok-intro").symlink_to(SCRIPT)
            log = root / "launched"
            stub = root / "grok"
            stub.write_text(
                f"#!{sys.executable}\n"
                "import os, termios\n"
                "from pathlib import Path\n"
                "state = termios.tcgetattr(0)\n"
                "assert state[3] & termios.ICANON and state[3] & termios.ECHO\n"
                "Path(os.environ['INTRO_HANDOFF_LOG']).write_text('restored')\n"
            )
            stub.chmod(0o755)
            # Isolate Zsh startup files so they cannot replace our stub PATH.
            env = {"HOME": str(root), "ZDOTDIR": str(root),
                   "PATH": str(root) + ":/usr/bin:/bin", "INTRO_HANDOFF_LOG": str(log)}
            for key in (None, b"\x1b[A", b"\x03"):
                with self.subTest(key=key):
                    log.unlink(missing_ok=True)
                    actions = () if key is None else ((.05, "input", key),)
                    code, raw, screen, restored, remainder = capture(
                        program=launcher, env=dict(env, GROK_INTRO_SPEED="1" if key else "30"),
                        actions=actions)
                    # Zsh may itself receive SIGINT; the invoking shell still sees 130.
                    self.assertIn(code, (130, -signal.SIGINT) if key == b"\x03" else (0,))
                    self.assertTrue(restored)
                    self.assertEqual(remainder, b"")
                    self.assertIn(LEAVE, raw)
                    self.assertEqual(screen.violations, [])
                    self.assertEqual(log.exists(), key != b"\x03")
                    if log.exists():
                        self.assertEqual(log.read_text(), "restored")


if __name__ == "__main__":
    unittest.main()
