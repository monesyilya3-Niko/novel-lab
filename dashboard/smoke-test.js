// 冒烟测试：dashboard/index.html
// 验证无 JS 运行时错误 + 核心渲染区块数据非空 + 书籍切换交互
const fs = require('fs');
const path = require('path');
// jsdom 加载：优先运行时解析，失败回退仓库内 gui/web 的 devDependency；
// 两者都不可用时给出明确提示并退出（不依赖任何外部绝对路径）。
let JSDOM, VirtualConsole;
try {
  ({ JSDOM, VirtualConsole } = require('jsdom'));
} catch (e) {
  try {
    ({ JSDOM, VirtualConsole } = require(
      path.join(__dirname, '..', 'gui', 'web', 'node_modules', 'jsdom')));
  } catch (e2) {
    console.error('❌ 无法加载 jsdom：运行时未解析到，仓库内 gui/web/node_modules/jsdom 也不存在。');
    console.error('   请先安装前端依赖：npm --prefix gui/web install');
    process.exit(2);
  }
}

// 只读取脚本自身所在目录（dashboard/），不依赖任何外部绝对路径。
const BASE = __dirname;
const html = fs.readFileSync(path.join(BASE, 'index.html'), 'utf8');
const dataJs = fs.readFileSync(path.join(BASE, 'dashboard-data.js'), 'utf8');

const errs = [];
let ok = 0, bad = 0;
const chk = (c, name, extra) => c ? (ok++, console.log('  ✅ ' + name))
                                    : (bad++, console.log('  ❌ ' + name + (extra ? ' → ' + extra : '')));

// 在 html 中注入 dashboard-data.js（jsdom 不会自动加载外部 script）
const htmlWithData = html.replace(
  '<script src="./dashboard-data.js"></script>',
  '<script>' + dataJs + '</script>'
);

const vc = new VirtualConsole();
vc.on('jsdomError', e => errs.push('jsdomError: ' + (e.detail || e.message)));
vc.on('error', (...a) => errs.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(htmlWithData, {
  runScripts: 'dangerously',
  url: 'http://localhost/',
  virtualConsole: vc,
  pretendToBeVisual: true,
});
const w = dom.window;
w.Element.prototype.scrollIntoView = function () {};
w.scrollTo = function () {};
w.URL.createObjectURL = () => 'blob:x';
w.URL.revokeObjectURL = () => {};

// 派发 DOMContentLoaded（脚本是 IIFE，同步执行）
w.document.dispatchEvent(new w.Event('DOMContentLoaded', { bubbles: true }));

const d = w.document;
const $ = (id) => d.getElementById(id);
const txt = (el) => (el ? el.textContent.trim() : '');

console.log('=== 冷启动渲染检查 ===');
chk(errs.length === 0, '无运行时 JS 错误', errs.join(' | '));

// 统计卡片
const statCards = d.querySelectorAll('#stats .stat');
chk(statCards.length === 6, '概览统计卡片 6 张', '实际 ' + statCards.length);

// 书籍 tabs
const tabs = d.querySelectorAll('#tabs .tab');
chk(tabs.length === 4, '书籍切换 tab 4 个', '实际 ' + tabs.length);
chk(tabs.length > 0 && tabs[0].classList.contains('active'), '默认选中第一本书');

// 书籍档案
chk($('book-profile') && $('book-profile').innerHTML.trim().length > 0, '书籍档案渲染非空');
chk(txt($('nav-genre')).includes('校园救赎'), '题材名正确显示');

// 声线卡（负空间三字段）
const bannedWords = d.querySelectorAll('#voice-card .tag.red');
chk(bannedWords.length > 0, '禁用词渲染', '实际 ' + bannedWords.length + ' 词');

// 笔法卡
const dimItems = d.querySelectorAll('#craft-card .dim-item');
chk(dimItems.length === 10, '笔法卡 10 个技法维度', '实际 ' + dimItems.length);

// 结构观察
chk($('structure-obs') && $('structure-obs').innerHTML.trim().length > 0, '结构观察渲染非空');

// 商业观察
chk($('commercial-obs') && $('commercial-obs').innerHTML.trim().length > 0, '商业观察渲染非空');

// 题材包
chk($('genre-pack') && $('genre-pack').innerHTML.trim().length > 0, '题材包渲染非空');
const ironRules = d.querySelectorAll('#genre-pack .tech');
chk(ironRules.length > 0, '语言铁律渲染', '实际 ' + ironRules.length + ' 条');

// 蒸馏层
chk($('distilled') && $('distilled').innerHTML.trim().length > 0, '蒸馏规则渲染非空');

// 桥段库
const tropeCards = d.querySelectorAll('#trope-library .trope-card');
chk(tropeCards.length === 8, '桥段库 8 个桥段', '实际 ' + tropeCards.length);

console.log('\n=== 交互检查 ===');

// 切换书籍
const beforeSwitch = errs.length;
const secondTab = tabs[1];
secondTab.click();
const activeAfter = d.querySelector('#tabs .tab.active');
chk(errs.length === beforeSwitch, '切换书籍无新增错误', errs.slice(beforeSwitch).join('|'));
chk(activeAfter && activeAfter.textContent.includes('清宁'), '切换后 tab 状态正确', 'active=' + txt(activeAfter));

// 技法维度折叠展开
const beforeToggle = errs.length;
const firstDimHead = d.querySelector('#craft-card .dim-head');
if (firstDimHead) {
  firstDimHead.click();
  const firstDimItem = d.querySelector('#craft-card .dim-item');
  chk(errs.length === beforeToggle, '展开技法维度无错误', errs.slice(beforeToggle).join('|'));
  chk(firstDimItem && firstDimItem.classList.contains('open'), '技法维度可展开');
  firstDimHead.click(); // 收起
  chk(firstDimItem && !firstDimItem.classList.contains('open'), '技法维度可收起');
}

console.log('\n=== 汇总 ===');
console.log('通过 ' + ok + ' 项 / 失败 ' + bad + ' 项');
if (errs.length) {
  console.log('\n捕获的错误：');
  errs.forEach(e => console.log('  ' + e));
}
process.exit(bad > 0 ? 1 : 0);
