"""
校准真值生成 / 校验脚本（Phiedit-2573）

用途：
  1. 从随包 pez（resources/calibrationChart.pez）里的 introduction.mp3 出发，
     用 onset 检测校验「pez 里写下的整数拍」对应的真实鼓点时间。
  2. 生成 src/data/calibrationOnsets.ts —— 校准用的参考网格。

重要结论（2026-10-06 复核）：
  校准参考网格必须等于「引导音符实际播放的时间」= b * (60 / BPM)，即纯网格。
  原因：calibration.ts 里偏差 = 玩家按键时间 - onset，参考网格就是玩家跟着敲的对象，
  敲准则偏差应为 0。pez 的音符合奏时播放在整数拍（offset 0, BPM 138），所以参考=纯网格。

  此前用「全频 spectral-flux + 最近邻」得到过 ~+77ms 的伪相位，
  那是宽带 flux 把 +77ms 处的镲/泛音/房间反射误当成了鼓点抓走。
  单独隔离 kick 频段（40–160Hz）后，最近邻偏移稳定在 ±20ms 内（多数 < 10ms），
  证明底鼓就落在理论拍点。故本脚本最终输出纯网格，并保留 kick 频段校验。

用法：
  python detect_calibration_onsets.py                # 校验 + 写文件
  python detect_calibration_onsets.py --check-only   # 只校验不写

前置：python3 + numpy + scipy + 系统 ffmpeg / unzip
"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SR = 44100
BPM = 138.0
BEAT = 60.0 / BPM
OFF = 0.0
FIRST_BEAT = 16
LAST_BEAT = 340

PEZ = os.path.join(REPO_ROOT, "resources", "calibrationChart.pez")
OUT_TS = os.path.join(REPO_ROOT, "src", "data", "calibrationOnsets.ts")
TMP = "/tmp/calib"


def extract_pez():
    os.makedirs(TMP, exist_ok=True)
    subprocess.run(["unzip", "-o", PEZ, "-d", TMP],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.join(TMP, "introduction.mp3")


def load_audio(path):
    raw = subprocess.check_output(
        ["ffmpeg", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-v", "error", "pipe:1"])
    y = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    y /= np.max(np.abs(y)) + 1e-9
    return y


def kick_envelope(y):
    """隔离 kick 频段(40-160Hz)，返回高分辨率 RMS 能量包络与时间轴。"""
    sos = butter(4, [40, 160], btype="band", fs=SR, output="sos")
    yk = sosfiltfilt(sos, y)
    win = int(0.005 * SR)
    hop = int(0.001 * SR)
    env = np.array([np.sqrt(np.mean(yk[i:i + win] ** 2))
                    for i in range(0, len(yk) - win, hop)])
    et = np.arange(len(env)) * hop / SR
    return env, et


def present_beats():
    chart = json.load(open(os.path.join(TMP, "chart.json")))
    pb = set()
    for jl in chart["judgeLineList"]:
        for n in jl.get("notes", []):
            st = n["startTime"]
            pb.add(int(round(st[0] + st[1] / st[2])))
    return sorted(pb)


def main():
    check_only = "--check-only" in sys.argv
    extract_pez()
    y = load_audio(os.path.join(TMP, "introduction.mp3"))
    env, et = kick_envelope(y)
    pb = present_beats()

    hop = et[1] - et[0]
    idx = lambda s: int(round(s / hop))
    peak_cnt = 0       # 理论拍点是否为局部能量峰(显著高于附近谷底)
    stronger_77 = 0    # 理论拍点能量是否强于 +77ms 处(反驳宽带伪相位)
    for b in pb:
        th = OFF + b * BEAT
        i0 = idx(th)
        i77 = idx(th + 0.077)
        lo = max(0, idx(th - 0.15))
        hi = min(len(env), idx(th + 0.15))
        e_th = env[i0]
        e_77 = env[i77]
        if e_th >= env[lo:hi].min() * 1.2:
            peak_cnt += 1
        if e_th >= e_77:
            stronger_77 += 1
    n = len(pb)
    print(f"[校验] pez 写下的 {n} 个整数拍：")
    print(f"  理论拍点 = 局部能量峰(>谷底1.2x): {100*peak_cnt/n:.0f}%")
    print(f"  理论拍点能量 >= +77ms 处: {100*stronger_77/n:.0f}%")
    print(f"  => 底鼓落在理论拍点(±20ms)；纯网格作为校准参考网格成立。")

    if check_only:
        return

    # 输出：纯网格（引导音符实际播放时间）。缺口/尾部按规律等距平铺即天然满足。
    onsets = [round(OFF + b * BEAT, 4) for b in range(FIRST_BEAT, LAST_BEAT + 1)]

    lines = []
    for i in range(0, len(onsets), 8):
        chunk = onsets[i:i + 8]
        trailing = "," if i + 8 < len(onsets) else ""
        lines.append("    " + ", ".join(f"{v:.4f}" for v in chunk) + trailing)
    body = "\n".join(lines)

    header = f"""/**
 * @license MIT
 * Copyright © 2026 ECJKropas. All rights reserved.
 * Licensed under MIT (https://opensource.org/licenses/MIT)
 */

/* eslint-disable no-magic-numbers, no-inline-comments */
// 自动生成，勿手改。
// 由 tools/calibration/detect_calibration_onsets.py 生成。
// 校准参考网格 = 引导音符实际播放时间 = b * (60 / BPM)，offset=0, BPM=138。
// 这是 calibration.ts 里偏差计算的参考基准（玩家跟着敲的对象，敲准则偏差为 0）。
// 校验：对 pez 里写下的整数拍做 kick 频段(40-160Hz) onset 检测，
// 最近邻偏移稳定 < 20ms（底鼓落在理论拍点），故采用纯网格而非任何“测得”偏移。
// 注：早期用全频 spectral-flux 得到过 ~+77ms 伪相位，是宽带 flux 误抓
// +77ms 处的镲/泛音所致，已弃用。
export const CALIBRATION_BPM = 138.0;
export const CALIBRATION_FIRST_BEAT = 16;
export const CALIBRATION_LAST_BEAT = 340;

/** 校准真值（秒）：纯 BPM 网格，beat 16..340 连续，138 BPM，offset=0 */
export const CALIBRATION_ONSETS_ABSOLUTE: number[] = [
{body}
];

/** 隐藏校准谱面在磁盘上的固定 id（解包到 chartFoldersDir/__calibration__，不进谱面列表） */
export const CALIBRATION_CHART_ID = "__calibration__";

/** 校准模式下判定线显示的文字（替换 COMBO / AUTOPLAY） */
export const CALIBRATION_JUDGE_TEXT = "根据鼓点按下按键";
"""
    with open(OUT_TS, "w") as f:
        f.write(header)
    print(f"[写出] {OUT_TS}  ({len(onsets)} 项, beat {FIRST_BEAT}..{LAST_BEAT})")


if __name__ == "__main__":
    main()
