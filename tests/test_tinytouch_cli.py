import importlib.machinery
import importlib.util
import plistlib
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("tinytouch_cli", str(ROOT / "tinytouch"))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


class PackagingTests(unittest.TestCase):
    def test_launch_agent_uses_current_repository(self):
        python = Path("/tmp/example-python")
        payload = plistlib.loads(cli.launch_agent_contents(python))
        self.assertEqual(payload["ProgramArguments"], [str(python), str(cli.HELPER)])
        self.assertTrue(payload["KeepAlive"])

    def test_device_errors_are_translated(self):
        message = cli.human_device_error("ERR STATUS sensor")
        self.assertIn("fingerprint sensor", message)
        self.assertNotIn("ERR STATUS", message)

    def test_closed_input_has_human_instruction(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(cli.ToolError) as context:
                cli.choose_mode(None)
        self.assertIn("--mode piv", str(context.exception))

    def test_frozen_cli_installs_itself_and_updates_zprofile(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / "downloaded-tinytouch"
            source.write_bytes(b"signed executable")
            install_dir = home / ".local" / "bin"
            install_path = install_dir / "tinytouch"
            with (
                mock.patch.object(cli, "FROZEN", True),
                mock.patch.object(cli, "CLI_INSTALL_DIR", install_dir),
                mock.patch.object(cli, "CLI_INSTALL_PATH", install_path),
                mock.patch.object(cli.sys, "executable", str(source)),
                mock.patch.object(cli.Path, "home", return_value=home),
            ):
                cli.install_command_if_needed()
            self.assertEqual(install_path.read_bytes(), source.read_bytes())
            self.assertIn(".local/bin", (home / ".zprofile").read_text())


class ParserTests(unittest.TestCase):
    def test_setup_mode(self):
        args = cli.parser().parse_args(["setup", "--mode", "piv", "--skip-enroll"])
        self.assertEqual(args.mode, "piv")
        self.assertTrue(args.skip_enroll)

    def test_delete_slot(self):
        args = cli.parser().parse_args(["delete", "--slot", "5"])
        self.assertEqual(args.slot, 5)
        self.assertFalse(args.all)
        self.assertFalse(args.yes)

    def test_mode_alias(self):
        args = cli.parser().parse_args(["mode", "hid", "--skip-enroll"])
        self.assertEqual(args.mode, "hid")
        self.assertTrue(args.skip_enroll)

    def test_customer_setup_has_no_firmware_build_options(self):
        args = cli.parser().parse_args(["setup", "--mode", "hid"])
        self.assertEqual(args.mode, "hid")
        self.assertFalse(hasattr(args, "board"))
        self.assertFalse(hasattr(args, "fqbn"))

    def test_verbose_before_command(self):
        args = cli.parser().parse_args(["--verbose", "status"])
        self.assertTrue(args.verbose)

    def test_verbose_after_command(self):
        args = cli.parser().parse_args(["status", "--verbose"])
        self.assertTrue(args.verbose)

    def test_verbose_defaults_off(self):
        args = cli.parser().parse_args(["status"])
        self.assertFalse(args.verbose)


if __name__ == "__main__":
    unittest.main()
