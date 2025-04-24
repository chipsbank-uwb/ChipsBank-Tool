# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs
import datetime

hiddenimports = collect_submodules('kiwisolver') + ['pkg_resources.extern']
binaries = collect_dynamic_libs('kiwisolver')

# 获取当前时间
current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

#Alpha：表示软件处于早期开发阶段，功能可能不完整，存在较多的错误和不稳定性。
#Beta：表示软件已经完成了主要功能的开发，但仍可能存在一些错误，需要进一步测试和修复。
#Release：表示软件的正式发布版本，经过了充分的测试和修复，适合生产环境使用。
version = "V1.0.0 Release"

# 写入文件
with open("build_info.txt", "w") as f:
    f.write(f"Build Time: {current_time}\n")
    f.write(f"Version: {version}\n")

a = Analysis(
    ['ChipsBankUWBTool.py'],
    pathex=['.'],
    binaries=binaries,
    datas=[
        ('icon', 'icon'),
        ('configs', 'configs'),
        ('build_info.txt', '.')  # 添加生成的文件到 datas 中
    ],
    hiddenimports=hiddenimports,
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    distpath='ChipsBankUWBTool'
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ChipsBankUWBTool',
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
    icon='logo.ico'
    dist_subdir='ChipsBankUWBTool'
)

