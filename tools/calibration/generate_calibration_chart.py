"""
重新生成隐藏校准谱面 resources/calibrationChart.pez（纯仓库资产，可复现）。

做法：
- 以随包 pez（resources/calibrationChart.pez）为模板，复用其已验证的判定线结构
  （位置/速度/透明度/背景图）与**已有的 note 拍位（含视觉留白缺口）**。
- 仅把每个 note 的时间，按 src/data/calibrationOnsets.ts 的 CALIBRATION_ONSETS_ABSOLUTE
  （= beat*60/BPM，offset=0）重新对齐：note.startTime 拍数 = onset秒 * BPM / 60。
  => 播放头到达 onset 时音符撞判定线；缺口（无 note 的区间）保持原样。
- 前置：标准库即可（zipfile），无需 ffmpeg。

说明：CALIBRATION_ONSETS_ABSOLUTE 是偏差计算的参考网格；pez 的实际 note 只落在
用户选定的拍上（含视觉留白），二者分离。本脚本只重对齐时间，不新增/删除 note，
故重打后的 pez 与当前随包 pez 在 note 集合上完全一致。
"""
import json
import os
import re
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEMPLATE_PEZ = os.path.join(REPO_ROOT, "resources", "calibrationChart.pez")
ONSETS_TS = os.path.join(REPO_ROOT, "src", "data", "calibrationOnsets.ts")
OUT_PEZ = os.path.join(REPO_ROOT, "resources", "calibrationChart.pez")
TMP = "/tmp/calibration_chart_regen"


def read_onset_map():
    with open(ONSETS_TS, encoding="utf-8") as f:
        ts = f.read()
    bpm = float(re.search(r"CALIBRATION_BPM\s*=\s*([\d.]+)", ts).group(1))
    first = int(re.search(r"CALIBRATION_FIRST_BEAT\s*=\s*(\d+)", ts).group(1))
    last = int(re.search(r"CALIBRATION_LAST_BEAT\s*=\s*(\d+)", ts).group(1))
    onsets = [float(x) for x in
              re.search(r"CALIBRATION_ONSETS_ABSOLUTE\s*:\s*number\[\]\s*=\s*\[([^\]]+)\]", ts)
              .group(1).split(",")]
    # beat -> absolute seconds
    return bpm, {b: onsets[b - first] for b in range(first, last + 1)}


def main():
    bpm, onset_map = read_onset_map()
    beat_per_sec = bpm / 60.0

    os.makedirs(TMP, exist_ok=True)
    with zipfile.ZipFile(TEMPLATE_PEZ) as z:
        z.extractall(TMP)
        names = z.namelist()

    jname = next(n for n in names if n.endswith(".json") and "info" not in n.lower())
    with open(os.path.join(TMP, jname), encoding="utf-8") as f:
        chart = json.load(f)

    n = 0
    for jl in chart.get("judgeLineList", []):
        for note in jl.get("notes", []):
            st = note["startTime"]
            b = int(round(st[0] + st[1] / st[2]))
            if b in onset_map:
                beats = round(onset_map[b] * beat_per_sec, 4)
                note["startTime"] = [beats, 0, 1]
                note["endTime"] = [beats, 0, 1]
                n += 1

    with open(os.path.join(TMP, jname), "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)

    if os.path.exists(OUT_PEZ):
        os.remove(OUT_PEZ)
    with zipfile.ZipFile(OUT_PEZ, "w", zipfile.ZIP_DEFLATED) as z:
        for nm in names:
            z.write(os.path.join(TMP, nm), nm)
    print(f"已写出 {OUT_PEZ} ({os.path.getsize(OUT_PEZ)} bytes)，重对齐 {n} 个 note")


if __name__ == "__main__":
    main()
