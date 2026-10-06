#!/usr/bin/env python3
"""
离线提取校准音乐的鼓点 onset，并生成硬编码数据文件。

流程：
1. 读取分析用 wav（已由 ffmpeg 转成 22050Hz 单声道）。
2. 用宽带频谱通量(spectral flux)做 onset 检测 + 峰值挑选，并合并 90ms 内的双峰。
3. 扫描全曲：对每个候选窗口，搜索最匹配的周期 P 与相位 φ（网格拟合）。
   目标是在「可跟的速度」内，挑网格线命中密度最高(每拍都有鼓)、且周期=实测间隔的、尽可能慢的周期。
4. 由拟合出的鼓点 ±padding 定义循环区间。
5. 用 ffmpeg 把该循环区间从原 mp3 切出到 public/calibrationLoop.mp3。
6. 写出 src/data/calibrationOnsets.ts（onset 秒数相对循环起点 + 循环长度 + 元信息）。

只依赖 numpy / scipy，运行时无 DSP。
"""
import os
import subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram, find_peaks

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# !! LEGACY — 其输出格式（CALIBRATION_LOOP_START / CALIBRATION_ONSETS）已废弃，
#    与当前 src/data/calibrationOnsets.ts（CALIBRATION_ONSETS_ABSOLUTE）不兼容。
#    请勿直接用它覆盖正式数据文件；产物改写到 _archive/ 下，仅供回溯参考。
SRC_MP3 = os.path.join(REPO_ROOT, "tools/calibration/assets/introduction.mp3")
ANALYSIS_WAV = "/tmp/intro_analysis.wav"
OUT_MP3 = os.path.join(REPO_ROOT, "tools/calibration/_archive/calibrationLoop.mp3")
OUT_TS = os.path.join(REPO_ROOT, "tools/calibration/_archive/calibrationOnsets.legacy.ts")

# --- 参数 ---
SR_TARGET = 22050
HOP_S = 512 / SR_TARGET
MIN_SPACING_S = 0.05       # 峰值最小间隔(去连击)
MERGE_S = 0.13             # 130ms 内双峰合并为一个鼓点(攻击+衰减被检成两个峰)
PEAK_HEIGHT = 0.08
PEAK_PROMINENCE = 0.04
WINDOW_LEN_S = 16.0
WINDOW_HOP_S = 2.0
P_MIN, P_MAX, P_STEP = 0.22, 0.62, 0.005  # 搜索周期范围：8分~2分音符
MIN_HITS = 18              # 窗口内最少落在网格上的鼓点数
DENSITY_TARGET = 0.80      # 期望网格线命中密度
PERIOD_TOL = 0.15          # 周期与实测间隔偏差容忍
PAD_S = 0.40


def detect_onsets(wav_path):
    sr, y = wavfile.read(wav_path)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype(np.float64)
    y /= np.max(np.abs(y)) + 1e-9

    freqs, times, Sxx = spectrogram(
        y, fs=sr, window="hann", nperseg=1024, noverlap=512, mode="magnitude"
    )
    flux = np.zeros(Sxx.shape[1])
    diff = np.diff(Sxx, axis=1)
    flux[1:] = np.sum(np.maximum(diff, 0.0), axis=0)
    flux /= flux.max() + 1e-12

    min_dist = max(1, int(round(MIN_SPACING_S / HOP_S)))
    peaks, _ = find_peaks(flux, distance=min_dist, height=PEAK_HEIGHT,
                          prominence=PEAK_PROMINENCE)
    t = times[peaks]

    # 合并 90ms 内双峰(同一鼓击的攻击+衰减被检成两个峰)
    merged = []
    last = None
    for p in t:
        if last is None or (p - last) > MERGE_S:
            merged.append(p)
            last = p
    return np.array(merged)


def fit_grid(onsets, P, tol):
    """返回 (命中网格线的鼓点数, 最佳相位 phi, 命中掩码)。"""
    best = (0, 0.0, None)
    for ref in onsets:
        phi = ref % P
        d = np.abs((onsets - phi) % P)
        d = np.minimum(d, P - d)
        mask = d <= tol
        cnt = int(mask.sum())
        if cnt > best[0]:
            best = (cnt, phi, mask)
    return best


def best_grid_for_window(onsets, span):
    s, e = span
    best = None
    for P in np.arange(P_MIN, P_MAX + 1e-9, P_STEP):
        tol = max(0.04, 0.12 * P)
        hits, phi, mask = fit_grid(onsets, P, tol)
        if hits < 2:
            continue
        # 命中「不同」网格线的数量(只统计落在区间内的线，去双峰重复命中)
        idx = np.round((onsets[mask] - phi) / P).astype(int)
        total_lines = int((e - s) / P) + 1
        idx_in = idx[(idx >= 0) & (idx <= total_lines - 1)]
        distinct = len(np.unique(idx_in))
        density = distinct / total_lines if total_lines else 0.0
        med_ioi = float(np.median(np.diff(onsets[mask]))) if hits >= 2 else 0.0
        max_ioi = float(np.max(np.diff(onsets[mask]))) if hits >= 2 else 0.0
        if best is None or density > best["density"]:
            best = {"P": P, "phi": phi, "mask": mask,
                    "hits": hits, "density": density,
                    "med_ioi": med_ioi, "max_ioi": max_ioi}
    return best


