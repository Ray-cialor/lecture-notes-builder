#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 0：开工自检（preflight）

在任何撰写/修订之前跑一次，把输出留在对话里。
它的作用不是"检查文档"，而是**证明进程走过**：规则清单 + 当前文件体检一次打出来。

用法：
    python preflight.py 笔记.md
    python preflight.py 笔记.md --pages 4-50 --assets assets

退出码恒为 0（这是清单，不是门禁）；真正的门禁是 md_to_docx.py --check-only。
"""
import sys
import os
import re
import glob

# ---------- 1. 文风负面清单（讲义腔，不是讲稿腔） ----------
STYLE_BAD = {
    "讲稿腔·俚语": ["晃", "胖", "白丢分", "打乒乓", "打架", "捣乱", "硬凑", "顺口", "整题白做", "钉死", "秒懂"],
    "讲稿腔·超级化": ["最该记住", "最漂亮", "最省事", "最要紧", "最容易搞混", "最好记"],
    "讲稿腔·设问": ["看出来没有", "为什么？因为", "你能想象"],
    "讲稿腔·金句尾巴": ["一句话记", "一句话记法", "一句话概括"],
    "元叙述（讲怎么讲）": ["这一节讲", "这一段的顺序", "下面按", "接下来讲"],
}

# ---------- 2. 必跑命令 ----------
COMMANDS = [
    ("结构自检", "python md_to_docx.py --check-only 笔记.md"),
    ("公式真渲染", "node katex_check.js 笔记.md"),
    ("目录重建（改过标题才跑）", "python md_to_docx.py 笔记.md --fix-toc --depth 3"),
]


def zh_len(t):
    return sum(1 for c in t if "\u4e00" <= c <= "\u9fff")


def scan(path, assets="assets"):
    s = open(path, encoding="utf-8").read()
    L = s.split("\n")
    print("=" * 58)
    print("阶段 0 · 开工自检")
    print("=" * 58)
    print("文件：%s" % path)
    print("  行数 %d ｜ 汉字 %d ｜ 公式块 %d ｜ 图 %d ｜ 表行 %d ｜ ### %d" % (
        len(L), zh_len(s),
        s.count("\n$$\n") // 2,
        s.count("!["),
        sum(1 for l in L if l.startswith("|")),
        sum(1 for l in L if l.startswith("### ")),
    ))
    blank = sum(1 for l in L if not l.strip())
    dd = sum(1 for l in L if l.strip() == "$$")
    print("  排版占比：空行 %d、$$ 分隔行 %d（合计 %.0f%% 不是正文）" % (
        blank, dd, 100.0 * (blank + dd) / max(1, len(L))))

    # ---------- 3. 条款级红线（--check-only 查不到的那些） ----------
    print("-" * 58)
    print("条款级红线（--check-only 的盲区）")
    bad = 0

    hit = [l[4:44] for l in L if l.startswith("### ") and ("$" in l or "\\" in l)]
    if hit:
        bad += 1
        print("  ✗ ### 标题里有公式（pitfall 39）：%d 处，例 %s" % (len(hit), hit[0]))
        print("     → --fix-toc --depth 3 会把 $...$ 原文带进目录，改成文字")

    hit = [m.group(1)[:24] for m in re.finditer(r"!\[([^\]]*)\]", s)
           if "$" in m.group(1) or "\\" in m.group(1)]
    if hit:
        bad += 1
        print("  ✗ 图注 alt 里有 LaTeX（pitfall 40）：%d 处，例 %s" % (len(hit), hit[0]))
        print("     → 图片加载失败时会显示公式原文，改成纯文字")

    for w in ["**考点**", "考点：", "- [ ]"]:
        if w in s:
            bad += 1
            print("  ✗ 出现禁用写法：%s（%d 处）" % (w, s.count(w)))

    if re.search(r"\*\*\$[^$]*\$\*\*", s):
        bad += 1
        print("  ✗ 加粗直接包公式 **$...$**：%d 处" % len(re.findall(r"\*\*\$[^$]*\$\*\*", s)))

    n = len(re.findall(r"(?<![\\\w])\d+\s*/\s*\(", s))
    if n:
        bad += 1
        print("  ✗ 斜杠分数 x/(y)：%d 处（改 \\frac）" % n)

    # 资产反向检查（只在本篇用到的文件名前缀内比较，避免多章共用 assets 目录时误报）
    d = os.path.join(os.path.dirname(os.path.abspath(path)), assets)
    if os.path.isdir(d):
        used = set(re.findall(r"!\[[^\]]*\]\((?:%s/)?([^)/]+)\)" % re.escape(assets), s))
        prefixes = {u.split("_")[0] + "_" for u in used if "_" in u}
        files = {os.path.basename(f) for f in glob.glob(os.path.join(d, "*"))}
        files = {f for f in files if any(f.startswith(p) for p in prefixes)} if prefixes else files
        unused = sorted(files - used)
        if unused:
            bad += 1
            print("  ✗ assets 里有 %d 张图没被引用：%s" % (len(unused), ", ".join(unused[:4])))
            print("     → 多半该插的图漏了，先查是不是内容缺口")

    # spec 覆盖检查：图有裁切坐标存档，且条目数 = 引用图数
    import glob as _g
    spec = None
    for cand in (os.path.dirname(os.path.abspath(path)),):
        hits = _g.glob(os.path.join(cand, "*figure_spec*.json"))
        if hits:
            spec = hits[0]
            break
    if spec:
        try:
            import json
            names = {f["name"] for f in json.load(open(spec, encoding="utf-8"))["figures"]}
            used = set(re.findall(r"!\[[^\]]*\]\((?:%s/)?([^)/]+)\)" % re.escape(assets), s))
            miss = sorted(u for u in used if u.startswith("ch") and u not in names)
            print("  %s spec 条目 %d / 引用图 %d%s" % (
                "✓" if not miss else "✗", len(names), len(used),
                "" if not miss else "，缺坐标：" + ", ".join(miss[:3])))
            if miss:
                bad += 1
        except Exception as e:
            print("  · spec 读取失败：%s" % e)
    else:
        print("  · 未找到 *figure_spec*.json，跳过 spec 覆盖检查")

    # 备考清单条数
    if "## 备考清单" in s:
        cnt = len(re.findall(r"(?m)^\d+\. ", s[s.index("## 备考清单"):]))
        flag = "" if cnt <= 8 else "  ← 超上限 8"
        print("  %s 备考清单条数 %d%s" % ("✓" if cnt <= 8 else "✗", cnt, flag))
        if cnt > 8:
            bad += 1

    # 中德对照（粗略）：术语成对加粗后面有没有括注
    pairs = re.findall(r"\*\*[A-ZÄÖÜ][^*\n]*[\u4e00-\u9fff][^*\n]+\*\*", s)
    no_gloss = [p for p in pairs if not re.search(re.escape(p) + r"（", s)]
    if pairs:
        print("  · 术语成对加粗 %d 处，其中 %d 处无中文括注（基础词可豁免）" % (
            len(pairs), len(no_gloss)))

    if bad == 0:
        print("  ✓ 条款级红线全过")

    # ---------- 4. 文风扫描 ----------
    print("-" * 58)
    print("文风扫描（讲义腔 vs 讲稿腔）")
    total = 0
    for kind, words in STYLE_BAD.items():
        hit = [(w, s.count(w)) for w in words if w in s]
        if hit:
            total += sum(c for _, c in hit)
            print("  ! %s：%s" % (kind, "、".join("%s×%d" % (w, c) for w, c in hit)))
    if total == 0:
        print("  ✓ 未命中负面词表")
    else:
        print("  合计 %d 处。讲义腔的标准是：直接陈述 + 数字说话，不用设问、不用金句收尾。" % total)

    # ---------- 5. 交付前必跑 ----------
    print("-" * 58)
    print("交付前必跑（两个都 0 错才算完）")
    for name, cmd in COMMANDS:
        print("  [%s] %s" % (name, cmd))
    print("=" * 58)
    print("把这段输出贴在交付说明里——它是我走过流程的唯一凭据。")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    path = args[0]
    assets = "assets"
    if "--assets" in sys.argv:
        assets = sys.argv[sys.argv.index("--assets") + 1]
    if not os.path.exists(path):
        print("找不到文件：%s" % path)
        return
    scan(path, assets)


if __name__ == "__main__":
    main()
