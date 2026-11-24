// Supabase client SDK import karein (CDN)
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

const supabaseUrl = 'https://ynhojvxzyutnutojtoof.supabase.co';
const supabaseKey = 'sb_publishable_IMDnXTnsfucHizS7XYNDKQ_7Zo-McTD';
const supabase = createClient(supabaseUrl, supabaseKey);

const $ = s => document.querySelector(s);
const NAMES = { booking: "بکنگ", fuel: "فیول", kharcha: "خرچہ" };

// IndexedDB setup (Dexie.js ke baghair, native API)
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

// UI update
async function show() {
  const pending = await getPending();
  $("#pend").textContent = pending.length;
  $("#list").innerHTML = pending.map(e =>
    `<li>⏳ ${e.day} - ${NAMES[e.kind]} - ${e.amount}</li>`
  ).join('');
}

// Sync function
async function sync() {
  const pending = await getPending();
  if (!pending.length || !navigator.onLine) return;

  for (const entry of pending) {
    try {
      const { error } = await supabase.from('entries').insert({
        vehicle_id: entry.vehicle_id,
        day: entry.day,
        kind: entry.kind,
        amount: entry.amount,
        note: entry.note,
        uid: entry.uid
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

// Form submit
$("#f").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  if (!f.v.value) return;
  const k = f.kind.value;

  const entry = {
    uid: Date.now() + "-" + Math.random().toString(36).slice(2),
    vehicle_id: +f.v.value,
    day: f.day.value,
    kind: k,
    amount: f.amt.value,
    note: f.note.value
  };

  // Pehle local mein save
  await savePending(entry);
  f.amt.value = "";
  f.note.value = "";
  $("#st").textContent = NAMES[k] + " محفوظ ہو گیا";
  show();

  // Phir sync try karein
  sync();
};

// Network events
addEventListener("online", sync);
setInterval(sync, 30000);

// Kind buttons (purana logic)
document.querySelectorAll(".kind").forEach(b => b.onclick = () => {
  $("#f").kind.value = b.dataset.k;
  document.querySelectorAll(".kind").forEach(x => x.classList.toggle("on", x == b));
});
$("#day").value = new Date().toISOString().slice(0, 10);

// Initial
show();
sync();