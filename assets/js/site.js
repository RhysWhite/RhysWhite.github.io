(() => {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
    nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      nav.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }));
  }

  const buttons = [...document.querySelectorAll('.filter-btn')];
  const search = document.querySelector('.pub-search');
  const pubs = [...document.querySelectorAll('.pub-item')];
  const empty = document.querySelector('.pub-empty');
  if (pubs.length) {
    let active = 'all';
    const apply = () => {
      const q = (search?.value || '').trim().toLowerCase();
      let shown = 0;
      pubs.forEach(pub => {
        const tags = (pub.dataset.tags || '').split(' ');
        const matchesFilter = active === 'all' || tags.includes(active) || pub.dataset.year === active;
        const matchesSearch = !q || pub.textContent.toLowerCase().includes(q);
        const visible = matchesFilter && matchesSearch;
        pub.hidden = !visible;
        if (visible) shown += 1;
      });
      if (empty) empty.style.display = shown ? 'none' : 'block';
    };
    buttons.forEach(button => button.addEventListener('click', () => {
      active = button.dataset.filter;
      buttons.forEach(b => b.setAttribute('aria-pressed', String(b === button)));
      apply();
    }));
    search?.addEventListener('input', apply);
  }

  document.querySelectorAll('[data-print-cv]').forEach(button => {
    button.addEventListener('click', () => window.print());
  });

  const compactNumber = new Intl.NumberFormat('en-NZ', { notation: 'compact', maximumFractionDigits: 1 });
  const regularNumber = new Intl.NumberFormat('en-NZ');
  const formatMetric = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return String(value ?? '');
    return Math.abs(n) >= 10000 ? compactNumber.format(n) : regularNumber.format(n);
  };

  const impactGroups = [...new Set([...document.querySelectorAll('[data-impact]')].map(el => el.dataset.impact))];
  impactGroups.forEach(async name => {
    try {
      const response = await fetch(`/data/impact/${name}.json`, { cache: 'no-cache' });
      if (!response.ok) return;
      const data = await response.json();
      const metrics = data.metrics || {};
      const targets = [...document.querySelectorAll(`[data-impact="${name}"]`)];
      let populated = 0;
      targets.forEach(group => {
        group.querySelectorAll('[data-metric]').forEach(el => {
          const item = metrics[el.dataset.metric];
          const value = item && typeof item === 'object' ? item.value : item;
          if (value === undefined || value === null || value === '') return;
          el.textContent = formatMetric(value);
          el.closest('div')?.removeAttribute('hidden');
          populated += 1;
        });
        if (populated) group.hidden = false;
      });
      if (populated) {
        document.querySelectorAll(`[data-impact-pending="${name}"]`).forEach(el => el.hidden = true);
      }
      if (data.updated) {
        const d = new Date(data.updated);
        const label = Number.isNaN(d.getTime()) ? data.updated : d.toLocaleDateString('en-NZ', { year: 'numeric', month: 'short' });
        document.querySelectorAll(`[data-impact-updated="${name}"]`).forEach(el => el.textContent = `boast snapshot · ${label}`);
      }
    } catch (_) {
      // Last-known-good static site remains fully usable if a metric fetch fails.
    }
  });

  document.querySelectorAll('[data-year-now]').forEach(el => {
    el.textContent = String(new Date().getFullYear());
  });
})();
