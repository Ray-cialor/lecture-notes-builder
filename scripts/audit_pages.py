#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""逐页覆盖审计：PPT 有 N 页，笔记提到了哪些？

用法：
    python audit_pages.py 笔记.md --pages 4-50
    python audit_pages.py 笔记.md --pages 4-50 --ignore 7,18,33

识别 `Folie 3`、`Folie 3–5`、`Folie 3-5` 三种写法；区间展开后逐页比对。
`--ignore` 用来跳过纯标题的分隔页——不排除的话"未覆盖页=0"永远达不到。
"""
import io
import re
import sys


def parse_pages(spec):
    a, _, b = spec.partition("-")
    return int(a), int(b or a)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    if "--pages" not in sys.argv:
        print("缺 --pages A-B")
        return
    lo, hi = parse_pages(sys.argv[sys.argv.index("--pages") + 1])
    ignore = set()
    if "--ignore" in sys.argv:
        ignore = {int(x) for x in sys.argv[sys.argv.index("--ignore") + 1].split(",") if x.strip()}

    s = io.open(path, encoding="utf-8").read()
    hit = set()
    for m in re.finditer(r"Folie\s*(\d+)(?:\s*[–\-]\s*(\d+))?", s):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        for k in range(a, b + 1):
            hit.add(k)

    pages = set(range(lo, hi + 1)) - ignore
    covered = pages & hit
    miss = sorted(pages - hit)

    print("覆盖审计：%s" % path)
    print("=" * 50)
    print("页码范围 %d–%d，排除 %s，共 %d 页" % (
        lo, hi, ("%、".join(map(str, sorted(ignore))) if ignore else "无"), len(pages)))
    print("提到 %d 页，未提到 %d 页" % (len(covered), len(miss)))
    if miss:
        print("未覆盖：%s" % "、".join(map(str, miss)))
        print("→ 逐页核对这几页是漏写，还是该加进 --ignore（分隔页/空白页）。")
    else:
        print("✓ 未覆盖 0 页")
    out_of_range = sorted(p for p in hit if p < lo or p > hi)
    if out_of_range:
        print("⚠ 正文提到超出范围的页号：%s（检查是否标错）" % "、".join(map(str, out_of_range)))


if __name__ == "__main__":
    main()
