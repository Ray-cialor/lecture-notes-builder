#!/usr/bin/env node
/**
 * 阶段 4 附加检查：把笔记里所有 $...$ / $$...$$ 交给 KaTeX 真渲染一遍。
 *
 * 为什么需要它：md_to_docx.py --check-only 只验 `$` 是否配平，验不了 LaTeX
 * 语法。`\lvert` 写错、`\underbrace` 少了花括号、用了 KaTeX 不认的命令
 * 这类问题只有真渲染才暴露（pandoc 遇错会静默降级成纯文本）。
 *
 * 注意分工：公式里混进表格行、`$|S|$` 被竖线切成两半，属于结构问题，
 * 由 md_to_docx.py --check-only 负责；本脚本只管公式本身合不合法。
 * 两者都要跑。
 *
 * 用法：
 *   node katex_check.js 笔记.md
 *
 * 依赖：katex（npm i katex，或用环境变量 KATEX_PATH 指向已安装目录）。
 * 找不到 katex 时脚本以 exit 3 退出并给出提示（不阻塞流程）。
 */
const fs = require('fs');
const path = require('path');

function loadKatex() {
  const cands = [];
  if (process.env.KATEX_PATH) cands.push(process.env.KATEX_PATH);
  cands.push('katex');
  cands.push(path.join(process.env.USERPROFILE || process.env.HOME || '', '.workbuddy/binaries/node/workspace/node_modules/katex'));
  for (const c of cands) {
    try { return require(c); } catch (e) { /* 继续试下一个 */ }
  }
  return null;
}

const katex = loadKatex();
if (!katex) {
  console.error('找不到 katex 模块：npm i katex，或设 KATEX_PATH 指向安装目录。');
  process.exit(3);
}

const file = process.argv[2];
if (!file) {
  console.error('用法：node katex_check.js 笔记.md');
  process.exit(2);
}

let md = fs.readFileSync(file, 'utf8');
// 先剔掉围栏代码块，避免把代码里的 $ 当成公式
md = md.replace(/```[\s\S]*?```/g, m => m.replace(/[^\n]/g, ' '));

const blocks = [];
let m;
const reDisplay = /\$\$([\s\S]+?)\$\$/g;
while ((m = reDisplay.exec(md))) blocks.push({ display: true, tex: m[1] });
const rest = md.replace(reDisplay, ' ');
const reInline = /\$([^$\n]+?)\$/g;
while ((m = reInline.exec(rest))) blocks.push({ display: false, tex: m[1] });

let fails = 0;
for (const b of blocks) {
  try {
    katex.renderToString(b.tex, { displayMode: b.display, throwOnError: true, strict: false });
  } catch (e) {
    fails++;
    const line = md.slice(0, md.indexOf(b.tex)).split('\n').length;
    console.log(`[公式错误] 约第 ${line} 行 <${b.display ? 'display' : 'inline'}>`);
    console.log('  ' + b.tex.replace(/\s+/g, ' ').slice(0, 100));
    console.log('  -> ' + e.message.split('\n')[0]);
  }
}
console.log(`KaTeX 校验：${blocks.length} 个公式，失败 ${fails} 个`);
process.exit(fails ? 1 : 0);
