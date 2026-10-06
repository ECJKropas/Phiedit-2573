# tools/

与**软件本身无关**、但在**软件改版 / 升级时可能用到**的辅助程序与脚本。

这些文件不进入打包范围（不在 `public/`、`resources/`、`dist_electron/` 之内），
不会被打进安装包，可安全保留在仓库里供后续维护与复现使用。

- `calibration/`：隐藏校准谱面（`resources/calibrationChart.pez`）相关的开发 / 复现脚本。
- `calibration/assets/`、`calibration/_archive/`：二进制资产（原始歌曲、旧版 zip 等），
  已被 `.gitignore` 排除，不进仓库（与 pez 内歌曲重复，避免体积膨胀）。
