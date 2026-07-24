// --- auth chrome: only active when the server has AUTH_ENABLED=true ---------
(async function initAuth() {
  let me;
  try { me = await (await fetch('/api/me')).json(); } catch (_) { return; }
  if (!me || !me.auth_enabled || !me.user) return;   // auth off → behave exactly as before
  const user = me.user;

  // 1) the logged-in identity becomes the author everywhere
  try { localStorage.setItem('maayan.author', user.display_name); } catch (_) {}
  ['author', 'termAuthor', 'composeAuthor', 'connectAuthor'].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) { el.value = user.display_name; el.readOnly = true; el.title = 'Signed in as ' + user.display_name; }
  });

  // 2) header chrome: who · (Users) · Logout
  const mkBtn = function (label) {
    const b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'border:1px solid #e6e0d5; background:#fff; border-radius:7px; padding:5px 10px; cursor:pointer; font-size:13px;';
    return b;
  };
  // The header is a flex row (nav buttons live at its end) — join it, don't float over it.
  const bar = document.createElement('div');
  bar.style.cssText = 'display:flex; gap:10px; align-items:center; font-size:13px; color:#8a8275; flex:0 0 auto;';
  const who = document.createElement('span');
  who.textContent = user.display_name + (user.role === 'admin' ? ' · admin' : '');
  bar.appendChild(who);
  if (user.role === 'admin') { const ub = mkBtn('Users'); ub.onclick = openUsers; bar.appendChild(ub); }
  const lo = mkBtn('Logout');
  lo.onclick = async function () { await fetch('/api/logout', { method: 'POST' }); window.location.href = '/login'; };
  bar.appendChild(lo);
  const header = document.querySelector('header');
  if (header) header.appendChild(bar);

  // 3) admin-only Users panel
  async function openUsers() {
    let users = [];
    try { users = await (await fetch('/api/users')).json(); } catch (_) {}
    const ov = document.createElement('div');
    ov.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,.35); display:flex; align-items:center; justify-content:center; z-index:50;';
    const card = document.createElement('div');
    card.style.cssText = 'background:#fff; border-radius:12px; padding:22px; width:520px; max-height:80vh; overflow:auto; box-shadow:0 10px 40px rgba(0,0,0,.2);';
    card.innerHTML = '<h2 style="margin:0 0 12px; font-size:18px">Users</h2>';
    const list = document.createElement('div');
    users.forEach(function (u) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #f0ece3; font-size:14px;';
      row.innerHTML = '<b style="min-width:120px">' + u.username + '</b>' +
        '<span style="color:#8a8275; flex:1">' + (u.display_name || '') + ' · ' + u.role + (u.active ? '' : ' · disabled') + '</span>';
      const tog = mkBtn(u.active ? 'Disable' : 'Enable');
      tog.onclick = async function () {
        await fetch('/api/users/' + u.id + '/active', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ active: !u.active }) });
        ov.remove(); openUsers();
      };
      row.appendChild(tog);
      list.appendChild(row);
    });
    card.appendChild(list);
    const form = document.createElement('div');
    form.style.cssText = 'margin-top:16px; padding-top:14px; border-top:1px solid #e6e0d5;';
    form.innerHTML =
      '<h3 style="margin:0 0 8px; font-size:14px">Add user</h3>' +
      '<input id="nuUser" placeholder="username" style="width:100%; padding:8px; margin:4px 0; border:1px solid #e6e0d5; border-radius:7px" />' +
      '<input id="nuName" placeholder="display name (optional)" style="width:100%; padding:8px; margin:4px 0; border:1px solid #e6e0d5; border-radius:7px" />' +
      '<input id="nuPass" type="password" placeholder="password (8+ chars)" style="width:100%; padding:8px; margin:4px 0; border:1px solid #e6e0d5; border-radius:7px" />' +
      '<label style="font-size:13px; display:flex; gap:6px; align-items:center; margin:6px 0"><input type="checkbox" id="nuAdmin" /> admin</label>' +
      '<div id="nuErr" style="color:#a23; font-size:13px; min-height:16px"></div>';
    card.appendChild(form);
    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex; gap:8px; justify-content:flex-end; margin-top:10px;';
    const create = mkBtn('Create'); const close = mkBtn('Close');
    close.onclick = function () { ov.remove(); };
    create.onclick = async function () {
      const body = {
        username: document.getElementById('nuUser').value,
        display_name: document.getElementById('nuName').value,
        password: document.getElementById('nuPass').value,
        role: document.getElementById('nuAdmin').checked ? 'admin' : 'member',
      };
      const r = await fetch('/api/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (r.ok) { ov.remove(); openUsers(); }
      else { const d = await r.json().catch(() => ({})); document.getElementById('nuErr').textContent = d.detail || 'Failed.'; }
    };
    actions.appendChild(create); actions.appendChild(close);
    card.appendChild(actions);
    ov.appendChild(card);
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
    document.body.appendChild(ov);
  }
})();
