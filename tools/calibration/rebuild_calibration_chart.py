"""
按用户重排的规律重建隐藏校准谱面（就地修改已解包的 __calibration__/chart.json）。

用户实测 BPM=138，并按听觉重音把 note 排在 beat 16..28 的连续整数四分音符上。
用户拍板：真值 = 整数拍网格（做法A，不采纳 onset 的 +75ms 相位差），
note 从他的第一个 tap(beat 16) 一直铺到歌曲结束。

同时：清空判定线上的所有事件（eventLayers 各事件 + extended），
只保留一个垫底速度事件让音符能正常下落，判定线静止居中、不再有任何动效。
"""
import json
import os

CHART = os.path.expanduser("~/Library/Application Support/phiedit2573/charts/__calibration__/chart.json")

BPM = 138.0
FIRST_BEAT = 16          # 用户第一个 tap
LAST_BEAT = 340          # 到歌曲结束（148.1s / (60/138) ≈ 340 拍）
SPEED = 10               # 垫底速度事件，让音符正常下落（编辑器 addEventLayer 默认值）


def ev(t, start, end):
    return {
        "bezier": 0,
        "bezierPoints": [0.0, 0.0, 0.0, 0.0],
        "easingLeft": 0.0,
        "easingRight": 1.0,
        "easingType": 1,
        "end": end,
        "endTime": [t + 1, 0, 1],
        "linkgroup": 0,
        "start": start,
        "startTime": [t, 0, 1],
    }


def static_layer():
    """一个静止的垫底事件层：x/y/角度固定 0，alpha 全 1，speed 恒定。"""
    return {
        "moveXEvents": [ev(0, 0, 0)],
        "moveYEvents": [ev(0, 0, 0)],
        "rotateEvents": [ev(0, 0, 0)],
        "alphaEvents": [ev(0, 255, 255)],
        "speedEvents": [ev(0, SPEED, SPEED)],
    }


with open(CHART, encoding="utf-8") as f:
    chart = json.load(f)

chart["BPMList"] = [{"bpm": BPM, "startTime": [0, 0, 1]}]
chart.setdefault("META", {})["offset"] = 0

for jl in chart["judgeLineList"]:
    # 1) 清空所有判定线动效：4 层事件层全部换成静止垫底层，extended 清空
    jl["eventLayers"] = [static_layer() for _ in range(4)]
    jl["extended"] = {
        "scaleXEvents": [],
        "scaleYEvents": [],
        "inclineEvents": [],
    }
    # 判定线静止居中、始终可见
    jl["alphaControl"] = [
        {"easing": 1, "alpha": 1, "x": 0},
        {"easing": 1, "alpha": 1, "x": 999999},
    ]
    jl["anchor"] = [0.5, 0.5]
    jl["isCover"] = 1
    jl["father"] = -1
    jl["zOrder"] = 1

    # 2) 按整数拍网格铺 note：beat FIRST_BEAT..LAST_BEAT
    notes = []
    for b in range(FIRST_BEAT, LAST_BEAT + 1):
        notes.append({
            "startTime": [b, 0, 1],
            "endTime": [b, 1, 4],
            "type": 1,
            "positionX": 0,
            "above": 1,
            "alpha": 255,
            "speed": 1,
            "size": 1,
            "isFake": 0,
            "visibleTime": 999999,
            "yOffset": 0,
            "judgeArea": 1,
        })
    jl["notes"] = notes
    jl["numOfNotes"] = len(notes)

with open(CHART, "w", encoding="utf-8") as f:
    json.dump(chart, f, ensure_ascii=False, indent=2)

n = sum(len(jl["notes"]) for jl in chart["judgeLineList"])
print(f"已重建 {CHART}")
print(f"BPM={BPM}，note 铺满 beat {FIRST_BEAT}..{LAST_BEAT}，共 {n} 个 tap（整数拍网格）")
print("判定线事件已全部清空（静止居中，无动效）")
