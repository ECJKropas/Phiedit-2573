# 校准谱面辅助脚本

隐藏校准谱面 `resources/calibrationChart.pez` 的开发 / 复现工具。**不进安装包**。

## 前置

- Python 3.10+
- `numpy`、`scipy`（仅 `detect_calibration_onsets.py` / `extract_onsets.py` 需要）
- 系统 `ffmpeg`、`unzip`（部分脚本会调用）

## 脚本

| 脚本 | 作用 | 输入 | 输出 |
| --- | --- | --- | --- |
| `detect_calibration_onsets.py` | 校验 pez 内整数拍是否落在真实鼓点（kick 频段），并重新生成 `src/data/calibrationOnsets.ts`（纯网格） | `resources/calibrationChart.pez` | `src/data/calibrationOnsets.ts` |
| `generate_calibration_chart.py` | 以随包 pez 为模板，按 `calibrationOnsets.ts` 重对齐 note 时间，重新打包 pez（**保留原 note 拍位 / 缺口**） | `resources/calibrationChart.pez` + `src/data/calibrationOnsets.ts` | `resources/calibrationChart.pez` |
| `package_calibration_pez.py` | 把你手动调好的 userData 谱面打包成随包 pez | `~/Library/Application Support/phiedit2573/charts/__calibration__/*` | `resources/calibrationChart.pez` |
| `rebuild_calibration_chart.py` | 就地重建 userData 里的谱面（整数拍网格铺 note、清空判定线动效） | userData `__calibration__/chart.json` | 同左（就地修改） |
| `extract_onsets.py` | **（旧 / 遗留）** 全曲 onset 提取与循环区间切分；其输出格式已废弃，**不要**直接覆盖 `calibrationOnsets.ts` | `assets/introduction.mp3` | `_archive/calibrationOnsets.legacy.ts` |

## 典型流程

- **复现 / 校验校准数据**：`python detect_calibration_onsets.py --check-only`
- **重打随包 pez**：先确认 `calibrationOnsets.ts` 正确 → `python generate_calibration_chart.py`

> 注：`assets/introduction.mp3`（原始歌曲）不在仓库内（与 pez 内歌曲重复，且被 `.gitignore` 排除）。
> 需要时可从 `resources/calibrationChart.pez` 解包取得同名文件放入 `assets/`。
