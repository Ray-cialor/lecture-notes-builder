# -*- coding: utf-8 -*-
"""md 笔记 → Word 文档（课程详解笔记流水线 · 阶段 4/5/6）

用法：
  python md_to_docx.py --check-only 笔记.md          # 阶段4：只自检 md
  python md_to_docx.py 笔记.md 输出.docx             # 阶段5+6：构建并校验

依赖：pip install pypandoc-binary python-docx（pypandoc-binary 自带 pandoc 3.9）
"""
import os, re, sys, tempfile

# ---------- 阶段 4：md 自检 ----------
def strip_row(line):
    """把 Markdown 表格行拆成单元格（去掉首尾竖线）。"""
    t = line.strip()
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|"):
        t = t[:-1]
    return t.split("|")


def check_md(path):
    errors, warns = [], []
    s = open(path, encoding="utf-8").read()
    lines = s.split("\n")
    # 1) 行内 $ 成对
    for i, l in enumerate(lines, 1):
        if "$$" in l:
            if l.strip() != "$$":
                errors.append(f"L{i}: 单行内混排 $$ 与文字/公式：{l.strip()[:60]}")
            continue
        if (l.count("$")) % 2 != 0:
            errors.append(f"L{i}: 行内 $ 不成对：{l.strip()[:60]}")
    # 2) $$ 块内部空行 / 前后空行
    in_math = False
    for i, l in enumerate(lines, 1):
        if l.strip() == "$$":
            if in_math:
                in_math = False
                if i < len(lines) and lines[i].strip() != "":
                    warns.append(f"L{i+1}: $$ 块后建议留一个空行")
            else:
                in_math = True
                if out := (i >= 2 and lines[i - 2].strip() != ""):
                    warns.append(f"L{i}: $$ 块前建议留一个空行")
        elif in_math and l.strip() == "":
            errors.append(f"L{i}: $$ 公式块内部出现空行（pandoc 会解析失败）")
    # 3) Unicode 下标 / HTML
    for i, l in enumerate(lines, 1):
        if re.search(r"[₀₁₂₃₄ᵢₙ]", l):
            errors.append(f"L{i}: 使用了 Unicode 下标字符（中文字体缺字形）：{l.strip()[:50]}")
        if re.search(r"<img|<p align", l, re.I):
            errors.append(f"L{i}: 出现 HTML 标签（预览器会过滤，改用 Markdown 图片语法）")
    # 4) assets 引用存在
    for m in re.finditer(r"!\[[^\]]*\]\((assets/[^)]+)\)", s):
        if not os.path.exists(m.group(1)):
            errors.append(f"图片不存在：{m.group(1)}")
    # 4.5) 锚点链接校验：slug 必须与实际标题的 slug 一致（github-slugger 规则）
    heading_slugs = {slug_of(l) for l in lines if re.match(r"^##+\s", l)}
    for i, l in enumerate(lines, 1):
        for m in re.finditer(r"\]\(#([^)]+)\)", l):
            if m.group(1) not in heading_slugs:
                errors.append(f"L{i}: 锚点 #{m.group(1)} 与任何标题的 slug 不匹配（用 --fix-toc 重新生成）")
    # 5) $$ 块内禁止 Markdown 表格语法（pandoc 会把表格当成公式内容 → 整块渲染失败）
    #    注意：`|\bar{u}| = ...` 这种绝对值开头的公式不是表格，表格行必须首尾都是 `|`
    in_math = False
    for i, l in enumerate(lines, 1):
        if l.strip() == "$$":
            in_math = not in_math
            continue
        t = l.strip()
        is_sep = re.match(r"^\|(\s*:?-{3,}:?\s*\|)+$", t) is not None
        is_row = t.startswith("|") and t.endswith("|") and t.count("|") >= 2
        if in_math and (is_sep or is_row):
            errors.append(f"L{i}: $$ 公式块内出现表格语法：{t[:50]}（表格必须写在 $$ 之外）")
    # 5.5) 正文行禁止出现裸竖线：部分渲染器会把整行按 | 切成一格格的"伪表格"
    #      典型事故：$Z = |\underline{Z}|$、$|\bar{u}|$、图片 alt 里的 |ū|
    in_math = False
    for i, l in enumerate(lines, 1):
        if l.strip() == "$$":
            in_math = not in_math
            continue
        if in_math or "|" not in l:
            continue
        t = l.strip()
        if t.startswith("|") or (t.startswith(">") and t[1:].strip().startswith("|")):
            continue
        errors.append(
            f"L{i}: 正文行含竖线，可能被渲染成表格：{t[:50]}"
            "（绝对值请写 \\lvert…\\rvert；标题/alt 里改用文字）"
        )
    # 6) 表格结构：表头非空、列数一致、单元格内 $ 成对（$|S|$ 被竖线切断是经典事故）
    block, start = [], 0
    for i, l in enumerate(lines + [""], 1):
        if l.strip().startswith("|"):
            if not block:
                start = i
            block.append((i, l))
            continue
        if block:
            if len(block) >= 2:
                head = strip_row(block[0][1])
                ncol = len(head)
                if not any(c.strip() for c in head):
                    errors.append(f"L{start}: 表头为空（多半是改稿残留的空表）：{block[0][1].strip()[:40]}")
                for ln, t in block:
                    cells = strip_row(t)
                    if len(cells) != ncol:
                        errors.append(f"L{ln}: 表格列数不一致（表头 {ncol} 列、本行 {len(cells)} 列）")
                    for k, c in enumerate(cells):
                        if c.count("$") % 2:
                            errors.append(f"L{ln} 第{k+1}格: 单元格内 $ 不成对（常见于 $|S|$ 被竖线切断 → 改 \\lvert\\rvert 或挪出表格）")
            block = []
    # 7) 偏好检查（警告级；换课程/换人时可按项目覆盖）
    exam_at = next((k for k, l in enumerate(lines) if l.strip().startswith("## 备考清单")), len(lines))
    for i, l in enumerate(lines[:exam_at], 1):
        if "**考点**" in l or re.match(r"^\s*考点[：:]", l):
            warns.append(f"L{i}: 正文出现「考点：」（偏好：考试提示一律收进文末《备考清单》）")
    if "德语" in s:
        warns.append(f"全文出现「德语」{s.count('德语')} 处（偏好：德文词前不加这两个字，直接给原词）")
    n_h2 = sum(1 for l in lines if re.match(r"^##\s", l))
    n_h3 = sum(1 for l in lines if re.match(r"^###\s", l))
    if n_h2 >= 3 and n_h3 == 0:
        warns.append("全文没有 ### 小标题：长节会失去分步提示（长章每 10–15 个正文段落配一个内容型 ### 较合适）")
    # 8) 统计
    blocks = sum(1 for i, l in enumerate(lines) if l.strip() == "$$") // 2
    print(f"$$ 显示公式块: {blocks}  行内公式对: {s.count('$')//1 - 0}  标题: ## {n_h2} / ### {n_h3}")
    for e in errors: print("[错误]", e)
    for w in warns: print("[建议]", w)
    return errors


