"""
把本机已验证的隐藏校准谱面（userData/charts/__calibration__）打包成
resources/calibrationChart.pez，供随包发布。

这么做保证「随包发布的谱面」与「用户手动调好的谱面」逐字节一致，
避免仓库里那份旧 pez（BPM120/21note/样板动效）在别人机器上复现。

pez = zip，内含：
  - chart.json           谱面本体（BPM138，beat16..340 共 325 tap，判定线静止无动效）
  - info.txt             谱面信息
  - introduction.mp3     完整歌曲（与真值同一坐标系）
  - calibration_bg.png   背景图

前置：本机需先跑过一次校准（userData 里才有 __calibration__ 谱面）。
"""
import os
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOME = os.path.expanduser("~")
SRC_DIR = os.path.join(HOME, "Library/Application Support/phiedit2573/charts/__calibration__")
OUT_PEZ = os.path.join(REPO_ROOT, "resources", "calibrationChart.pez")

FILES = [
    ("chart.json", "chart.json"),
    ("info.txt", "info.txt"),
    ("introduction.mp3", "introduction.mp3"),
    ("calibration_bg.png", "calibration_bg.png"),
]

# 必备文件检查
for local, _ in FILES:
    p = os.path.join(SRC_DIR, local)
    if not os.path.exists(p):
        raise SystemExit(f"缺少文件: {p}")

if os.path.exists(OUT_PEZ):
    os.remove(OUT_PEZ)

os.makedirs(os.path.dirname(OUT_PEZ), exist_ok=True)
with zipfile.ZipFile(OUT_PEZ, "w", zipfile.ZIP_DEFLATED) as z:
    for local, arc in FILES:
        z.write(os.path.join(SRC_DIR, local), arc)

print(f"已打包 {OUT_PEZ} ({os.path.getsize(OUT_PEZ)} bytes)")
with zipfile.ZipFile(OUT_PEZ) as z:
    for n in z.namelist():
        print(f"  {n}  {z.getinfo(n).file_size} bytes")
