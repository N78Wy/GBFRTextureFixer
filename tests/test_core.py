from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gbfr_texture_fixer.core import (  # noqa: E402
    CacheEntry,
    FixerError,
    ModInfo,
    OriginalMmatCache,
    ToolPaths,
    discover_mods,
    process_mod,
    remove_matching_granite_params,
)


class GraniteTests(unittest.TestCase):
    def test_removes_only_matching_materials(self) -> None:
        document = {
            "materials": [
                {
                    "texture_maps": [{"texture_name": "NP0000_SKIN_LOD0_MSK2"}],
                    "granite_params": {"page_file": ["old"]},
                    "shader_type": 6,
                },
                {
                    "texture_maps": [{"texture_name": "unrelated"}],
                    "granite_params": {"page_file": ["keep"]},
                },
                {"texture_maps": [{"texture_name": "np0000_skin_lod0_msk2"}]},
            ]
        }

        removed = remove_matching_granite_params(document, {"np0000_skin_lod0_msk2"})

        self.assertEqual(removed, 1)
        self.assertNotIn("granite_params", document["materials"][0])
        self.assertEqual(document["materials"][0]["shader_type"], 6)
        self.assertIn("granite_params", document["materials"][1])

    def test_requires_materials_array(self) -> None:
        with self.assertRaises(FixerError):
            remove_matching_granite_params({}, set())


class DiscoveryTests(unittest.TestCase):
    def test_discovers_standard_mod_and_deduplicates_texture_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            mod = base / "nested" / "example"
            (mod / "GBFR/data/texture/2k").mkdir(parents=True)
            (mod / "GBFR/data/texture/4k").mkdir(parents=True)
            (mod / "GBFR/data/model/pl/pl0400/vars").mkdir(parents=True)
            (mod / "ModConfig.json").write_text('{"ModName":"Example"}', encoding="utf-8")
            (mod / "GBFR/data/texture/2k/body.texture").write_bytes(b"2k")
            (mod / "GBFR/data/texture/4k/BODY.texture").write_bytes(b"4k")
            (mod / "GBFR/data/model/pl/pl0400/vars/10.mmat").write_bytes(b"mmat")

            mods = discover_mods(base)

            self.assertEqual(len(mods), 1)
            self.assertEqual(mods[0].name, "Example")
            self.assertEqual(mods[0].textures, frozenset({"body"}))
            self.assertEqual(mods[0].mmat_files[0].name, "10.mmat")


def make_tools(root: Path) -> ToolPaths:
    root.mkdir(parents=True, exist_ok=True)
    for name in ("GBFRDataTools.exe", "flatc.exe", "MMat_ModelMaterial.fbs"):
        (root / name).write_bytes(name.encode("ascii"))
    return ToolPaths.from_directory(root)


class CacheTests(unittest.TestCase):
    def test_extracts_once_then_reuses_strict_json_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = make_tools(root / "tools")
            game = root / "game"
            game.mkdir()
            (game / "data.i").write_bytes(b"index")
            calls: list[list[str]] = []

            def runner(arguments: list[str], cwd: Path):
                calls.append(arguments)
                if "extract" in arguments:
                    output = Path(arguments[arguments.index("-o") + 1])
                    archive = Path(*arguments[arguments.index("-f") + 1].split("/"))
                    path = output / archive
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"original")
                elif "--json" in arguments:
                    mmat = Path(arguments[arguments.index("--") + 1])
                    mmat.with_suffix(".json").write_text('{"materials":[]}', encoding="utf-8")
                return None

            cache = OriginalMmatCache(root / "cache", root / "work", game, tools, runner)
            first = cache.get("model/np/np0000/vars/0.mmat")
            second = cache.get("model/np/np0000/vars/0.mmat")

            self.assertFalse(first.hit)
            self.assertTrue(second.hit)
            self.assertEqual(len(calls), 2)
            self.assertTrue(second.json_path.is_file())


class FakeCache:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path

    def get(self, archive_path: str) -> CacheEntry:
        return CacheEntry(self.json_path.with_suffix(".mmat"), self.json_path, True)


class ProcessModTests(unittest.TestCase):
    def test_stages_backs_up_and_replaces_existing_mmat(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = make_tools(root / "tools")
            data_root = root / "mod/GBFR/data"
            target = data_root / "model/np/np0000/vars/0.mmat"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old mod")
            source_json = root / "original.json"
            source_json.write_text(
                json.dumps(
                    {
                        "materials": [
                            {
                                "texture_maps": [{"texture_name": "body"}],
                                "granite_params": {"page_file": ["vanilla"]},
                                "shader_type": 6,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            mod = ModInfo(root / "mod", "Example", frozenset({"BODY"}), (target,), data_root)

            def runner(arguments: list[str], cwd: Path):
                if "-b" in arguments:
                    output = Path(arguments[arguments.index("-o") + 1])
                    input_json = Path(arguments[-1])
                    document = json.loads(input_json.read_text(encoding="utf-8"))
                    self.assertNotIn("granite_params", document["materials"][0])
                    output.mkdir(parents=True, exist_ok=True)
                    (output / f"{input_json.stem}.mmat").write_bytes(b"fixed")
                return None

            result = process_mod(
                mod,
                FakeCache(source_json),
                tools,
                root / "work",
                runner,
                now=lambda: datetime(2026, 7, 11, 16, 30, 0, 123456),
            )

            self.assertIsNone(result.error)
            self.assertEqual(result.repaired_files, 1)
            self.assertEqual(result.repaired_materials, 1)
            self.assertEqual(target.read_bytes(), b"fixed")
            self.assertEqual(len(result.backups), 1)
            self.assertEqual(result.backups[0].read_bytes(), b"old mod")
            self.assertIn("20260711_163000_123456", result.backups[0].name)

    def test_compile_failure_leaves_mod_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = make_tools(root / "tools")
            data_root = root / "mod/GBFR/data"
            target = data_root / "model/np/np0000/vars/0.mmat"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old mod")
            source_json = root / "original.json"
            source_json.write_text(
                '{"materials":[{"texture_maps":[{"texture_name":"body"}],"granite_params":{}}]}',
                encoding="utf-8",
            )
            mod = ModInfo(root / "mod", "Example", frozenset({"body"}), (target,), data_root)

            def runner(arguments: list[str], cwd: Path):
                raise FixerError("compile failed")

            result = process_mod(mod, FakeCache(source_json), tools, root / "work", runner)

            self.assertEqual(result.error, "compile failed")
            self.assertEqual(target.read_bytes(), b"old mod")
            self.assertEqual(list(target.parent.glob("*.bak.*")), [])


if __name__ == "__main__":
    unittest.main()

