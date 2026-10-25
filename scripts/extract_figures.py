# -*- coding: utf-8 -*-
"""从 PDF 页面提取插图（课程详解笔记流水线 · 阶段 2）

用法：
  python extract_figures.py --pdf 讲义.pdf --pages 1-3 --dpi 300 --out assets --spec spec.json

spec.json 示例（坐标为整页宽高的分数）：
{
  "figures": [
    {"name": "figure_1.png", "page": 1, "box": [0.17, 0.13, 0.99, 0.86], "trim": true, "pad": 14},
    {"name": "figure_2.png", "page": 2, "box": [0.0625, 0.186, 0.63, 0.539],
     "wipe": [{"box": [0.06, 0.16, 0.46, 0.21],
               "keep": [[255, 0, 0], [0, 200, 60], [0, 99, 255]], "tol": 90}]},
    {"name": "figure_3.png", "page": 3, "trim": true, "pad": 14,
     "compose": [
        {"box": [0.353, 0.222, 0.456, 0.363], "pad_left": 0.001},
        {"box": [0.783, 0.222, 0.886, 0.363], "pad_left": 0.001},
        {"box": [0.781, 0.418, 0.895, 0.557], "pad_left": 0.001}
     ]}
  ]
}

wipe：把页面上的文字涂白、只保留彩色图例（幻灯片正文压在图例上方时用）。
    每个 wipe 是一个分数框，先涂白再裁剪。
    - 推荐写成 {"box": [...], "keep": [[R,G,B], ...], "tol": 90}：只保留与这些
      颜色相近的像素，其余全白。图例颜色从已裁好的图里采样最准。
    - 也接受简写 [x0,y0,x1,y1]：按饱和度一刀切（sat_min，默认 55），
      能清掉灰黑文字，但"深红/深蓝的彩色标题"会留下——这类页必须给 keep。
    注意：页面上若有与图例同色的文字（蓝色链接、彩色页眉），颜色法无法分离，
    这类页把 wipe 框限制在图例上方，或直接下移裁剪边界躲开（实测就有一页
    Folie 的蓝色页眉与蓝色曲线同色，只能裁掉）。

依赖：pdftoppm（poppler/MikTeX）、Pillow、numpy。
裁完的每张图必须用 ViewImage 工具目检（不是 Read —— Read 只返回图片路径）：
完整、无杂物、标签没被切。**同一路径的图片 ViewImage 会返回缓存旧图，
核验前先复制成新文件名**。
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image

def find_pdftoppm():
    exe = shutil.which("pdftoppm")
    if exe:
        return exe
    cands = []
    if os.name == "nt":  # Windows：MikTeX 自带 poppler 的常见安装位置
        for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""),
                     os.environ.get("ProgramW6432", ""), os.environ.get("MIKTEX_BIN", "")):
            if base:
                cands += [os.path.join(base, "Programs", "MikTeX", "miktex", "bin", "x64"),
                          os.path.join(base, "MikTeX", "miktex", "bin", "x64")]
        if os.environ.get("MIKTEX_BIN", ""):
            cands.insert(0, os.environ["MIKTEX_BIN"])
    for cand in cands:
        exe = os.path.join(cand, "pdftoppm.exe")
        if os.path.exists(exe):
            return exe
    raise SystemExit("找不到 pdftoppm，请安装 poppler（macOS: brew install poppler；"
                     "Linux: apt/dnf install poppler-utils；Windows: 装 MikTeX 或 Poppler for Windows）")

def render_pages(pdf, pages, dpi, workdir):
    """pages: '54-56' 或 '54,55'。返回 {page: png路径}，路径为 C:/ 风格。"""
    exe = find_pdftoppm()
    pdf = os.path.abspath(pdf).replace("\\", "/")
    prefix = os.path.join(workdir, "pg").replace("\\", "/")
    cmd = [exe, "-f", str(min(pages)), "-l", str(max(pages)), "-r", str(dpi), "-png", pdf, prefix]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"pdftoppm 失败: {r.stderr}")
    out = {}
    for f in os.listdir(workdir):
        m = re.match(r"pg-(\d+)\.png$", f)
        if m:
            out[int(m.group(1))] = os.path.join(workdir, f).replace("\\", "/")
    return out

def crop_fraction(im, box):
    W, H = im.size
    x0, y0, x1, y1 = [int(v * d) for v, d in zip(box, (W, H, W, H))]
    return im.crop((x0, y0, x1, y1))

def autotrim(c, pad=14, thresh=248):
    g = np.array(c.convert("L"))
    mask = g < thresh
    rows = np.where(mask.any(axis=1))[0]; cols = np.where(mask.any(axis=0))[0]
    if not len(rows) or not len(cols):
        return c
    r0, r1, c0, c1 = rows[0], rows[-1], cols[0], cols[-1]
    return c.crop((max(0, c0 - pad), max(0, r0 - pad),
                   min(c.width, c1 + pad), min(c.height, r1 + pad)))

def content_row_bands(im, box, thresh=235, min_px=3):
    """返回窗口内内容行带（frac），用于确定 y 边界、防切标签。"""
    W, H = im.size
    x0, y0, x1, y1 = [int(v * d) for v, d in zip(box, (W, H, W, H))]
    sub = np.array(im.crop((x0, y0, x1, y1)).convert("RGB")).astype(int)
    nw = (sub.min(axis=2) < thresh)
    rows = nw.sum(axis=1); bands = []; s = None
    for j in range(len(rows)):
        if rows[j] > min_px and s is None: s = j
        elif rows[j] <= min_px and s is not None:
            if j - s > 4: bands.append((round((y0 + s) / H, 4), round((y0 + j - 1) / H, 4)))
            s = None
    if s is not None: bands.append((round((y0 + s) / H, 4), round((y0 + len(rows) - 1) / H, 4)))
    return bands

def blue_boxes(im, min_area=200):
    """检测幻灯片蓝色信息框（浅蓝填充），返回连通域边界(frac)。用于框与文字紧邻时的精确定位。"""
    from collections import deque
    im2 = im.resize((im.width // 4, im.height // 4))
    a = np.array(im2).astype(int); H, W, _ = a.shape
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mask = ((B - R > 12) & (B > 160)).astype(np.uint8)
    lbl = np.zeros_like(mask); out = []
    for i in range(H):
        for j in range(W):
            if mask[i, j] and lbl[i, j] == 0:
                q = deque([(i, j)]); lbl[i, j] = 1; n = 0
                mnx = mxx = j; mny = mxy = i
                while q:
                    y, x = q.popleft(); n += 1
                    mnx = min(mnx, x); mxx = max(mxx, x); mny = min(mny, y); mxy = max(mxy, y)
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and lbl[ny, nx] == 0:
                            lbl[ny, nx] = 1; q.append((ny, nx))
                if n >= min_area:
                    out.append((n, mnx / W, mny / H, mxx / W, mxy / H))
    out.sort(reverse=True)
    return out

def compose_row(imgs, gap=70, pad=15):
    Hm = max(b.height for b in imgs) + 20
    Wm = sum(b.width for b in imgs) + gap * (len(imgs) - 1) + 2 * pad
    row = Image.new("RGB", (Wm, Hm), "white"); x = pad
    for b in imgs:
        row.paste(b, (x, (Hm - b.height) // 2)); x += b.width + gap
    return row

def wipe_noncolored(im, box, sat_min=55, keep_colors=None, tol=80):
    """把区域内"要保留的内容"之外全部涂白。

    典型场景：幻灯片版式里正文（黑/灰，也可能是深红深蓝的标题）紧贴或压在
    图例（绿/红/蓝）上方，纯矩形裁剪躲不开。

    两种判定方式：
    - 给了 keep_colors（推荐）：只保留与这些颜色相差 ≤ tol 的像素，其余全白。
      图例/曲线的颜色可以从已裁好的图里采样得到，最可控。
    - 没给 keep_colors：按饱和度阈值 sat_min 判断，灰度文字会被清掉，
      但"彩色标题"（深红、深蓝的页眉）会留下来 —— 这类页必须给 keep_colors。

    box 为页面宽高的分数 [x0, y0, x1, y1]。
    """
    W, H = im.size
    x0, y0, x1, y1 = (int(round(box[0] * W)), int(round(box[1] * H)),
                      int(round(box[2] * W)), int(round(box[3] * H)))
    a = np.array(im.convert("RGB")).astype(np.int16)
    reg = a[y0:y1, x0:x1]
    if keep_colors:
        keep = np.zeros(reg.shape[:2], dtype=bool)
        for c in keep_colors:
            diff = np.abs(reg - np.array(c, dtype=np.int16)).max(axis=2)
            keep |= (diff <= tol)
    else:
        keep = (reg.max(axis=2) - reg.min(axis=2)) > sat_min
    reg[~keep] = 255
    a[y0:y1, x0:x1] = reg
    return Image.fromarray(a.astype("uint8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pages", required=True, help="如 54-56 或 54,55")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", default="assets")
    ap.add_argument("--spec", required=True, help="spec.json，见文件头注释")
    args = ap.parse_args()
    pages = sorted({int(x) for p in args.pages.split(",") for x in
                    ([p] if "-" not in p else [p.split("-")[0], p.split("-")[1]])})
    pages = list(range(pages[0], pages[-1] + 1))
    os.makedirs(args.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        imgs = render_pages(args.pdf, pages, args.dpi, td.replace("\\", "/"))
        spec = json.load(open(args.spec, encoding="utf-8"))
        for fig in spec["figures"]:
            page = fig["page"]; im = Image.open(imgs[page]).convert("RGB")
            # 先按 wipe 区域涂白（保留彩色图例），再裁剪
            for wb in fig.get("wipe", []):
                if isinstance(wb, dict):
                    im = wipe_noncolored(im, wb["box"], wb.get("sat_min", fig.get("sat_min", 55)),
                                         wb.get("keep"), wb.get("tol", 80))
                else:
                    im = wipe_noncolored(im, wb, fig.get("sat_min", 55))
            if "compose" in fig:
                parts = []
                for item in fig["compose"]:
                    b = list(item["box"])
                    pl = item.get("pad_left", 0)   # 左侧紧邻文字列时抬高左边界，防文字残片混入
                    b[0] += pl
                    c = crop_fraction(im, b)
                    parts.append(autotrim(c, pad=item.get("pad", 12)))
                compose_row(parts).save(os.path.join(args.out, fig["name"]))
            else:
                c = crop_fraction(im, fig["box"])
                if fig.get("trim", True):
                    c = autotrim(c, pad=fig.get("pad", 14))
                c.save(os.path.join(args.out, fig["name"]))
            print(f"{fig['name']:36s} <- p{page}")
    print("完成。务必用 ViewImage 逐张目检（Read 只返回路径，看不了图）；"
          "同路径有缓存，核验前复制成新文件名。")

if __name__ == "__main__":
    main()