# ---------- 阶段 5.5：行内公式轻量化（可读性核心） ----------
MNS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def _omath_parts(el):
    """解析简单行内 OMML → [(text, is_sub)]。含分数/矩阵/括号匹配等复杂结构时返回 None。"""
    parts = []
    for ch in el:
        tag = ch.tag
        if tag.endswith("}Pr"):
            continue
        if tag == MNS + "r":
            t = "".join(t.text or "" for t in ch.iter(MNS + "t"))
            parts.append((t, False))
        elif tag in (MNS + "sSub", MNS + "sSup"):
            e = ch.find(MNS + "e")
            s = ch.find(MNS + "sub") if tag.endswith("Sub") else ch.find(MNS + "sup")
            if e is None or s is None:
                return None
            # 基底/上下标内部若再嵌套结构则放弃
            if e.find(MNS + "sSub") is not None or e.find(MNS + "sSup") is not None:
                return None
            bt = "".join(t.text or "" for t in e.iter(MNS + "t"))
            st = "".join(t.text or "" for t in s.iter(MNS + "t"))
            if not st:
                return None
            parts.append((bt, False)); parts.append((st, True))
        else:
            return None
    text = "".join(t for t, _ in parts)
    if not text.strip() or len(text) > 48 or len(parts) > 14:
        return None
    return parts

def _make_run(text, sub=False, sup=False):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    r = OxmlElement("w:r")
    if sub or sup:
        rpr = OxmlElement("w:rPr")
        va = OxmlElement("w:vertAlign")
        va.set(qn("w:val"), "subscript" if sub else "superscript")
        rpr.append(va); r.append(rpr)
    t = OxmlElement("w:t"); t.set(qn("xml:space"), "preserve"); t.text = text
    r.append(t)
    return r

