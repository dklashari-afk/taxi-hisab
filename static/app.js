const $=s=>document.querySelector(s),K="q";
const get=()=>JSON.parse(localStorage.getItem(K)||"[]"),put=a=>localStorage.setItem(K,JSON.stringify(a));
$("#day").value=new Date().toISOString().slice(0,10);
document.querySelectorAll(".kind").forEach(b=>b.onclick=()=>{$("#f").kind.value=b.dataset.k;document.querySelectorAll(".kind").forEach(x=>x.classList.toggle("on",x==b))});
function show(){const q=get();$("#pend").textContent=q.length;$("#list").innerHTML=q.map(e=>`<li>⏳ ${e.day} - ${NAMES[e.kind]} - ${e.amount}</li>`).join("")}
async function sync(){const q=get();if(!q.length||!navigator.onLine)return;
 try{const r=await fetch("/api/sync",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({entries:q})});
 if(r.status==401){$("#st").textContent="دوبارہ لاگ ان کریں";return}
 const d=await r.json(),done=[...d.ok,...d.bad];put(get().filter(e=>!done.includes(e.uid)));
 $("#st").textContent=d.bad.length?"کچھ اندراج غلط تھے، دوبارہ لکھیں":"✅ بھیج دی گئیں"}catch(e){}show()}
$("#f").onsubmit=e=>{e.preventDefault();const f=e.target;if(!f.v.value)return;const k=f.kind.value;
 put([...get(),{uid:Date.now()+"-"+Math.random().toString(36).slice(2),vehicle_id:+f.v.value,day:f.day.value,kind:k,amount:f.amt.value,note:f.note.value}]);
 f.amt.value=f.note.value="";$("#st").textContent=NAMES[k]+" محفوظ ہو گیا";show();sync()};
addEventListener("online",sync);setInterval(sync,30000);show();sync();