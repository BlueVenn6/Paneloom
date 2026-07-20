from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


ROOT = Path(SPECPATH).resolve().parent
GENERATED = ROOT / "packaging" / "generated"

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "desktop" / "resources"), "desktop/resources"),
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "THIRD_PARTY_LICENSES.md"), "."),
    (str(ROOT / "sbom"), "sbom"),
    (str(ROOT / "packaging" / "licenses"), "packaging/licenses"),
    (str(GENERATED / "build-info.json"), "."),
]
datas += collect_data_files("webview")

hiddenimports = [
    "bottle",
    "clr",
    "pythonnet",
    "proxy_tools",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

a = Analysis(
    [str(ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Paneloom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "desktop" / "resources" / "paneloom.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Paneloom",
)