def lighten_inline_math(doc):
    """把简单行内公式（符号+上下标）降级为带真下标/上标的文本运行，提升可读性。
    独立公式（oMathPara 内）与复杂结构（分数/矩阵/根号）保持 OMML。"""
    n_ok = n_keep = 0
    for p in doc.element.body.iter(WNS + "p"):
        for om in list(p.iter(MNS + "oMath")):
            if om.getparent().tag == MNS + "oMathPara":
                continue  # 独立公式保持原样
            parts = _omath_parts(om)
            if parts is None:
                n_keep += 1; continue
            parent = om.getparent()
            idx = list(parent).index(om)
            for k, (txt, is_sub) in enumerate(parts):
                if txt == "":
                    continue
                parent.insert(idx + k, _make_run(txt, sub=is_sub))
            parent.remove(om); n_ok += 1
    return n_ok, n_keep

def style_tables(doc):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    for t in doc.tables:
        tblPr = t._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement("w:" + edge)
            e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), "A6A6A6")
            borders.append(e)
        tblPr.append(borders)
        for ri, row in enumerate(t.rows[:1]):
            for c in row.cells:
                tcPr = c._tc.get_or_add_tcPr()
                sh = OxmlElement("w:shd")
                sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), "DCE6F1")
                tcPr.append(sh)



# ---------- 目录锚点（github-slugger 规则） ----------
import unicodedata
def slug_of(heading_line):
    t = re.sub(r"^#+\s*", "", heading_line.strip()).lower()
    out = []
    for ch in t:
        if ch == " ":
            out.append("-")
        elif ch == "-" or ch == "_" or unicodedata.category(ch)[0] in ("L", "N"):
            out.append(ch)
    return "".join(out)

def fix_toc(path, depth=2):
    lines = open(path, encoding="utf-8").read().split("\n")
    depth = max(2, min(int(depth), 4))
    pat = r"^#{2,%d}\s" % depth
    heads = [l for l in lines if re.match(pat, l) and l.strip() != "## 目录"]
    entries = "\n".join(f"- [{h.lstrip('# ')}](#{slug_of(h)})" for h in heads)
    new_toc = "## 目录\n\n" + entries + "\n"
    # 替换既有目录段（## 目录 到其后第一个非列表行）
    i = next((k for k, l in enumerate(lines) if l.strip() == "## 目录"), None)
    if i is None:
        raise SystemExit("未找到 '## 目录' 段")
    j = i + 1
    while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith("- ")):
        j += 1
    lines[i:j] = new_toc.split("\n")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"目录已重建：{len(heads)} 个条目（slug 自动生成）")

