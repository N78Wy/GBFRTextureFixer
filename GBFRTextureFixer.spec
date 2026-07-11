# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_dir = Path(SPECPATH)
libs_dir = project_dir / "libs"

datas = [
    (str(libs_dir / "GBFRDataTools.exe"), "libs"),
    (str(libs_dir / "flatc.exe"), "libs"),
    (str(libs_dir / "MMat_ModelMaterial.fbs"), "libs"),
    (str(libs_dir / "e_sqlite3.dll"), "libs"),
    (str(libs_dir / "filelist.txt"), "libs"),
    (str(libs_dir / "unknown_hash_to_folder.txt"), "libs"),
    (str(project_dir / "packaging" / "runtime-libs" / "config.txt"), "libs"),
]

a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["tkinter", "tkinter.filedialog", "tkinter.messagebox"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GBFRTextureFixer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
