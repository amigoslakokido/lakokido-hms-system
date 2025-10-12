// static/js/smart_ui.js
(function(){
  function analyze(t){
    t = (t || "").toLowerCase();
    let score=0, tags=[], sugg=[];
    const high=["حريق","دخان","انفجار","انزلاق","كهرب","ماس","اختناق","سم","غاز"];
    const med =["تسريب","زيوت","دهون","ملوث","كسر","تعطل","انسكاب","رطوبة"];

    high.forEach(w=>{ if(t.indexOf(w)>=0){ score+=2; tags.push(w); }});
    med.forEach(w=>{ if(t.indexOf(w)>=0){ score+=1; tags.push(w); }});

    let sev="منخفض";
    if(score>=3) sev="مرتفع";
    else if(score===2) sev="متوسط";

    if(/دهون|زيوت|شحم/.test(t)) sugg.push("جدولة تفريغ خزان الدهون ومراجعة سجل الصيانة.");
    if(/كهرب|ماس|قاطع/.test(t)) sugg.push("استدعاء فني كهرباء وفحص القواطع وتوثيق القياسات.");
    if(/انزلاق|انسكاب|رطوبة/.test(t)) sugg.push("تجفيف الأرضية ووضع لافتات تحذيرية وفحص التسريب.");
    if(/نفايات|فرز|بلدية/.test(t)) sugg.push("مراسلة البلدية رسميًا وتوثيق الرد وخطة مؤقتة للفرز.");

    tags = [...new Set(tags)];
    sugg = [...new Set(sugg)];
    return {severity:sev, tags, suggestions:sugg};
  }

  function render(res){
    const sev = document.getElementById("ai-sev");
    const tags = document.getElementById("ai-tags");
    const sug = document.getElementById("ai-sugg");
    if(sev) sev.textContent = res.severity || "—";
    if(tags){
      tags.innerHTML = "";
      (res.tags||[]).forEach(t=>{
        const span = document.createElement("span");
        span.className="pill";
        span.textContent=t;
        tags.appendChild(span);
      });
    }
    if(sug){
      sug.innerHTML="";
      (res.suggestions||[]).forEach(s=>{
        const li=document.createElement("li");
        li.textContent=s;
        sug.appendChild(li);
      });
    }
  }

  window.addEventListener("DOMContentLoaded", ()=>{
    const btn = document.getElementById("ai-analyze");
    if(!btn) return;
    btn.addEventListener("click", ()=>{
      const t = (document.getElementById("details")?.value || "") + "\n" + (document.getElementById("actions")?.value || "");
      render(analyze(t));
    });
  });
})();
