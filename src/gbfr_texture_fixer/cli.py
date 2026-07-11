from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .core import FixerError, RunSummary, ToolPaths, run_fixer


CONFIG_NAME = "gbfr_texture_fixer.json"


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir(base_dir: Path) -> Path:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir) / "libs"
    return base_dir / "libs"


def load_config(config_path: Path) -> Path | None:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
        game_dir = Path(payload["game_dir"]).expanduser().resolve()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return game_dir if (game_dir / "data.i").is_file() else None


def save_config(config_path: Path, game_dir: Path) -> None:
    payload = {"game_dir": str(game_dir.resolve())}
    temporary = config_path.with_name(config_path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, config_path)


def choose_game_dir() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError as error:
        raise FixerError("The tkinter directory picker is not available on this system") from error

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        while True:
            selected = filedialog.askdirectory(
                parent=root,
                title="Select the Granblue Fantasy: Relink installation directory",
                mustexist=True,
            )
            if not selected:
                return None
            game_dir = Path(selected).resolve()
            if (game_dir / "data.i").is_file():
                return game_dir
            messagebox.showerror("Invalid directory", "The selected directory does not contain data.i. Select the game installation directory.", parent=root)
    finally:
        root.destroy()


def print_summary(summary: RunSummary) -> None:
    print("\n========== Processing complete ==========")
    print(f"Mods found: {summary.discovered_mods}")
    print(f"Mods repaired: {summary.repaired_mods}")
    print(f"Mods failed: {summary.failed_mods}")
    print(f"MMAT files replaced: {summary.repaired_files}")
    print(f"granite_params fields removed: {summary.repaired_materials}")
    print(f"MMAT files unchanged: {summary.skipped_files}")
    print(f"Cache hits/misses: {summary.cache_hits}/{summary.cache_misses}")
    backups = [path for result in summary.results for path in result.backups]
    if backups:
        print("\nBackup files:")
        for path in backups:
            print(f"  {path}")
    failures = [result for result in summary.results if result.error]
    if failures:
        print("\nFailure details:")
        for result in failures:
            print(f"  {result.name}: {result.error}")


def pause() -> None:
    if os.environ.get("GBFR_TEXTURE_FIXER_NO_PAUSE") == "1":
        return
    try:
        input("\nPress Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> int:
    print("GBFR Mod Texture Fixer")
    print("Original game files are read only and will not be modified.\n")
    base_dir = application_dir()
    config_path = base_dir / CONFIG_NAME
    try:
        tools = ToolPaths.from_directory(resource_dir(base_dir))
        game_dir = load_config(config_path)
        if game_dir is None:
            print("First run or saved game directory is invalid. Select the game installation directory in the dialog.")
            game_dir = choose_game_dir()
            if game_dir is None:
                print("Selection cancelled. No files were modified.")
                return 1
            save_config(config_path, game_dir)
            print(f"Game directory saved: {game_dir}\n")
        else:
            print(f"Game directory: {game_dir}\n")
        summary = run_fixer(base_dir, game_dir, tools, print)
        print_summary(summary)
        return 2 if summary.failed_mods else 0
    except (FixerError, OSError) as error:
        print(f"\nError: {error}")
        return 2
    finally:
        pause()
