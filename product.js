// 产品定义页：标签切换 + SoC 选型高亮 + 哈希路由
(function () {
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const panes = {
    brief: document.getElementById('pane-brief'),
    hw: document.getElementById('pane-hw'),
    sw: document.getElementById('pane-sw'),
    plan: document.getElementById('pane-plan'),
  };

  function activate(name) {
    if (!panes[name]) return;
    tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === name));
    Object.entries(panes).forEach(([key, node]) => node.classList.toggle('active', key === name));
    if (window.location.hash !== '#' + name) {
      history.replaceState(null, '', '#' + name);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  tabs.forEach((tab) => tab.addEventListener('click', () => activate(tab.dataset.tab)));

  // SoC 行点击：高亮 + 在标题上给出当前选择
  const table = document.getElementById('socTable');
  if (table) {
    table.addEventListener('click', (event) => {
      const row = event.target.closest('tr[data-soc]');
      if (!row) return;
      table.querySelectorAll('tr[data-soc]').forEach((tr) => {
        tr.style.background = tr === row ? 'rgba(76,141,255,.12)' : '';
      });
      const name = row.querySelector('td').textContent;
      const conclusion = row.querySelector('td.pick')?.textContent || '';
      const note = table.parentElement.querySelector('.note');
      if (note) {
        note.textContent = `当前选择：${name}${conclusion ? '（' + conclusion + '）' : ''} · 软件栈不变，换的是硬件平台与多屏能力。`;
      }
    });
  }

  const initial = (window.location.hash || '#brief').slice(1);
  activate(panes[initial] ? initial : 'brief');
})();
