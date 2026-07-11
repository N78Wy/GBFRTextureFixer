# GBFR Mod Texture Fixer

[Chinese (Simplified)](README_zh-CN.md)

Repairs outdated MMAT texture-streaming metadata in *Granblue Fantasy: Relink* mods after game updates. The tool reads the game's original `data.i` archive and modifies only the mod files it discovers.

> [!WARNING]
> This script can fix only simple texture errors. It processes every supported mod file under the directory where it is run, so carefully limit the contents and scope of that directory. Back up your mods before running it.

## Usage

1. Back up the mods you intend to process.
2. Place `GBFRTextureFixer.exe` in a directory containing one or more mod folders. Keep unrelated mods and files outside this directory to limit the repair scope.
3. Run the executable. On first launch, select the game installation directory containing `data.i`.
4. The tool automatically scans all standard mods containing `ModConfig.json` and prints a summary when finished.
5. A timestamped backup is created next to every overwritten `.mmat`, for example `0.mmat.bak.20260711_163000_123456`.

A standard mod must contain all of the following:

- `ModConfig.json`
- `GBFR/data/texture/**/*.texture`
- `GBFR/data/model/**/vars/*.mmat`

The selected game directory is stored in `gbfr_texture_fixer.json` next to the executable. Delete this file to choose a different directory on the next run. Original MMAT files are cached in `.gbfr_texture_fixer/cache`; the cache is refreshed automatically when the game's `data.i` or a bundled conversion tool changes.

## Repair behavior

For each `.mmat` path already present in a mod, the tool extracts the original file at the same path from the game archive and converts it to strict JSON. If a material's `texture_maps[].texture_name` matches the filename of a `.texture` supplied by the mod (case-insensitive and without the extension), the tool removes that material's `granite_params`, recompiles the file, and overwrites the mod's existing `.mmat`.

The tool does not add MMAT variants that are absent from the mod. Files with no matching textures are not overwritten.

## Development and testing

Python 3.10 or newer is required. The test suite has no third-party dependencies:

```powershell
py -3 -m unittest discover -s tests -v
```

Run directly in a development environment:

```powershell
py -3 main.py
```

## Building a single-file executable

Install the build dependencies and run the build script:

```powershell
py -3 -m pip install -r requirements-dev.txt
.\build.ps1
```

The resulting executable is written to `dist/GBFRTextureFixer.exe`. It bundles `GBFRDataTools`, `flatc`, the schema, DLL, file list, and hash-to-directory mapping. End users do not need Python or an internet connection.

## Acknowledgements

Special thanks to:

- [Nenkai/GBFRDataTools](https://github.com/Nenkai/GBFRDataTools)
- [google/flatbuffers](https://github.com/google/flatbuffers)

## License

This project is licensed under the [MIT License](LICENSE).
