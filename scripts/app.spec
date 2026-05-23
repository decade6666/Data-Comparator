# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# 获取项目根目录，假设spec文件在 scripts 目录下，项目根目录是 scripts 的上一级
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.dirname(spec_dir)

# 定义数据文件和图标路径，使用项目根目录作为基准
# 优先使用 src 目录下的 app_icon.ico，兼容旧路径 assets/icons/app_icon.ico
icon_path_candidates = [
    os.path.join(project_root, 'src', 'app_icon.ico'),
    os.path.join(project_root, 'src', 'assets', 'icons', 'app_icon.ico'),
]
icon_path = next((p for p in icon_path_candidates if os.path.exists(p)), None)
parameters_path = os.path.join(project_root, 'src', 'config', 'parameters.json')
version_file_path = os.path.join(project_root, 'scripts', 'version_info.txt')

# 数据文件列表
datas = []
if os.path.exists(parameters_path):
    datas.append((parameters_path, '.'))

# 添加图标文件到数据文件，保持其在打包后的相对路径
if icon_path and os.path.exists(icon_path):
    # 统一打包到 assets/icons 下，set_window_icon 会做两种路径兼容
    datas.append((icon_path, 'assets/icons'))

block_cipher = None

a = Analysis(
    [os.path.join(project_root, 'src', 'main.py')],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pandas',
        'numpy',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.utils.dataframe',
        'openpyxl.workbook',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.colorchooser',
        'threading',
        'queue',
        'json',
        'datetime',
        'os',
        'sys',
        'warnings',
        'concurrent.futures',
        'time',
        'gc',
        're',
        'tempfile',
        'xml.etree.ElementTree',
        'zipfile',
        'shutil',
        'appdirs',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'tornado',
        'zmq',
        'sqlite3',
        'test',
        'unittest',
        'xmlrpc',
        'http.server',
        'wsgiref',
        'distutils',
        'email',
        'html',
        'urllib3',
        'requests',
        'setuptools',
        'pkg_resources'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='比对程序',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if icon_path and os.path.exists(icon_path) else None,
    version=version_file_path if os.path.exists(version_file_path) else None,
) 