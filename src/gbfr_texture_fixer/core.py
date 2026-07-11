from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable


class FixerError(RuntimeError):
    """An expected error that can be reported without a traceback."""


@dataclass(frozen=True)
class ToolPaths:
    directory: Path
    data_tools: Path
    flatc: Path
    schema: Path

    @classmethod
    def from_directory(cls, directory: Path) -> "ToolPaths":
        directory = directory.resolve()
        paths = cls(
            directory=directory,
            data_tools=directory / "GBFRDataTools.exe",
            flatc=directory / "flatc.exe",
            schema=directory / "MMat_ModelMaterial.fbs",
        )
        missing = [str(path) for path in (paths.data_tools, paths.flatc, paths.schema) if not path.is_file()]
        if missing:
            raise FixerError("Required tool files are missing: " + ", ".join(missing))
        return paths


@dataclass(frozen=True)
class ModInfo:
    root: Path
    name: str
    textures: frozenset[str]
    mmat_files: tuple[Path, ...]
    data_root: Path


@dataclass
class CacheEntry:
    mmat_path: Path
    json_path: Path
    hit: bool


@dataclass
class ModResult:
    name: str
    root: Path
    repaired_files: int = 0
    repaired_materials: int = 0
    skipped_files: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    backups: list[Path] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunSummary:
    discovered_mods: int = 0
    results: list[ModResult] = field(default_factory=list)

    @property
    def repaired_mods(self) -> int:
        return sum(1 for item in self.results if item.repaired_files and not item.error)

    @property
    def failed_mods(self) -> int:
        return sum(1 for item in self.results if item.error)

    @property
    def repaired_files(self) -> int:
        return sum(item.repaired_files for item in self.results)

    @property
    def repaired_materials(self) -> int:
        return sum(item.repaired_materials for item in self.results)

    @property
    def skipped_files(self) -> int:
        return sum(item.skipped_files for item in self.results)

    @property
    def cache_hits(self) -> int:
        return sum(item.cache_hits for item in self.results)

    @property
    def cache_misses(self) -> int:
        return sum(item.cache_misses for item in self.results)


def _casefold_suffix(path: Path, suffix: str) -> bool:
    return path.name.casefold().endswith(suffix.casefold())


def discover_mods(base_dir: Path) -> list[ModInfo]:
    """Find standard Reloaded-II mods below *base_dir*."""
    mods: list[ModInfo] = []
    seen: set[Path] = set()
    for config in base_dir.rglob("ModConfig.json"):
        if any(part.casefold() == ".gbfr_texture_fixer" for part in config.parts):
            continue
        root = config.parent.resolve()
        if root in seen:
            continue
        seen.add(root)
        data_root = root / "GBFR" / "data"
        texture_root = data_root / "texture"
        model_root = data_root / "model"
        if not texture_root.is_dir() or not model_root.is_dir():
            continue
        textures = frozenset(
            path.stem.casefold()
            for path in texture_root.rglob("*")
            if path.is_file() and _casefold_suffix(path, ".texture")
        )
        mmat_files = tuple(
            sorted(
                (
                    path
                    for path in model_root.rglob("*")
                    if path.is_file()
                    and _casefold_suffix(path, ".mmat")
                    and path.parent.name.casefold() == "vars"
                ),
                key=lambda path: str(path).casefold(),
            )
        )
        if not textures or not mmat_files:
            continue
        name = root.name
        try:
            payload = json.loads(config.read_text(encoding="utf-8-sig"))
            name = str(payload.get("ModName") or payload.get("ModId") or name)
        except (OSError, ValueError, TypeError):
            pass
        mods.append(ModInfo(root, name, textures, mmat_files, data_root))
    return sorted(mods, key=lambda item: str(item.root).casefold())


