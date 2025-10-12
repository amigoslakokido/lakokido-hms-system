document.addEventListener("DOMContentLoaded", () => {
  // RTL/LTR toggle (عند تبديل اللغة من الروابط العلوية)
  const langLinks = document.querySelectorAll(".lang-switch a");
  langLinks.forEach(link => {
    link.addEventListener("click", () => {
      const lang = link.textContent.trim().toLowerCase();
      document.documentElement.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");
      document.documentElement.lang = lang;
    });
  });

  const menu = document.getElementById("side-menu");
  const feedBody = document.getElementById("feed-table");
  const feedEmpty = document.getElementById("feed-empty");
  const kpiSec = document.getElementById("kpi-sec");
  const kpiReports = document.getElementById("kpi-reports");
  const kpiAvvik = document.getElementById("kpi-avvik");
  const kpiWorkers = document.getElementById("kpi-workers");

  const addBtn = document.getElementById("add-btn");
  const toast = document.getElementById("toast");

  // Modals
  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalBody = document.getElementById("modal-body");
  const modalSave = document.getElementById("modal-save");
  const modalClose = document.getElementById("modal-close");
  const modalCancel = document.getElementById("modal-cancel");

  const detModal = document.getElementById("details-modal");
  const detClose = document.getElementById("details-close");
  const detTitle = document.getElementById("details-title");
  const detBody = document.getElementById("details-body");
  const detEdit = document.getElementById("details-edit");
  const detDelete = document.getElementById("details-delete");

  const genBtn = document.getElementById("gen-btn");
  const genModal = document.getElementById("gen-modal");
  const genClose = document.getElementById("gen-close");
  const genCancel = document.getElementById("gen-cancel");
  const genRun = document.getElementById("gen-run");
  const genCat = document.getElementById("gen-category");
  const genBy  = document.getElementById("gen-by");
  const genResult = document.getElementById("gen-result");

  const schedBtn = document.getElementById("sched-btn");
  const schedModal = document.getElementById("sched-modal");
  const schedClose = document.getElementById("sched-close");
  const schedCancel = document.getElementById("sched-cancel");
  const schedSave = document.getElementById("sched-save");
  const schedEnabled = document.getElementById("sched-enabled");
  const schedWeekday = document.getElementById("sched-weekday");
  const schedHour = document.getElementById("sched-hour");
  const schedMinute = document.getElementById("sched-minute");
  const schedCats = document.getElementById("sched-cats");
  const schedLast = document.getElementById("sched-last");

  const openFolderBtn = document.getElementById("open-folder-btn");

  let currentCategory = "";
  let currentEditingId = null;

  const API = {
    records: (cat="") => fetch(`/api/records${cat?`?category=${encodeURIComponent(cat)}`:""}`).then(r=>r.json()),
    stats:   (cat="") => fetch(`/api/stats${cat?`?category=${encodeURIComponent(cat)}`:""}`).then(r=>r.json()),
    form:    (cat)    => fetch(`/forms/${cat}`).then(r=>r.text()),
    create:  (fd)     => fetch(`/api/create_record`, { method: "POST", body: fd }).then(r=>r.json()),
    details: (id)     => fetch(`/api/record_details/${id}`).then(r=>r.json()),
    update:  (id,fd)  => fetch(`/api/update_record/${id}`, { method:"POST", body: fd }).then(r=>r.json()),
    remove:  (id)     => fetch(`/api/delete_record/${id}`, { method:"POST" }).then(r=>r.json()),
    genReport: (cat, by)  => fetch(`/api/report_generate`, { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify({category:cat, created_by: by||"Admin"}) }).then(r=>r.json()),
    schedGet: ()      => fetch(`/api/report_scheduler`).then(r=>r.json()),
    schedSet: (payload)=> fetch(`/api/report_scheduler`, { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(payload) }).then(r=>r.json())
  };

  function showToast(msg){
    toast.textContent = msg;
    toast.style.display = "block";
    setTimeout(()=>{ toast.style.display="none"; }, 3500);
  }
  function updateKpis(s){
    kpiSec.textContent = s.sikkerhet ?? 0;
    kpiReports.textContent = s.rapporter ?? 0;
    kpiAvvik.textContent = s.avvik ?? 0;
    kpiWorkers.textContent = s.arbeidere ?? 0;
  }
  function actionBtns(id){
    return `
      <button class="ghost-btn btn-small" data-action="view" data-id="${id}">👁</button>
      <button class="ghost-btn btn-small" data-action="edit" data-id="${id}">✏️</button>
      <button class="ghost-btn btn-small" data-action="del" data-id="${id}">🗑</button>
    `;
  }
  function updateTable(rows){
    feedBody.innerHTML = "";
    if(!rows || !rows.length){ feedEmpty.style.display = "block"; return; }
    feedEmpty.style.display = "none";
    rows.forEach((r,i)=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${i+1}</td>
        <td>${r.category||""}</td>
        <td>${r.title||""}</td>
        <td>${r.status||""}</td>
        <td>${(r.created_at||"").replace("T"," ")}</td>
        <td>${actionBtns(r.id)}</td>`;
      feedBody.appendChild(tr);
    });
  }

  async function load(cat=""){
    currentCategory = cat;
    addBtn.style.display = cat ? "inline-flex" : "none";
    addBtn.textContent = "+ " + (document.documentElement.lang==="ar" ? "إضافة" : "Ny");
    const [s, rec] = await Promise.all([API.stats(cat), API.records(cat)]);
    updateTable(rec.records||[]); updateKpis(s||{});
  }

  // side menu
  menu.addEventListener("click", (e)=>{
    const a = e.target.closest("a.item"); if(!a) return;
    e.preventDefault(); menu.querySelectorAll(".item").forEach(x=>x.classList.remove("active"));
    a.classList.add("active"); load(a.dataset.cat || "");
  });

  // open folder
  openFolderBtn.addEventListener("click", ()=>{
    const cat = currentCategory || "reports";
    window.open(`/reports/${encodeURIComponent(cat)}`, "_blank");
  });

  // open create modal
  addBtn.addEventListener("click", async ()=>{
    if(!currentCategory) return;
    modal.classList.add("open");
    modalTitle.textContent = "+";
    modalBody.innerHTML = "<div class='loading'>Loading…</div>";
    currentEditingId = null;
    try{
      const html = await API.form(currentCategory);
      modalBody.innerHTML = html;
      // inject hidden category
      const form = modalBody.querySelector("form");
      let hidden = document.createElement("input");
      hidden.type="hidden"; hidden.name="category"; hidden.value=currentCategory;
      form.appendChild(hidden);
      // prevent default submit (we use modalSave)
      form.addEventListener("submit",(ev)=>{ ev.preventDefault(); });
    }catch{
      modalBody.innerHTML = "<div class='error'>Error loading form.</div>";
    }
  });
  function closeModal(){ modal.classList.remove("open"); modalBody.innerHTML=""; }
  modalClose.addEventListener("click", closeModal); modalCancel.addEventListener("click", closeModal);
  modal.addEventListener("click", (e)=>{ if(e.target===modal) closeModal(); });

  // save (create/update)
  modalSave.addEventListener("click", async ()=>{
    const form = modalBody.querySelector("form"); if(!form) return;
    const fd = new FormData(form);
    try{
      modalSave.disabled=true; modalSave.textContent="…";
      let res = currentEditingId ? await API.update(currentEditingId, fd) : await API.create(fd);
      modalSave.disabled=false; modalSave.textContent="Lagre";
      if(!res.ok){ alert("Feil."); return; }
      closeModal(); showToast(currentEditingId ? "✅ Oppdatert" : "✅ Lagret");
      await load(currentCategory);
    }catch{
      modalSave.disabled=false; modalSave.textContent="Lagre";
      alert("Feil.");
    }
  });

  // table actions
  feedBody.addEventListener("click", async (e)=>{
    const btn = e.target.closest("button"); if(!btn) return;
    const id = parseInt(btn.dataset.id,10);
    const action = btn.dataset.action;
    if(action==="view"){
      const d = await API.details(id);
      if(!d.ok){ alert("Feil."); return; }
      detTitle.textContent = d.record.title || "Detaljer";
      const att = (d.attachments||[]).map(a=>`<a class="att-item" href="${a.url}" target="_blank">${a.kind==="image"?"🖼":"📄"} ${a.original_name}</a>`).join("") || "<span class='muted'>-</span>";
      detBody.innerHTML = `
        <div class="det-grid">
          <div><b>Kategori:</b> ${d.category}</div>
          <div><b>Status:</b> ${d.record.status}</div>
          <div style="grid-column:1 / -1"><b>Beskrivelse:</b><div>${(d.record.description||"-").replace(/\n/g,"<br>")}</div></div>
          <div><b>Dato:</b> ${(d.record.created_at||"").replace("T"," ")}</div>
          <div style="grid-column:1 / -1"><b>Vedlegg:</b><div class="att-list">${att}</div></div>
        </div>`;
      detModal.dataset.id = String(id);
      detModal.classList.add("open");
    }
    if(action==="edit"){
      const d = await API.details(id);
      if(!d.ok){ alert("Feil."); return; }
      modal.classList.add("open");
      modalTitle.textContent = "Rediger";
      modalBody.innerHTML = "<div class='loading'>Loading…</div>";
      currentEditingId = id;
      const html = await API.form(d.category);
      modalBody.innerHTML = html;
      const form = modalBody.querySelector("form");
      (form.querySelector("[name=title]")||{}).value = d.record.title || "";
      (form.querySelector("[name=description]")||{}).value = d.record.description || "";
      (form.querySelector("[name=status]")||{}).value = d.record.status || "open";
      form.addEventListener("submit",(ev)=>ev.preventDefault());
    }
    if(action==="del"){
      if(!confirm("Slette?")) return;
      const r = await API.remove(id);
      if(r.ok){ showToast("🗑 Slettet"); load(currentCategory); } else { alert("Feil."); }
    }
  });
  detClose.addEventListener("click", ()=> detModal.classList.remove("open"));
  detModal.addEventListener("click", (e)=>{ if(e.target===detModal) detModal.classList.remove("open"); });
  detEdit.addEventListener("click", async ()=>{
    const id = parseInt(detModal.dataset.id,10); detModal.classList.remove("open");
    const d = await API.details(id); if(!d.ok) return;
    modal.classList.add("open"); modalTitle.textContent="Rediger"; modalBody.innerHTML="<div class='loading'>Loading…</div>";
    currentEditingId = id;
    const html = await API.form(d.category);
    modalBody.innerHTML = html;
    const form = modalBody.querySelector("form");
    (form.querySelector("[name=title]")||{}).value = d.record.title || "";
    (form.querySelector("[name=description]")||{}).value = d.record.description || "";
    (form.querySelector("[name=status]")||{}).value = d.record.status || "open";
    form.addEventListener("submit",(ev)=>ev.preventDefault());
  });
  detDelete.addEventListener("click", async ()=>{
    const id = parseInt(detModal.dataset.id,10);
    if(!confirm("Slette?")) return;
    const r = await API.remove(id);
    if(r.ok){ detModal.classList.remove("open"); showToast("🗑 Slettet"); load(currentCategory); }
  });

  // manual report
  function openGen(){ genModal.classList.add("open"); genResult.textContent=""; }
  function closeGen(){ genModal.classList.remove("open"); genResult.textContent=""; }
  genBtn.addEventListener("click", openGen); genClose.addEventListener("click", closeGen); genCancel.addEventListener("click", closeGen);
  genModal.addEventListener("click", (e)=>{ if(e.target===genModal) closeGen(); });
  genRun.addEventListener("click", async ()=>{
    const cat = genCat.value; const by = genBy.value.trim() || "Admin";
    genResult.textContent = "Genererer…";
    try{
      const res = await API.genReport(cat, by);
      if(!res.ok){ genResult.textContent = "Feil ved generering."; return; }
      genResult.innerHTML = `Ferdig. <a href="/${res.file}" target="_blank">Last ned rapport</a>`;
    }catch{ genResult.textContent = "Feil ved generering."; }
  });

  // scheduler
  function openSched(){ schedModal.classList.add("open"); loadSched(); }
  function closeSched(){ schedModal.classList.remove("open"); }
  schedBtn.addEventListener("click", openSched);
  schedClose.addEventListener("click", closeSched);
  schedCancel.addEventListener("click", closeSched);
  schedModal.addEventListener("click", (e)=>{ if(e.target===schedModal) closeSched(); });
  async function loadSched(){
    try{
      const s = await API.schedGet();
      if(s.ok){
        schedEnabled.value = s.enabled ? "1":"0";
        schedWeekday.value = s.weekday; schedHour.value = s.hour; schedMinute.value = s.minute;
        const checks = schedCats.querySelectorAll("input[type='checkbox']");
        checks.forEach(ch => ch.checked = (s.categories||[]).includes(ch.value));
        schedLast.textContent = s.last_run ? `Siste kjøring: ${s.last_run}` : "Siste kjøring: -";
      }
    }catch{}
  }
  schedSave.addEventListener("click", async ()=>{
    const cats = Array.from(schedCats.querySelectorAll("input[type='checkbox']:checked")).map(x=>x.value);
    const payload = {
      enabled: schedEnabled.value === "1",
      weekday: parseInt(schedWeekday.value,10),
      hour: parseInt(schedHour.value,10),
      minute: parseInt(schedMinute.value,10),
      categories: cats
    };
    try{
      const r = await API.schedSet(payload);
      if(r.ok){ closeSched(); showToast("✅ Lagret."); } else { alert("Feil ved lagring."); }
    }catch{ alert("Feil ved lagring."); }
  });

  // initial
  load();
});
