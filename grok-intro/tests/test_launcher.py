"""Check launcher decisions in real PTYs, using local stubs instead of Grok."""
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import sys
import tempfile
import unittest


LAUNCHER = Path(__file__).resolve().parents[1] / "start.sh"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="grok launcher ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.launcher = self.root / "start.sh"
        shutil.copy2(LAUNCHER, self.launcher)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.home = self.root / "home"
        self.fallback = self.home / ".local/bin/grok-intro"
        self.fallback.parent.mkdir(parents=True)
        self.local_intro = self.root / "grok-intro"
        self.intro_log = self.root / "intro.log"
        self.grok_log = self.root / "grok.json"
        self.write_intro(self.local_intro, "local")
        self.write_intro(self.fallback, "fallback")
        grok = self.bin_dir / "grok"
        grok.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['TEST_GROK_LOG'], 'w') as log:\n"
            "    json.dump({'args': sys.argv[1:], 'cwd': os.getcwd()}, log)\n"
            "sys.exit(int(os.environ.get('TEST_GROK_RC', '0')))\n"
        )
        grok.chmod(0o755)

    @staticmethod
    def write_intro(path, name):
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' '{name}' >> \"$TEST_INTRO_LOG\"\n"
            'exit "${TEST_INTRO_RC:-0}"\n'
        )
        path.chmod(0o755)

    def run_launcher(self, args=(), *, env=None, tty_in=True, tty_out=True):
        self.intro_log.unlink(missing_ok=True)
        self.grok_log.unlink(missing_ok=True)
        child_env = dict(os.environ, HOME=str(self.home), ZDOTDIR=str(self.home), TERM="xterm-256color",
                         PATH=f"{self.bin_dir}:{os.environ['PATH']}",
                         TEST_INTRO_LOG=str(self.intro_log), TEST_GROK_LOG=str(self.grok_log))
        for name in ("GROK_NO_INTRO", "TEST_INTRO_RC", "TEST_GROK_RC"):
            child_env.pop(name, None)
        child_env.update(env or {})
        master, slave = pty.openpty()
        try:
            result = subprocess.run(
                [str(self.launcher), *args], cwd=self.root, env=child_env,
                stdin=slave if tty_in else subprocess.DEVNULL,
                stdout=slave if tty_out else subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=4,
            )
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(result.stderr, b"")
        played = self.intro_log.read_text().splitlines() if self.intro_log.exists() else []
        launched = json.loads(self.grok_log.read_text()) if self.grok_log.exists() else None
        if launched is not None:
            self.assertEqual(launched, {"args": list(args), "cwd": str(self.root)})
        return result.returncode, played, launched

    def assert_launch(self, args=(), *, plays=True, **kwargs):
        code, played, launched = self.run_launcher(args, **kwargs)
        self.assertEqual(code, 0)
        self.assertEqual(played, ["local"] if plays else [])
        self.assertIsNotNone(launched)

    def test_interactive_and_resume_options(self):
        for args in ((), ("Explain this project",), ("-c",), ("--continue",),
                     ("-r",), ("--resume", "models"), ("--resume=doctor",),
                     ("-rmy session",), ("--resume", "--continue"),
                     ("--worktree",), ("--worktree", "models"), ("-wwork",),
                     ("--fullscreen", "--no-plan", "--verbatim", "hello")):
            with self.subTest(args=args):
                self.assert_launch(args)

    def test_option_values_do_not_become_subcommands(self):
        options = ("-m", "-s", "--model", "--cwd", "--agent", "--agents", "--rules",
                   "--allow", "--allowedTools", "--allowed-tools", "--deny",
                   "--disallowedTools", "--disallowed-tools", "--add-dir", "--debug-file",
                   "--leader-socket", "--max-turns", "--permission-mode", "--reasoning-effort",
                   "--effort", "--session-id", "--sandbox", "--system-prompt-override",
                   "--system-prompt", "--tools", "--worktree-ref", "--ref")
        for option in options:
            with self.subTest(option=option):
                self.assert_launch((option, "models"))
                inline = f"{option}=models" if option.startswith("--") else f"{option}models"
                self.assert_launch((inline,))
        self.assert_launch(("--rules", "has spaces; $(do-not-run) `literal`\nnext line", ""))

    def test_subcommands_skip_with_options_and_initial_prompt(self):
        commands = "agent clone completions dashboard doctor du disk-usage export help inspect leader login logout mcp memory models plugin sessions setup trace update usage version v worker worktree wrap".split()
        for command in commands:
            with self.subTest(command=command):
                self.assert_launch((command,), plays=False)
                self.assert_launch(("--model", "example", command), plays=False)
        self.assert_launch(("initial prompt", "models"), plays=False)

    def test_headless_inline_and_diagnostic_options_skip(self):
        for args in (("-h",), ("--help",), ("-v",), ("--version",),
                     ("-p", "hello"), ("-phello",), ("--single", "hello"), ("--single=hello",),
                     ("--prompt-file", "file"), ("--prompt-file=file",),
                     ("--prompt-json", "[]"), ("--prompt-json=[]",),
                     ("--output-format", "json"), ("--output-format=json",),
                     ("--include-partial-messages",), ("--json-schema", "{}"), ("--json-schema={}",),
                     ("--minimal",), ("--no-alt-screen",), ("--future-option",),
                     ("--model",), ("--model", "--help")):
            with self.subTest(args=args):
                self.assert_launch(args, plays=False)

    def test_double_dash_ends_launcher_option_parsing(self):
        self.assert_launch(("--", "--help"))
        self.assert_launch(("--", "models"))
        self.assert_launch(("--resume", "--", "--single"))

    def test_disabled_or_unsupported_environment_skips(self):
        for env in ({"GROK_NO_INTRO": "1"}, {"TERM": "dumb"}, {"TERM": ""}):
            with self.subTest(env=env):
                self.assert_launch(env=env, plays=False)
        self.assert_launch(tty_in=False, plays=False)
        self.assert_launch(tty_out=False, plays=False)

    def test_fallback_and_missing_animation(self):
        self.local_intro.chmod(0o644)
        code, played, launched = self.run_launcher()
        self.assertEqual((code, played), (0, ["fallback"]))
        self.assertIsNotNone(launched)
        self.local_intro.unlink()
        code, played, launched = self.run_launcher()
        self.assertEqual((code, played), (0, ["fallback"]))
        self.assertIsNotNone(launched)
        self.fallback.unlink()
        self.assert_launch(plays=False)

    def test_cancellation_stops_launch_and_errors_continue(self):
        for code in (129, 130, 143):
            with self.subTest(code=code):
                status, played, launched = self.run_launcher(env={"TEST_INTRO_RC": str(code)})
                self.assertEqual((status, played, launched), (code, ["local"], None))
        self.assert_launch(env={"TEST_INTRO_RC": "1"})
        status, played, launched = self.run_launcher(env={"TEST_GROK_RC": "23"})
        self.assertEqual((status, played), (23, ["local"]))
        self.assertIsNotNone(launched)


if __name__ == "__main__":
    unittest.main()
