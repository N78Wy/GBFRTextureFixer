from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gbfr_texture_fixer.cli import load_config, save_config  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_round_trip_and_invalid_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "Granblue Fantasy Relink"
            game.mkdir()
            (game / "data.i").write_bytes(b"index")
            config = root / "gbfr_texture_fixer.json"

            save_config(config, game)

            self.assertEqual(load_config(config), game.resolve())
            self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["game_dir"], str(game.resolve()))
            (game / "data.i").unlink()
            self.assertIsNone(load_config(config))


if __name__ == "__main__":
    unittest.main()