def pick_window(times, duration):
    candidates = []
    s = 0.0
    while s + WINDOW_LEN_S <= duration:
        e = s + WINDOW_LEN_S
        tw = times[(times >= s) & (times <= e)]
        if len(tw) < MIN_HITS:
            s += WINDOW_HOP_S
            continue
        g = best_grid_for_window(tw, (s, e))
        if g is None or g["hits"] < MIN_HITS:
            s += WINDOW_HOP_S
            continue
        # 周期必须等于实测间隔，否则拟合是脏的
        if abs(g["med_ioi"] - g["P"]) > PERIOD_TOL * g["P"]:
            s += WINDOW_HOP_S
            continue
        candidates.append({**g, "start": s, "end": e})
        s += WINDOW_HOP_S

    if not candidates:
        raise RuntimeError("未找到足够稳定的鼓点段落，请调整参数或更换曲目。")

    good = [c for c in candidates if c["density"] >= DENSITY_TARGET]
    pool = good if good else candidates
    top_density = max(c["density"] for c in pool)
    same = [c for c in pool if abs(c["density"] - top_density) < 1e-6]
    same.sort(key=lambda c: c["P"], reverse=True)  # 同密度挑最慢(舒服)
    return same[0]


def main():
    print("检测 onset ...")
    times = detect_onsets(ANALYSIS_WAV)
    duration = float(times[-1]) if len(times) else 0.0
    print(f"  合并后峰值数: {len(times)}, 曲目时长: {duration:.2f}s")

    best = pick_window(times, duration)
    tw = times[(times >= best["start"]) & (times <= best["end"])]
    fitted = tw[best["mask"]]
    P = best["P"]
    # 仅修剪头尾超过 1.5 倍周期的长间隔(剥掉前奏/尾奏死寂)，段内留白保留
    while len(fitted) >= 2 and (fitted[1] - fitted[0]) > 1.5 * P:
        fitted = fitted[1:]
    while len(fitted) >= 2 and (fitted[-1] - fitted[-2]) > 1.5 * P:
        fitted = fitted[:-1]
    loop_start = max(0.0, fitted[0] - PAD_S)
    loop_end = min(duration, fitted[-1] + PAD_S)
    loop_len = loop_end - loop_start
    onset_rel = np.round(fitted[(fitted >= loop_start) & (fitted <= loop_end)]
                         - loop_start, 4)

    iois = np.diff(onset_rel)
    print(f"选定循环区间: {loop_start:.2f}s - {loop_end:.2f}s (长 {loop_len:.2f}s)")
    print(f"周期 P={P*1000:.0f}ms (~{60/P:.1f} BPM 对应层), "
          f"命中密度: {best['density']*100:.1f}%, 鼓点数: {len(onset_rel)}")
    print(f"间隔 min/med/max: {iois.min()*1000:.0f}/"
          f"{np.median(iois)*1000:.0f}/{iois.max()*1000:.0f}ms")
    print(f"全部 onset(s): {np.round(onset_rel, 3).tolist()}")

    print("切出循环音频 ...")
    subprocess.run([
        "ffmpeg", "-y", "-i", SRC_MP3,
        "-ss", f"{loop_start:.4f}", "-t", f"{loop_len:.4f}",
        "-c:a", "libmp3lame", "-b:a", "192k", OUT_MP3,
    ], check=True, capture_output=True)
    print(f"  已写出 {OUT_MP3}")

    os.makedirs(os.path.dirname(OUT_TS), exist_ok=True)
    arr = ", ".join(f"{v:.4f}" for v in onset_rel)
    content = f"""// 自动生成，勿手改。
// 校准用的内置循环音乐鼓点 onset（秒，相对循环起点 0）。
// 由 extract_onsets.py（legacy）提取自 tools/calibration/assets/introduction.mp3。
// 同时用于：(1) 校准弹窗里下落 Tap 撞判定线的时刻；(2) 最近鼓点/回归的数学真值。
export const CALIBRATION_LOOP_START = {loop_start:.4f}; // 原曲中的循环起点(秒)
export const CALIBRATION_LOOP_LENGTH = {loop_len:.4f};  // 循环长度(秒)
export const CALIBRATION_ONSETS: number[] = [{arr}];
"""
    with open(OUT_TS, "w") as f:
        f.write(content)
    print(f"  已写出 {OUT_TS}")


if __name__ == "__main__":
    main()
