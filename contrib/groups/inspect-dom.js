// Inspect the DOM structure of the last message section
const sections = document.querySelectorAll('div > section');
const last = sections[sections.length - 1];

const info = [];
const walk = (el, depth) => {
  if (depth > 6) return;
  const tag = el.tagName.toLowerCase();
  const cls = (typeof el.className === 'string' && el.className)
    ? '.' + el.className.split(/\s+/).join('.') : '';
  const jsname = el.getAttribute?.('jsname') || '';
  const text = el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
    ? el.textContent.trim().substring(0, 80) : '';
  info.push(`${'  '.repeat(depth)}${tag}${cls}${jsname ? ` [jsname=${jsname}]` : ''}${text ? ` "${text}"` : ''}`);
  for (const child of el.children) walk(child, depth + 1);
};
walk(last, 0);
info.join('\n');
