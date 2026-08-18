import contextlib
import importlib.util
import hashlib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "tinytouch_helper", ROOT / "software" / "macos-helper" / "tinytouch_helper.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class ReadsExhausted(Exception):
    """Raised instead of blocking, so a test that never gets a reply fails fast."""


class FakeSerial:
    """Serial port replaying a fixed list of readline() results."""

    def __init__(self, reads):
        self.reads = list(reads)
        self.written = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def readline(self):
        if not self.reads:
            raise ReadsExhausted("serve_port consumed every read without replying")
        return self.reads.pop(0)

    def write(self, data):
        self.written.append(data)
        return len(data)

    def flush(self):
        pass


@contextlib.contextmanager
def helper_patched(fake, pairing_key, password):
    """Run serve_port() against a fake port, with no keychain or disk access."""
    with mock.patch.object(helper, "open_serial", return_value=fake), \
         mock.patch.object(helper, "keychain_get", return_value=password), \
         mock.patch.object(helper, "pairing_keychain_get", return_value=pairing_key), \
         mock.patch.object(helper, "load_state", return_value={"seen_nonces": []}), \
         mock.patch.object(helper, "save_state"):
        yield


class SerialFramingTests(unittest.TestCase):
    """The device's event stream survives being cut apart by a USB suspend."""

    def test_event_split_across_reads_is_reassembled(self):
        # readline() returns early when its timeout expires, so an event can straddle
        # two reads. The halves must not be verified separately.
        key = bytes(range(32))
        nonce = "03" * 16
        event_mac = helper.mac_hex(key, f"EV|{nonce}|1|1|1")
        line = f"EV {nonce} 1 1 1 {event_mac}\n".encode("ascii")
        split = len(line) - 20
        fake = FakeSerial([line[:split], line[split:]])

        with helper_patched(fake, key, b"hunter2"):
            helper.serve_port("/dev/cu.fake", once=True)

        self.assertEqual(len(fake.written), 1)
        self.assertEqual(fake.written[0].decode("ascii").split()[1], nonce)

    def test_event_glued_behind_a_truncated_one_is_recovered(self):
        # Observed shape: the truncated bytes flushed on resume with no newline before
        # the next event, so both arrived as a single line.
        key = bytes(range(32))
        nonce = "c51a6405ed821b8fe1b574ee20c6d05f"
        event_mac = helper.mac_hex(key, f"EV|{nonce}|5|1|1")
        glued = f"EV d5327a6c756644e27EV {nonce} 5 1 1 {event_mac}\n".encode("ascii")
        fake = FakeSerial([glued])

        with helper_patched(fake, key, b"hunter2"):
            helper.serve_port("/dev/cu.fake", once=True)

        self.assertEqual(len(fake.written), 1)
        self.assertEqual(fake.written[0].decode("ascii").split()[1], nonce)

    def test_resynchronize_leaves_clean_lines_alone(self):
        for line in ("EV aabb 1 1 1 ccdd", "PONG", "OK STATUS firmware=unified", ""):
            self.assertEqual(helper.resynchronize_event(line), line)


class HelperProtocolTests(unittest.TestCase):
    def test_authenticated_event_returns_decryptable_password(self):
        key = bytes(range(32))
        password = b"correct horse battery staple!"
        nonce = "01" * 16
        event_mac = helper.mac_hex(key, f"EV|{nonce}|7|1|1")
        response = helper.handle_event(
            f"EV {nonce} 7 1 1 {event_mac}",
            password,
            key,
            {"seen_nonces": []},
            persist_state=False,
        )
        self.assertIsNotNone(response)
        kind, got_nonce, iv_hex, ciphertext_hex, response_mac = response.split()
        self.assertEqual((kind, got_nonce), ("PW", nonce))
        self.assertEqual(
            response_mac,
            helper.mac_hex(key, f"PW|{nonce}|{iv_hex}|{ciphertext_hex}"),
        )
        plaintext = helper.aes_ctr_crypt(
            helper.session_key(key, nonce), bytes.fromhex(iv_hex), bytes.fromhex(ciphertext_hex)
        )
        self.assertEqual(plaintext, password)

    def test_commoncrypto_matches_nist_aes_256_ctr_vector(self):
        key = bytes.fromhex(
            "603deb1015ca71be2b73aef0857d7781"
            "1f352c073b6108d72d9810a30914dff4"
        )
        iv = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff")
        plaintext = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
        expected = bytes.fromhex("601ec313775789a5b7a7f504bbf3d228")
        self.assertEqual(helper.aes_ctr_crypt(key, iv, plaintext), expected)

    def test_replayed_nonce_is_rejected(self):
        key = bytes(range(32))
        nonce = "02" * 16
        event_mac = helper.mac_hex(key, f"EV|{nonce}|1|1|1")
        state = {"seen_nonces": [nonce]}
        response = helper.handle_event(
            f"EV {nonce} 1 1 1 {event_mac}",
            b"password",
            key,
            state,
            persist_state=False,
        )
        self.assertIsNone(response)

    def test_v2_event_selects_this_computers_independent_key(self):
        key = bytes(range(32))
        password = b"a different Mac password"
        nonce = "03" * 16
        key_id = hashlib.sha256(key).hexdigest()[:16]
        event_mac = helper.mac_hex(key, f"EV2|{key_id}|{nonce}|8|1|77")
        response = helper.handle_event(
            f"EV2 {nonce} 8 1 77 deadbeefdeadbeef:{'00' * 32} {key_id}:{event_mac}",
            password,
            key,
            {"seen_nonces": []},
            persist_state=False,
        )
        self.assertIsNotNone(response)
        kind, got_id, got_nonce, iv_hex, ciphertext_hex, response_mac = response.split()
        self.assertEqual((kind, got_id, got_nonce), ("PW2", key_id, nonce))
        self.assertEqual(
            response_mac,
            helper.mac_hex(key, f"PW2|{key_id}|{nonce}|{iv_hex}|{ciphertext_hex}"),
        )
        plaintext = helper.aes_ctr_crypt(
            helper.session_key(key, nonce), bytes.fromhex(iv_hex), bytes.fromhex(ciphertext_hex)
        )
        self.assertEqual(plaintext, password)

    def test_v2_event_for_another_computer_is_ignored(self):
        response = helper.handle_event(
            f"EV2 {'04' * 16} 1 1 1 deadbeefdeadbeef:{'00' * 32}",
            b"password",
            bytes(range(32)),
            {"seen_nonces": []},
            persist_state=False,
        )
        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
