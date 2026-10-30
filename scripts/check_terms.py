#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中德对照双向检查：源材料里出现过的德语术语，正文里有没有？

用法：
    python check_terms.py 笔记.md --ppt 讲义.pdf --skript 教材.pdf
    python check_terms.py 笔记.md --text dump.txt          # 已用 pdftotext 抽好的文本
    python check_terms.py 笔记.md --text dump.txt --min 5  # 只看出现 ≥5 次的词

输出两类缺口：
  ① 源材料高频、正文一次都没提（可能是漏写的概念）
  ② 术语表里有、正文没有（词表与正文脱节）

只做提示，不改文件。德语词提取用 `[A-ZÄÖÜ][a-zäöüß]{4,}`，已剔除页脚人名与功能词。
"""
import io
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

PDFTOTEXT = shutil.which("pdftotext") or shutil.which("pdftotext.exe")

STOP = set("""Elektro Medien Informationstechnik
Diese Dieser Dieses Damit Dabei Dazu Dann Wenn Wird Werden Wurde Kann Koennen Muss
Mussen Soll Sollen Ist Sind War Hat Haben Nach Bei Vom Von Zum Zur Aus Auf Ueber Unter Zwischen
Somit Also Auch Noch Nur Eine Einer Eines Einem Einen Der Die Das Den Dem Des Sie Ihr Ihre Ihrem
Ihren Man Nun Hier Dort Beispiel Beispielsweise Abbildung Seite Kapitel Nicht Ohne Sehr Mehr
Weniger Gilt Folgt Erhaelt Ergibt Betraegt Siehe Jetzt Welche Folgenden Realer Laesst Betrachtung
Darstellung Aufgabe Berechnung Berechnen Verhaeltnis Anteil Anteile Bereich Abstand Zeitpunkt
Ergebnis Definition Funktion Funktionen System Systems Signale Signalen Signal Signals Werte
Maximum Maximalwert Gleichung Sinus Grafik Zyklus Quelle Komplexe Allgemeinen""".split())


def pdf_text(path):
    exe = PDFTOTEXT if (PDFTOTEXT and os.path.exists(PDFTOTEXT)) else "pdftotext"
    p = subprocess.run([exe, "-layout", path, "-"], capture_output=True)
    return p.stdout.decode("utf-8", "replace")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    md_path = sys.argv[1]
    md = io.open(md_path, encoding="utf-8").read()
    body = md.split("## 全章德汉术语速查表")[0]
    gloss = md[md.index("## 全章德汉术语速查表"):] if "## 全章德汉术语速查表" in md else ""

    src = ""
    if "--text" in sys.argv:
        src += io.open(sys.argv[sys.argv.index("--text") + 1], encoding="utf-8", errors="ignore").read()
    if "--ppt" in sys.argv:
        src += pdf_text(sys.argv[sys.argv.index("--ppt") + 1])
    if "--skript" in sys.argv:
        src += pdf_text(sys.argv[sys.argv.index("--skript") + 1])
    if not src.strip():
        print("没给源材料：用 --text / --ppt / --skript 指定")
        return

    minfreq = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 4

    words = Counter(re.findall(r"[A-ZÄÖÜ][a-zäöüß]{4,}", src))
    cands = [(w, c) for w, c in words.most_common(300) if c >= minfreq and w not in STOP]

    miss_body = [(w, c) for w, c in cands if w not in body]
    miss_gloss = [(w, 0) for w, _ in cands if w in body and w not in gloss]

    print("中德对照检查：%s" % os.path.basename(md_path))
    print("=" * 56)
    print("源材料术语候选 %d 个（出现 ≥%d 次）" % (len(cands), minfreq))
    if miss_body:
        print("\n① 源材料有、正文没提（%d）：" % len(miss_body))
        print("   " + "、".join("%s(%d)" % (w, c) for w, c in miss_body[:20]))
    else:
        print("\n① 源材料术语正文全覆盖 ✓")
    if miss_gloss:
        print("\n② 正文有、术语表没收录（%d）：" % len(miss_gloss))
        print("   " + "、".join(w for w, _ in miss_gloss[:20]))
    else:
        print("② 正文术语术语表全覆盖 ✓")
    print("\n提示：基础词（电阻/电容/电压）不必进表；只补真正的专业术语。")


if __name__ == "__main__":
    main()