def remove_matching_granite_params(document: dict[str, Any], textures: Iterable[str]) -> int:
    """Remove granite metadata from every material using one of *textures*."""
    wanted = {name.casefold() for name in textures}
    removed = 0
    materials = document.get("materials")
    if not isinstance(materials, list):
        raise FixerError("The MMAT JSON does not contain a materials array")
    for material in materials:
        if not isinstance(material, dict) or "granite_params" not in material:
            continue
        texture_maps = material.get("texture_maps", [])
        if not isinstance(texture_maps, list):
            continue
        matched = any(
            isinstance(texture_map, dict)
            and isinstance(texture_map.get("texture_name"), str)
            and texture_map["texture_name"].casefold() in wanted
            for texture_map in texture_maps
        )
        if matched:
            del material["granite_params"]
            removed += 1
    return removed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_cache_key(game_dir: Path, tools: ToolPaths) -> str:
    data_index = game_dir / "data.i"
    stat = data_index.stat()
    identity = {
        "game_dir": os.path.normcase(str(game_dir.resolve())),
        "data_i_size": stat.st_size,
        "data_i_mtime_ns": stat.st_mtime_ns,
        "schema_sha256": _sha256_file(tools.schema),
        "data_tools_sha256": _sha256_file(tools.data_tools),
        "flatc_sha256": _sha256_file(tools.flatc),
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


CommandRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def run_command(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "no error output").strip()
        raise FixerError(f"External tool failed with exit code {completed.returncode}: {details}")
    return completed


class OriginalMmatCache:
    def __init__(
        self,
        cache_root: Path,
        work_root: Path,
        game_dir: Path,
        tools: ToolPaths,
        runner: CommandRunner = run_command,
    ) -> None:
        self.game_dir = game_dir.resolve()
        self.data_index = self.game_dir / "data.i"
        if not self.data_index.is_file():
            raise FixerError(f"The game directory does not contain data.i: {self.game_dir}")
        self.tools = tools
        self.runner = runner
        self.work_root = work_root
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root / build_cache_key(self.game_dir, tools)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, archive_path: str) -> CacheEntry:
        normalized = Path(*archive_path.replace("\\", "/").split("/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise FixerError(f"Invalid game archive path: {archive_path}")
        cached_mmat = self.cache_dir / normalized
        cached_json = cached_mmat.with_suffix(".json")
        if cached_mmat.is_file() and cached_json.is_file():
            try:
                json.loads(cached_json.read_text(encoding="utf-8"))
                return CacheEntry(cached_mmat, cached_json, True)
            except (OSError, ValueError):
                pass

        with tempfile.TemporaryDirectory(prefix="extract_", dir=self.work_root) as temporary:
            extract_root = Path(temporary)
            extraction = self.runner(
                [
                    str(self.tools.data_tools),
                    "extract",
                    "-i",
                    str(self.data_index),
                    "-f",
                    normalized.as_posix(),
                    "-o",
                    str(extract_root),
                ],
                self.tools.directory,
            )
            extracted_mmat = extract_root / normalized
            if not extracted_mmat.is_file():
                tool_output = ""
                if isinstance(extraction, subprocess.CompletedProcess):
                    tool_output = (extraction.stderr or extraction.stdout or "").strip()
                detail = f"; tool output: {tool_output}" if tool_output else ""
                raise FixerError(f"Failed to extract the original game file: {normalized.as_posix()}{detail}")
            self.runner(
                [
                    str(self.tools.flatc),
                    "--json",
                    "--strict-json",
                    "-o",
                    str(extracted_mmat.parent),
                    str(self.tools.schema),
                    "--",
                    str(extracted_mmat),
                    "--raw-binary",
                ],
                self.tools.directory,
            )
            extracted_json = extracted_mmat.with_suffix(".json")
            if not extracted_json.is_file():
                raise FixerError(f"Failed to convert the original MMAT to JSON: {normalized.as_posix()}")
            try:
                json.loads(extracted_json.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise FixerError(f"Invalid original MMAT JSON: {normalized.as_posix()} ({error})") from error
            cached_mmat.parent.mkdir(parents=True, exist_ok=True)
            _atomic_copy(extracted_mmat, cached_mmat)
            _atomic_copy(extracted_json, cached_json)
        return CacheEntry(cached_mmat, cached_json, False)


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def _compile_json(document: dict[str, Any], output_dir: Path, stem: str, tools: ToolPaths, runner: CommandRunner) -> Path:
    input_dir = output_dir / "json"
    binary_dir = output_dir / "binary"
    input_dir.mkdir(parents=True, exist_ok=True)
    binary_dir.mkdir(parents=True, exist_ok=True)
    json_path = input_dir / f"{stem}.json"
    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runner(
        [str(tools.flatc), "-b", "-o", str(binary_dir), str(tools.schema), str(json_path)],
        tools.directory,
    )
    mmat_path = binary_dir / f"{stem}.mmat"
    if not mmat_path.is_file() or mmat_path.stat().st_size == 0:
        raise FixerError(f"Failed to compile JSON to MMAT: {json_path}")
    return mmat_path


def _unique_backup_path(target: Path, timestamp: str) -> Path:
    candidate = target.with_name(f"{target.name}.bak.{timestamp}")
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.name}.bak.{timestamp}_{counter}")
        counter += 1
    return candidate


def _commit_replacements(replacements: list[tuple[Path, Path]], timestamp: str) -> list[Path]:
    backups: list[tuple[Path, Path]] = []
    for target, _ in replacements:
        backup = _unique_backup_path(target, timestamp)
        try:
            shutil.copy2(target, backup)
        except OSError as error:
            raise FixerError(f"Failed to back up {target}: {error}") from error
        backups.append((target, backup))

    replaced: list[tuple[Path, Path]] = []
    try:
        for (target, generated), (_, backup) in zip(replacements, backups):
            os.replace(generated, target)
            replaced.append((target, backup))
    except OSError as error:
        rollback_errors: list[str] = []
        for target, backup in reversed(replaced):
            try:
                shutil.copy2(backup, target)
            except OSError as rollback_error:
                rollback_errors.append(f"{target}: {rollback_error}")
        message = f"Failed to replace MMAT; rollback attempted: {error}"
        if rollback_errors:
            message += "; rollback failures: " + "; ".join(rollback_errors)
        raise FixerError(message) from error
    return [backup for _, backup in backups]


def process_mod(
    mod: ModInfo,
    cache: OriginalMmatCache,
    tools: ToolPaths,
    work_root: Path,
    runner: CommandRunner = run_command,
    now: Callable[[], datetime] = datetime.now,
) -> ModResult:
    result = ModResult(mod.name, mod.root)
    replacements: list[tuple[Path, Path]] = []
    work_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="mod_", dir=work_root) as temporary:
            stage_root = Path(temporary)
            for index, target in enumerate(mod.mmat_files):
                archive_path = target.relative_to(mod.data_root).as_posix()
                entry = cache.get(archive_path)
                if entry.hit:
                    result.cache_hits += 1
                else:
                    result.cache_misses += 1
                try:
                    original = json.loads(entry.json_path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    raise FixerError(f"Failed to read cached JSON {entry.json_path}: {error}") from error
                modified = copy.deepcopy(original)
                removed = remove_matching_granite_params(modified, mod.textures)
                if removed == 0:
                    result.skipped_files += 1
                    continue
                generated = _compile_json(modified, stage_root / str(index), target.stem, tools, runner)
                replacements.append((target, generated))
                result.repaired_materials += removed

            if replacements:
                timestamp = now().strftime("%Y%m%d_%H%M%S_%f")
                result.backups = _commit_replacements(replacements, timestamp)
                result.repaired_files = len(replacements)
    except (FixerError, OSError, ValueError) as error:
        result.error = str(error)
        result.repaired_files = 0
        result.repaired_materials = 0
    return result


def run_fixer(base_dir: Path, game_dir: Path, tools: ToolPaths, reporter: Callable[[str], None] | None = None) -> RunSummary:
    reporter = reporter or (lambda _: None)
    app_data = base_dir / ".gbfr_texture_fixer"
    cache = OriginalMmatCache(app_data / "cache", app_data / "work", game_dir, tools)
    mods = discover_mods(base_dir)
    summary = RunSummary(discovered_mods=len(mods))
    for number, mod in enumerate(mods, start=1):
        reporter(f"[{number}/{len(mods)}] Processing: {mod.name}")
        result = process_mod(mod, cache, tools, app_data / "work")
        summary.results.append(result)
        if result.error:
            reporter(f"  Failed: {result.error}")
        elif result.repaired_files:
            reporter(f"  Done: repaired {result.repaired_files} MMAT file(s), removed {result.repaired_materials} granite_params field(s)")
        else:
            reporter("  Skipped: no materials need repair")
    return summary
