# GBFR Mod 纹理修复工具

[English](README.md)

用于修复《Granblue Fantasy: Relink》更新后旧 mod 的 MMAT 纹理流送配置。工具只读取游戏原版 `data.i`，只会修改扫描到的 mod 文件。

> [!WARNING]
> 该脚本只能修复简单的贴图错误。脚本会处理其所在目录下全部受支持的 mod 文件，请谨慎控制该目录的内容和修复范围，并在修复前备份 mod。

## 使用方法

1. 备份需要处理的 mod。
2. 将 `GBFRTextureFixer.exe` 放到包含一个或多个 mod 文件夹的目录。为控制修复范围，请不要在该目录中放置无关的 mod 或文件。
3. 双击运行。首次启动会弹出目录选择窗口，请选择包含 `data.i` 的游戏安装目录。
4. 工具会自动扫描所有带 `ModConfig.json` 的标准 mod，完成后在控制台显示结果。
5. 每个被覆盖的 `.mmat` 旁都会生成独立的时间戳备份，例如 `0.mmat.bak.20260711_163000_123456`。

标准 mod 需要同时包含：

- `ModConfig.json`
- `GBFR/data/texture/**/*.texture`
- `GBFR/data/model/**/vars/*.mmat`

游戏目录记录在 exe 同目录的 `gbfr_texture_fixer.json`。需要重新选择时，删除该配置文件后再次运行即可。原版 MMAT 缓存在 `.gbfr_texture_fixer/cache`；游戏 `data.i` 或内置转换工具发生变化时会自动使用新的缓存。

## 修复规则

工具以 mod 中已有的 `.mmat` 路径为准，从游戏中提取同路径的原版文件，并将其转换为严格 JSON。如果某个 material 的 `texture_maps[].texture_name` 与 mod 自带 `.texture` 文件名（不含扩展名、忽略大小写）一致，工具会删除该 material 的 `granite_params`，然后重新编译并覆盖 mod 原有 `.mmat`。

工具不会向 mod 补充原本不存在的 MMAT 变体。没有任何纹理命中的文件不会被覆盖。

## 开发与测试

要求 Python 3.10 或更高版本。运行测试不需要第三方依赖：

```powershell
py -3 -m unittest discover -s tests -v
```

开发环境直接运行：

```powershell
py -3 main.py
```

## 构建单文件 EXE

安装构建依赖并执行构建脚本：

```powershell
py -3 -m pip install -r requirements-dev.txt
.\build.ps1
```

产物位于 `dist/GBFRTextureFixer.exe`，其中已嵌入 `GBFRDataTools`、`flatc`、schema、DLL、filelist 和哈希目录映射文件。目标用户不需要安装 Python，也不需要联网下载依赖。

## 鸣谢

特别感谢：

- [Nenkai/GBFRDataTools](https://github.com/Nenkai/GBFRDataTools)
- [google/flatbuffers](https://github.com/google/flatbuffers)

## 许可证

本项目采用 [MIT License](LICENSE)。
