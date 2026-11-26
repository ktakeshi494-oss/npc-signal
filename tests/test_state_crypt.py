"""Local test: encrypt/decrypt a throwaway SQLite file. Does not use the live database."""
import hashlib, os, sqlite3, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "state_crypt.sh"

class StateCrypt(unittest.TestCase):
    def test_roundtrip(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "a.sqlite"
            enc = Path(d) / "a.enc"
            out = Path(d) / "b.sqlite"
            con = sqlite3.connect(raw)
            con.execute("CREATE TABLE t(x INT)"); con.execute("INSERT INTO t VALUES (42)"); con.commit(); con.close()
            env = os.environ.copy()
            env["STATE_KEY"] = "test-key-not-for-production-1"
            subprocess.check_call(["bash", str(SCRIPT), "encrypt", str(raw), str(enc)], env=env)
            self.assertGreater(enc.stat().st_size, 0)
            # ciphertext must not contain the plaintext value as raw bytes
            self.assertNotIn(b"42", enc.read_bytes()[:16] and enc.read_bytes() or b"")
            subprocess.check_call(["bash", str(SCRIPT), "decrypt", str(enc), str(out)], env=env)
            self.assertEqual(
                hashlib.sha256(raw.read_bytes()).hexdigest(),
                hashlib.sha256(out.read_bytes()).hexdigest(),
            )
            con = sqlite3.connect(out)
            self.assertEqual(con.execute("SELECT x FROM t").fetchone()[0], 42)
            con.close()
            # wrong key must fail
            env["STATE_KEY"] = "wrong-key-not-the-same-001"
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.check_call(["bash", str(SCRIPT), "decrypt", str(enc), str(Path(d)/"fail.sqlite")], env=env)

    def test_rejects_short_key(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "a.sqlite"; raw.write_bytes(b"x")
            env = os.environ.copy(); env["STATE_KEY"] = "short"
            r = subprocess.run(["bash", str(SCRIPT), "encrypt", str(raw), str(Path(d)/"a.enc")], env=env)
            self.assertNotEqual(r.returncode, 0)

if __name__ == "__main__":
    unittest.main()
