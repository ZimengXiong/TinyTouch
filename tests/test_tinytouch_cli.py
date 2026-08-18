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
    def test_version_comes_from_shared_version_file(self):
        self.assertEqual(cli.CLI_VERSION, (ROOT / "VERSION").read_text().strip())

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
                mock.patch.dict(cli.os.environ, {"SHELL": "/bin/zsh"}),
            ):
                cli.install_command_if_needed()
            self.assertEqual(install_path.read_bytes(), source.read_bytes())
            self.assertIn(".local/bin", (home / ".zprofile").read_text())

    def test_frozen_cli_updates_fish_path(self):
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
                mock.patch.dict(cli.os.environ, {"SHELL": "/opt/homebrew/bin/fish"}),
            ):
                cli.install_command_if_needed()
            fish_config = home / ".config" / "fish" / "config.fish"
            self.assertIn('fish_add_path "$HOME/.local/bin"', fish_config.read_text())

    def test_unhealthy_sensor_status_still_identifies_unified_firmware(self):
        response = [
            "OK STATUS firmware=unified mode=piv sensor=no_response "
            "fingerprints=unknown keys=nvs hid_key=unconfigured"
        ]
        with mock.patch.object(cli, "serial_command", return_value=response):
            fields = cli.status_fields("/dev/cu.example")
        self.assertEqual(fields["firmware"], "unified")
        self.assertEqual(fields["sensor"], "no_response")

    def test_malformed_status_is_explained(self):
        with mock.patch.object(cli, "serial_command", return_value=["OK STATUS sensor=ok"]):
            with self.assertRaises(cli.ToolError) as context:
                cli.status_fields("/dev/cu.example")
        self.assertIn("without a runtime mode", str(context.exception))

    def test_legacy_firmware_error_has_update_action(self):
        with self.assertRaises(cli.ToolError) as context:
            cli.require_unified_firmware({"mode": "piv", "sensor": "ok"})
        self.assertIn("Older tinyTouch firmware", str(context.exception))
        self.assertIn(cli.FACTORY_FLASH_URL, str(context.exception))

    def test_sensor_error_names_required_uart_wiring(self):
        with self.assertRaises(cli.ToolError) as context:
            cli.require_fingerprint_sensor({"firmware": "unified", "sensor": "no_response"})
        message = str(context.exception)
        self.assertIn("firmware is running", message)
        self.assertIn("GPIO44", message)
        self.assertIn("GPIO43", message)
        self.assertIn("GPIO2", message)

    def test_busy_serial_port_has_specific_recovery(self):
        message = cli.serial_failure_message("/dev/cu.example", OSError(16, "Device busy"))
        self.assertIn("is busy", message)
        self.assertIn("Serial Monitor", message)

    def test_setup_preserves_status_failure_reason(self):
        args = cli.parser().parse_args(["setup", "--mode", "piv"])
        with (
            mock.patch.object(cli, "require_macos"),
            mock.patch.object(cli, "show_startup_mark"),
            mock.patch.object(cli, "choose_port", return_value="/dev/cu.example"),
            mock.patch.object(cli, "port_is_download_mode", return_value=False),
            mock.patch.object(
                cli, "status_fields", side_effect=cli.ToolError("fingerprint sensor detail")
            ),
        ):
            with self.assertRaises(cli.ToolError) as context:
                cli.command_setup(args)
        message = str(context.exception)
        self.assertIn("could not read its status", message)
        self.assertIn("fingerprint sensor detail", message)
        self.assertNotIn("factory firmware was not detected", message.lower())

    def test_protocol_two_adds_this_mac_without_replacing_existing_mac(self):
        key = bytes(range(32))
        commands = []
        with (
            mock.patch.object(cli, "ensure_helper_environment", return_value=Path("/tmp/python")),
            mock.patch.object(cli, "pairing_account_for_port", return_value="DEVICE"),
            mock.patch.object(cli, "keychain_get", return_value=None),
            mock.patch.object(cli, "keychain_exists", return_value=False),
            mock.patch.object(cli, "hid_key_ids", return_value=({"aaaaaaaaaaaaaaaa"}, 8)),
            mock.patch.object(cli.secrets, "token_bytes", return_value=key),
            mock.patch.object(cli, "serial_command", side_effect=lambda _p, command, **_k: commands.append(command) or ["OK"]),
            mock.patch.object(cli, "prompt_password", return_value="password"),
            mock.patch.object(cli, "keychain_set"),
            mock.patch.object(cli, "install_helper"),
        ):
            cli.configure_hid_credentials(
                "/dev/cu.example", {"protocol": "2", "hid_key": "configured"}
            )
        self.assertIn(f"HID_KEY_ADD {cli.hid_key_id(key)} {key.hex()}", commands)
        self.assertFalse(any(command.startswith("HID_KEY ") for command in commands))

    def test_legacy_hid_firmware_never_rekeys_another_mac_implicitly(self):
        with (
            mock.patch.object(cli, "ensure_helper_environment", return_value=Path("/tmp/python")),
            mock.patch.object(cli, "pairing_account_for_port", return_value="DEVICE"),
            mock.patch.object(cli, "keychain_get", return_value=None),
            mock.patch.object(cli, "keychain_exists", return_value=False),
        ):
            with self.assertRaises(cli.ToolError) as context:
                cli.configure_hid_credentials(
                    "/dev/cu.example", {"protocol": "1", "hid_key": "configured"}
                )
        self.assertIn("preserves the existing key", str(context.exception))


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

    def test_add_computer_uses_current_mode(self):
        args = cli.parser().parse_args(["add-computer", "--port", "/dev/cu.example"])
        self.assertEqual(args.port, "/dev/cu.example")

    def test_add_computer_in_hid_mode_only_adds_hid_credentials(self):
        args = cli.parser().parse_args(["add-computer", "--port", "/dev/cu.example"])
        status = {
            "firmware": "unified", "mode": "hid", "sensor": "ok",
            "fingerprints": "1", "keys": "nvs", "protocol": "2",
        }
        with (
            mock.patch.object(cli, "require_macos"),
            mock.patch.object(cli, "choose_port", return_value="/dev/cu.example"),
            mock.patch.object(cli, "status_fields", return_value=status),
            mock.patch.object(cli, "unlock_configuration") as unlock,
            mock.patch.object(cli, "configure_hid_credentials") as configure_hid,
            mock.patch.object(cli, "pair_piv") as pair_piv,
        ):
            cli.command_add_computer(args)
        unlock.assert_called_once_with("/dev/cu.example")
        configure_hid.assert_called_once_with("/dev/cu.example", status)
        pair_piv.assert_not_called()

    def test_add_computer_in_piv_mode_only_pairs_piv(self):
        args = cli.parser().parse_args(["add-computer", "--port", "/dev/cu.example"])
        status = {
            "firmware": "unified", "mode": "piv", "sensor": "ok",
            "fingerprints": "1", "keys": "nvs", "protocol": "2",
        }
        with (
            mock.patch.object(cli, "require_macos"),
            mock.patch.object(cli, "choose_port", return_value="/dev/cu.example"),
            mock.patch.object(cli, "status_fields", return_value=status),
            mock.patch.object(cli, "unlock_configuration") as unlock,
            mock.patch.object(cli, "configure_hid_credentials") as configure_hid,
            mock.patch.object(cli, "pair_piv") as pair_piv,
        ):
            cli.command_add_computer(args)
        unlock.assert_not_called()
        configure_hid.assert_not_called()
        pair_piv.assert_called_once_with(port="/dev/cu.example")

    def test_computers_remove_accepts_host_id(self):
        args = cli.parser().parse_args(["computers", "remove", "0123456789abcdef"])
        self.assertEqual(args.action, "remove")
        self.assertEqual(args.host_id, "0123456789abcdef")

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
