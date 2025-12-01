# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gfl2_scanner.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('easyocr_models', 'easyocr_models'),
        ('config.json', '.'),
    ],
    hiddenimports=[
        'easyocr',
        'torch',
        'cv2',
        'pandas',
        'PIL',
        'numpy',
        'keyboard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GFL2_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI-only mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you create one
)
