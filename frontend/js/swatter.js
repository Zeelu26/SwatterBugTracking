async function apiFetch(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' };
  if (body) opts.body = JSON.stringify(body);
  try { const res = await fetch('/api' + path, opts); const data = await res.json(); return { ok: res.ok, data }; }
  catch (e) { return { ok: false, data: { error: 'Cannot reach server.' } }; }
}
async function handleLogout() { await apiFetch('/logout', 'POST'); window.location.href = '/login'; }
function showToast(msg, color = '#22c55e') {
  const t = document.getElementById('toast'); if (!t) return;
  t.textContent = msg; t.style.background = color; t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 3000);
}
function esc(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function timeAgo(d) { if(!d)return''; const s=Math.floor((new Date()-new Date(d))/1000); if(s<60)return'just now'; if(s<3600)return Math.floor(s/60)+'m ago'; if(s<86400)return Math.floor(s/3600)+'h ago'; if(s<604800)return Math.floor(s/86400)+'d ago'; return new Date(d).toLocaleDateString(); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
function stars(n) { return '★'.repeat(n) + '☆'.repeat(5-n); }
function fileToBase64(file) {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
}
