'use strict';
// En Windows/Linux muestra los atajos como «Ctrl+C» en lugar de «⌘C» (los textos se escriben pensando en Mac).

(function () {
  if (/Mac|iPhone|iPad/.test(navigator.platform)) return;
  const fix = s => s.replace(/⌘(\w) \/ Ctrl\+\1/g, 'Ctrl+$1').replace(/⇧⌘/g, 'Ctrl+Mayús+').replace(/⌘\s*\+\s*/g, 'Ctrl+').replace(/⌘/g, 'Ctrl+');
  const ATTRS = ['title', 'placeholder', 'aria-label'];
  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (node.data.includes('⌘')) node.data = fix(node.data);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    for (const a of ATTRS) {
      const v = node.getAttribute(a);
      if (v && v.includes('⌘')) node.setAttribute(a, fix(v));
    }
    for (const c of node.childNodes) walk(c);
  }
  walk(document.body);
  new MutationObserver(muts => {
    for (const m of muts) {
      if (m.type === 'characterData') walk(m.target);
      else if (m.type === 'attributes') walk(m.target);
      else m.addedNodes.forEach(walk);
    }
  }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
})();
