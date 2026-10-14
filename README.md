# lecture-notes-builder

课程详解笔记流水线 —— 把「讲义 PDF + 课堂幻灯片 PDF」自动加工成结构化中文学习笔记（Markdown）与可编辑公式 Word 文档。

为「外教课听不懂、讲义是德语/英语原文」的场景设计：AI 解析 Skript 与 Folien，按讲义自身的叙述顺序撰写中文详解（含 LaTeX 公式、原版配图、例题逐步推导），最终通过 pandoc 产出公式可双击编辑的原生 .docx。最初为 USST Elektrotechnik II 课程工作流而建，但适用于任何"讲义 PDF + 幻灯片 PDF"形态的大学课程。

> 示例产出：458–822 行/章的中文详解、每章 11–15 张从原 PDF 精裁的教师原图、24–30 个公式块，docx 中全部为原生 OMML 公式。

## ✨ 特性

- **多轮工作流**：第一轮凭 Skript 生成 v1 自学版 → 上课后按「补 / 改 / 删」三前缀语义增量修订 → Folien 发布后补充课堂版内容，笔记越修越准而不是越修越厚
- **原图裁取**：课程配图一律用 `pdftoppm` + Pillow 从源 PDF 裁教师原图（行带分析 + 颜色检测两种定位手段），禁止 AI 手绘电路图
- **严格排版自检**：`$`/`$$` 定界符逐行奇偶校验、公式块内禁空行、禁 Unicode 下标、图片引用存在性校验
- **目录锚点脚本生成**：中德混排标题的 slug 用 github-slugger 规则自动生成并校验，杜绝手写错链
- **原生 Word 公式**：pandoc 3.9（pypandoc-binary 自带）转换 + python-docx 后处理，公式为可编辑 OMML，目录用自动域
- **讲解深度三档**：标准档 / 深入档（来龙去脉不跳步）/ 吃透档（常见错误 + 自测题 + 术语词源），可按小节混用

## 📦 安装

把整个文件夹复制到 WorkBuddy / CodeBuddy 的用户级技能目录：

```bash
# Windows
cp -r lecture-notes-builder ~/.workbuddy/skills/

# macOS / Linux
cp -r lecture-notes-builder ~/.workbuddy/skills/
```

依赖（一次性）：

```bash
pip install pypandoc-binary python-docx
```

`pdftoppm` 优先用 MikTeX 自带的（Windows 常见路径 `D:\program file\MikTex\miktex\bin\x64\`），也可安装 Poppler。

## 🚀 用法

对 AI 助手说人话即可触发，例如：

- 「根据 Skript 第 3 章做详解」（Skript 版；Folien 没发布也能先做）
- 「Folien 出了，补进第 2 章」（更新模式：裁 PPT 原图、增补课堂内容）
- 「补：老师今天说了 XXX」「改：这个公式换个讲法」「删：这段不考」（课上修订）
- 「§4 标准档，§6 吃透档」（深度档位）
- 「导出 Word」（唯一一次 docx 构建时机，需明确拍板）

详细工作流见 [SKILL.md](SKILL.md)。

## 📁 结构

```
lecture-notes-builder/
├── SKILL.md                  # 技能主文档：六阶段流程 + 行文规范 + 公式规则
├── references/
│   └── pitfalls.md           # 实战坑清单（本 skill 一半的核心价值）
└── scripts/
    ├── extract_figures.py    # PDF 配图裁剪（行带分析 / 颜色检测）
    └── md_to_docx.py         # 自检 --check-only / 目录修复 --fix-toc / docx 构建
```

## ⚠️ 说明

- 本 skill 只处理**用户自己拥有使用权的课程材料**（讲义、幻灯片），裁图仅用于个人学习笔记，不含也不分发任何受版权保护的课程原文。
- Windows + Git Bash 环境调教出来的（pdftoppm 路径风格、中文标题 slug 等），macOS/Linux 大体可用但未逐一验证。

## 📄 License

[MIT](LICENSE)
