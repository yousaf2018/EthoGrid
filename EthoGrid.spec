# EthoGrid.spec

import os

# Get the directory where this .spec file is located
HERE = os.path.abspath(os.path.dirname(__file__))
APP_FOLDER = os.path.join(HERE, 'EthoGrid_App')

block_cipher = None

a = Analysis(
    [os.path.join(APP_FOLDER, 'main.py')],
    pathex=[HERE],
    binaries=[],
    datas=[(os.path.join(APP_FOLDER, 'images'), 'images')],
    hiddenimports=[
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs',
        'openpyxl'
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
    name='EthoGrid',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(APP_FOLDER, 'images', 'logo.ico')
)