# ---------- 阶段 5：构建 ----------
def build(md_path, out_path):
    import pypandoc
    WIDTHS = {}  # 可选：特定图名手工指定宽度(cm)；缺省全部按像素自动定宽
    s = open(md_path, encoding="utf-8").read()

    def im(m):
        alt, path = m.group(1), m.group(2)
        name = os.path.basename(path)
        if name in WIDTHS:
            w = WIDTHS[name]
        else:
            # 自动定宽：按像素宽度换算，钳制在 6-15cm
            from PIL import Image as _Image
            px = _Image.open(path).width
            w = str(min(15, max(6, round(px / 100))))
        return f"![{alt}]({path}){{width={w}cm}}"
    s = re.sub(r"!\[([^\]]*)\]\((assets/[^)]+)\)", im, s)
    s = s.replace("# " + os.path.splitext(os.path.basename(md_path))[0] + "\n", "", 1) \
        if s.startswith("# ") else s
    s = re.sub(r"^# [^\n]+\n", "", s, count=1)
    s = ("% 学习笔记（课程详解流水线生成）\n\n") + s
    s = re.sub(r"## 目录\n\n(?:- \[[^\]]+\]\([^)]+\)\n)+\n---\n", "", s, count=1)

    with tempfile.TemporaryDirectory() as td:
        b = os.path.join(td, "build.md")
        open(b, "w", encoding="utf-8").write(s)
        pypandoc.convert_file(b, "docx", outputfile=out_path, format="markdown",
                              extra_args=["--toc", "--toc-depth=3", "--standalone",
                                          f"--resource-path={os.path.dirname(os.path.abspath(md_path))}"])

    # ---------- 后处理 ----------
    import docx
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    doc = docx.Document(out_path)

    def set_font(style, latin, ea, size=None):
        f = style.font; f.name = latin
        if size: f.size = Pt(size)
        rpr = style.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts"); rpr.append(rf)
        rf.set(qn("w:ascii"), latin); rf.set(qn("w:hAnsi"), latin); rf.set(qn("w:eastAsia"), ea)

    set_font(doc.styles["Normal"], "Calibri", "宋体", 11)
    for nm, sz in [("Heading 1", 17), ("Heading 2", 14), ("Heading 3", 12), ("Heading 4", 11)]:
        try: set_font(doc.styles[nm], "Calibri", "微软雅黑", sz)
        except KeyError: pass
    for nm in ["Body Text", "First Paragraph", "Compact"]:
        try: set_font(doc.styles[nm], "Calibri", "宋体", 10.5 if nm == "Compact" else 11)
        except KeyError: pass
    try: set_font(doc.styles["Image Caption"], "Calibri", "宋体", 9)
    except KeyError: pass
    pf = doc.styles["Normal"].paragraph_format
    pf.line_spacing = 1.3; pf.space_after = Pt(6)

    for t in doc.tables:
        for ri, row in enumerate(t.rows):
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9.5)
                        if ri == 0: r.font.bold = True

    n = 0
    for p in doc.paragraphs:
        if p._p.findall(".//" + qn("w:drawing")):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER; n += 1

    body = doc.element.body; prev_empty = False
    for el in list(body):
        if el.tag == qn("w:p"):
            txt = "".join(el.itertext()).strip()
            if txt == "" and not el.findall(".//" + qn("w:drawing")):
                if prev_empty: body.remove(el)
                prev_empty = True; continue
        prev_empty = False

    fp = doc.sections[0].footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin"); r1._r.append(f1)
    it = OxmlElement("w:instrText"); it.text = " PAGE "; r1._r.append(it)
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end"); r1._r.append(f2)
    r2 = fp.add_run(" / ")
    f3 = OxmlElement("w:fldChar"); f3.set(qn("w:fldCharType"), "begin"); r2._r.append(f3)
    it2 = OxmlElement("w:instrText"); it2.text = " NUMPAGES "; r2._r.append(it2)
    f4 = OxmlElement("w:fldChar"); f4.set(qn("w:fldCharType"), "end"); r2._r.append(f4)
    for r in fp.runs: r.font.size = Pt(9)
    for s_ in doc.sections:
        s_.left_margin = s_.right_margin = Cm(2.2)
        s_.top_margin = s_.bottom_margin = Cm(2.0)
    n_ok, n_keep = lighten_inline_math(doc)
    style_tables(doc)
    doc.save(out_path)
    print(f"行内公式轻量化: 转换 {n_ok} 处, 保留 OMML {n_keep} 处")

# ---------- 阶段 6：校验 ----------
def validate_docx(out_path, md_path):
    import zipfile, docx
    z = zipfile.ZipFile(out_path); xml = z.read("word/document.xml").decode("utf-8")
    md = open(md_path, encoding="utf-8").read()
    blocks = sum(1 for l in md.split("\n") if l.strip() == "$$") // 2
    imgs_md = len(re.findall(r"!\[[^\]]*\]\(assets/", md))
    imgs_doc = len([n for n in z.namelist() if n.startswith("word/media/")])
    omathpara = xml.count("<m:oMathPara>")  # 精确匹配，排除 <m:oMathParaPr>
    d = docx.Document(out_path)
    broken = [pp.text[:50] for pp in d.paragraphs if "$$" in pp.text or re.match(r"^\s*\w+_\w+ =", pp.text)]
    print(f"显示公式块: md={blocks} docx={omathpara} {'✓' if blocks == omathpara else '✗ 不一致!'}")
    print(f"图片: md={imgs_md} docx={imgs_doc} {'✓' if imgs_md == imgs_doc else '✗ 不一致!'}")
    print(f"表格: {xml.count('<w:tbl>')}  TOC 域: {'TOC' in xml}")
    if broken:
        print("✗ 疑似损坏公式段落:", broken)
    else:
        print("✓ 无字面 $$ / 损坏公式残留")
    return not broken and blocks == omathpara and imgs_md == imgs_doc

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--fix-toc" in sys.argv:
        depth = 2
        if "--depth" in sys.argv:
            depth = int(sys.argv[sys.argv.index("--depth") + 1])
        fix_toc(args[0], depth); sys.exit(0)
    if "--check-only" in sys.argv:
        errs = check_md(args[0])
        sys.exit(1 if errs else 0)
    if len(args) < 2:
        raise SystemExit(__doc__)
    md, out = args[0], args[1]
    errs = check_md(md)
    if errs:
        raise SystemExit("md 自检未通过，先修复再构建")
    build(md, out)
    ok = validate_docx(out, md)
    print("docx 构建完成:", os.path.abspath(out))
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
