
(function(){
  console.log("HMS_UNIFIED SMART UI (Phase 2)");

  const state = { cat: null, categories: [] };

  async function fetchJSON(url){
    const r = await fetch(url);
    return await r.json();
  }

  function el(tag, cls, txt){
    const e = document.createElement(tag);
    if(cls) e.className = cls;
    if(txt) e.textContent = txt;
    return e;
  }

  function drawChart(byCat){
    const canvas = document.getElementById('chart');
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    const keys = Object.keys(byCat);
    const vals = keys.map(k=>byCat[k]);
    const W = canvas.width; const H = canvas.height;
    ctx.clearRect(0,0,W,H);
    const max = Math.max(1, ...vals);
    const barW = Math.max(12, Math.floor(W / (keys.length*1.5)));
    let x = 10;
    ctx.font = '12px system-ui';
    for(let i=0;i<keys.length;i++){
      const h = Math.round((vals[i]/max) * (H-40));
      ctx.fillStyle = '#22d3ee';
      ctx.fillRect(x, H-20-h, barW, h);
      ctx.fillStyle = '#9ca3af';
      ctx.fillText(keys[i], x, H-6);
      x += barW + 10;
    }
  }

  function renderPills(){
    const bar = document.getElementById('cat-bar');
    bar.innerHTML = '';
    state.categories.forEach(c=>{
      const p = el('button', 'pill'+(state.cat===c.code?' active':''), c.name);
      p.onclick = ()=>{ state.cat = c.code; renderPills(); loadFeed(); };
      bar.appendChild(p);
    });
  }

  function renderFeed(items){
    const feed = document.getElementById('feed');
    feed.innerHTML='';
    if(!items || items.length===0){
      const empty = el('div','feed-item','لا توجد بيانات بعد');
      feed.appendChild(empty);
      return;
    }
    items.forEach(it=>{
      const card = el('div','feed-item');
      const title = el('div','title', it.title);
      const meta = el('div','meta', `${it.category} · ${it.status} · ${it.created_at}`);
      card.appendChild(title); card.appendChild(meta);
      if(it.description){
        const desc = el('div','desc', it.description);
        card.appendChild(desc);
      }
      feed.appendChild(card);
    });
  }

  async function loadCats(){
    const j = await fetchJSON('/api/categories');
    state.categories = j.categories || [];
    if(!state.cat && state.categories.length>0){ state.cat = state.categories[0].code; }
    renderPills();
  }

  async function loadKPIs(){
    const j = await fetchJSON('/api/stats');
    document.getElementById('kpi-total').textContent = j.total;
    document.getElementById('kpi-open').textContent = j.open;
    document.getElementById('kpi-closed').textContent = j.closed;
    drawChart(j.by_category||{});
  }

  async function loadFeed(){
    const url = state.cat ? `/api/records?category=${encodeURIComponent(state.cat)}` : '/api/records';
    const j = await fetchJSON(url);
    renderFeed(j.records||[]);
  }

  (async function init(){
    await loadCats();
    await loadKPIs();
    await loadFeed();
  })();
})();
