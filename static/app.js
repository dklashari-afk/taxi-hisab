import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

const supabaseUrl = 'https://ynhojvxzyutnutojtoof.supabase.co';
const supabaseKey = 'sb_publishable_IMDnXTnsfucHizS7XYNDKQ_7Zo-McTD';
const supabase = createClient(supabaseUrl, supabaseKey);

const $ = s => document.querySelector(s);
const NAMES = { booking: "بکنگ", fuel: "فیول", kharcha: "خرچہ" };

// ---------- IndexedDB ----------
const DB_NAME = 'taxi_offline';
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending_entries')) {
        db.createObjectStore('pending_entries', { keyPath: 'uid' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function savePending(entry) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending_entries', 'readwrite');
    tx.objectStore('pending_entries').put(entry);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getPending() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending_entries', 'readonly');
    const req = tx.objectStore('pending_entries').getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function deletePending(uid) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending_entries', 'readwrite');
    tx.objectStore('pending_entries').delete(uid);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ---------- UI ----------
async function show() {
  const pending = await getPending();
  $("#pend").textContent = pending.length;
  $("#list").innerHTML = pending.map(e =>
    `<li>⏳ ${e.day} - ${NAMES[e.kind]} - ${e.amount}</li>`
  ).join('');
}

function updateNetMsg() {
  const m = $("#netMsg");
  if (!navigator.onLine) {
    m.style.display = "block";
    m.textContent = "آف لائن موڈ: ڈیٹا محفوظ ہو رہا ہے، انٹرنیٹ آنے پر خود بھیج دیا جائے گا";
  } else {
    m.style.display = "none";
  }
}

// ---------- Vehicle list (Supabase se) ----------
async function loadVehicles() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    $("#vehicleSelect").innerHTML = '<option value="">پہلے لاگ ان کریں</option>';
    return;
  }

  const { data, error } = await supabase
    .from('vehicles')
    .select('id, number')
    .eq('driver_id', session.user.id);

  if (error || !data || !data.length) {
    $("#vehicleSelect").innerHTML = '<option value="">کوئی گاڑی نہیں ملی</option>';
    return;
  }

  $("#vehicleSelect").innerHTML = data
    .map(v => `<option value="${v.id}">${v.number}</option>`)
    .join('');
}

// ---------- Sync ----------
async function sync() {
  const pending = await getPending();
  if (!pending.length || !navigator.onLine) return;

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    $("#st").textContent = "لاگ ان کریں تاکہ ڈیٹا بھیج سکیں";
    return;
  }

  for (const entry of pending) {
    try {
      const { error } = await supabase.from('entries').insert({
        vehicle_id: entry.vehicle_id,
        day: entry.day,
        kind: entry.kind,
        amount: entry.amount,
        note: entry.note,
        uid: entry.uid,
        driver_id: session.user.id
      });
      if (!error) {
        await deletePending(entry.uid);
      } else {
        console.warn('Supabase insert error:', error);
      }
    } catch (e) {
      console.warn('Sync failed for', entry.uid, e);
    }
  }
  $("#st").textContent = "✅ بھیج دیا گیا";
  show();
}

// ---------- Form submit ----------
$("#f").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  if (!f.v.value) {
    $("#st").textContent = "پہلے گاڑی منتخب کریں";
    return;
  }
  const k = f.kind.value;

  const entry = {
    uid: Date.now() + "-" + Math.random().toString(36).slice(2),
    vehicle_id: +f.v.value,
    day: f.day.value,
    kind: k,
    amount: f.amt.value,
    note: f.note.value
  };

  await savePending(entry);
  f.amt.value = "";
  f.note.value = "";
  $("#st").textContent = NAMES[k] + " محفوظ ہو گیا";
  show();
  sync();
};

// ---------- Events ----------
addEventListener("online", () => { updateNetMsg(); sync(); });
addEventListener("offline", updateNetMsg);
setInterval(sync, 30000);

document.querySelectorAll(".kind").forEach(b => b.onclick = () => {
  $("#f").kind.value = b.dataset.k;
  document.querySelectorAll(".kind").forEach(x => x.classList.toggle("on", x == b));
});
$("#day").value = new Date().toISOString().slice(0, 10);

// ---------- Init ----------
updateNetMsg();
show();
sync();
loadVehicles();