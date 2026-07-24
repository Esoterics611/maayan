const $ = (id) => document.getElementById(id);
const AUTHOR_KEY = 'maayan.author';
let active = null;      // active thread id
let lastAnswer = null;  // last answer (sources + session_id) for "Connect these sources"
let chavrusaOn = false; // חברותא mode: route Ask through the bounded study loop (Prompt 39)

const esc = (t) => { const d = document.createElement('div'); d.textContent = t ?? ''; return d.innerHTML; };
const j = (r) => r.json();
// POST JSON and surface HTTP errors instead of silently parsing a 500/502 body as if
// it were an answer. Throws Error(detail) on !ok so callers can show a retryable notice.
async function jPost(url, payload) {
  const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload) });
  if (!r.ok) {
    let detail = 'שגיאה ' + r.status;
    try { const e = await r.json(); if (e && e.detail) detail = e.detail; } catch (_) {}
    throw new Error(detail);
  }
  return r.json();
}
// Guard slow actions (approve / develop / connect / seed …): show a pending state on the
// button, block duplicate clicks while the request is in flight (so a double-click can't
// fire two approvals / two model calls), and surface failures so the user can retry.
async function withBusy(btn, fn) {
  if (!btn || btn.dataset.busy === '1') return;   // ignore re-entrant clicks
  btn.dataset.busy = '1';
  const prevHTML = btn.innerHTML, wasDisabled = btn.disabled;
  btn.disabled = true; btn.innerHTML = '⏳ ' + prevHTML;
  try {
    await fn();
  } catch (e) {
    toast('שגיאה: ' + (e && e.message ? e.message : 'הפעולה נכשלה — נסה שוב'));
  } finally {
    // On success the container usually re-renders (button detached) — nothing to restore.
    // Otherwise (validation/early-return/error) re-enable so the user can retry.
    if (btn.isConnected) { btn.disabled = wasDisabled; btn.innerHTML = prevHTML; btn.dataset.busy = ''; }
  }
}
window.withBusy = withBusy;
// The one evidence-badge grammar (UI spec Rule 2) — identical everywhere.
const EV_GLYPH = {expert:'●', curated:'◆', deterministic:'⚙',
                  derived_approved:'◐', derived_bootstrap:'◌'};

async function loadKinds() {
  try { const ks = await j(await fetch('/kinds'));
    $('kind').innerHTML = ks.map(k => `<option>${k}</option>`).join('');
  } catch (e) { $('kind').innerHTML = '<option>connection</option>'; }
}

async function loadThreads() {
  const ts = await j(await fetch('/threads'));
  $('threadList').innerHTML = ts.length ? ts.map(t =>
    `<div class="thread-item ${t.id === active ? 'active' : ''}" data-id="${t.id}">${esc(t.title)}</div>`
  ).join('') : '<div class="hint">No topics yet.</div>';
  [...document.querySelectorAll('#threadList .thread-item')].forEach(el =>
    el.onclick = () => openThread(el.dataset.id));
}

async function loadTerms() {
  try {
    const ts = await j(await fetch('/terms'));
    $('termList').innerHTML = ts.length ? ts.map(t =>
      `<div class="thread-item" title="${esc(t.term_type)} · by ${esc(t.author)}">`
      + `${esc(t.canonical)} <span class="badge term">${esc(t.term_type)}</span></div>`
    ).join('') : '<div class="hint">No terms yet.</div>';
  } catch (e) { $('termList').innerHTML = '<div class="hint">No terms yet.</div>'; }
}

// -- modal helper (R6): the sacred actions deserve better than window.prompt --
// One small form-in-overlay: context shown, validation inline, cancel does nothing.
function mkModal({ title, context, fields, submitLabel, onSubmit }) {
  const back = document.createElement('div');
  back.className = 'modal-back';
  const inputs = (fields || []).map(f => `
    <label class="field">${esc(f.label)}</label>
    ${f.textarea
      ? `<textarea id="m-${esc(f.id)}" rows="2" dir="auto" placeholder="${esc(f.placeholder || '')}"></textarea>`
      : `<input id="m-${esc(f.id)}" dir="auto" placeholder="${esc(f.placeholder || '')}" />`}
  `).join('');
  back.innerHTML = `<div class="modal">
    <h3 dir="auto">${esc(title)}</h3>
    ${context ? `<div class="ctx" dir="auto">${esc(context)}</div>` : ''}
    ${inputs}
    <div class="err" id="m-err"></div>
    <div class="actions" style="justify-content:flex-end">
      <button class="secondary" id="m-cancel">ביטול</button>
      <button id="m-ok">${esc(submitLabel || 'שמור')}</button>
    </div></div>`;
  back.addEventListener('click', (e) => { if (e.target === back) back.remove(); });
  document.body.appendChild(back);
  // Initial values set via .value (never interpolated into markup): quote-safe.
  (fields || []).forEach(f => {
    const el = back.querySelector('#m-' + f.id);
    if (el && f.value) el.value = f.value;
  });
  const err = back.querySelector('#m-err');
  back.querySelector('#m-cancel').onclick = () => back.remove();
  back.querySelector('#m-ok').onclick = async () => {
    const values = {};
    (fields || []).forEach(f => { values[f.id] = back.querySelector('#m-' + f.id).value.trim(); });
    await onSubmit(values, (msg) => { err.textContent = msg; }, () => back.remove());
  };
  const first = back.querySelector('input, textarea');
  if (first) first.focus();
  return back;
}
window.mkModal = mkModal;

// -- the Review workbench (הכרעות): every gate in one place (redesign R3) ----
// One queue, one count, one card anatomy: what is proposed · its evidence ·
// approve / reject. Dismiss carries the same weight as answer.
const KIND_HE = { developments: 'פיתוחים', relations: 'קשרים', inquiries: 'שאלות לרב', inbox: 'מחשבות' };

async function loadReviewCount() {
  let data = null;
  try { data = await j(await fetch('/api/review/queue')); } catch (e) { /* offline */ }
  const cnt = $('reviewCnt');
  if (!data) {
    if (cnt) cnt.classList.add('zero');
    $('reviewSummary').textContent = 'לא זמין כרגע';
    return null;
  }
  if (cnt) { cnt.textContent = data.total; cnt.classList.toggle('zero', !data.total); }
  const parts = Object.entries(data.counts || {}).filter(([, v]) => v > 0)
    .map(([k, v]) => `${KIND_HE[k] || k} ${v}`);
  $('reviewSummary').innerHTML = data.total
    ? `<b>${data.total}</b> ממתינות: ${esc(parts.join(' · '))}`
    : 'אין הכרעות ממתינות ✓';
  return data;
}

function reviewCard(inner) { return `<div class="src" dir="auto">${inner}</div>`; }

async function openReview() {
  document.body.classList.remove('drawer-open');
  const data = await loadReviewCount();
  if (!data) { toast('שולחן ההכרעות אינו זמין.'); return; }
  const devRows = (data.developments || []).map(d => reviewCard(`
    <div class="ref">◐ פיתוח מוצע <span class="badge proposed">proposed</span>
      <span class="hint">(זרע של ${esc(d.author)})</span></div>
    <div dir="auto">${esc(d.text)}</div>
    ${d.grounded_in && d.grounded_in.length
      ? `<div class="hint">מבוסס על: ${esc(d.grounded_in.join(', '))}</div>` : ''}
    <div class="actions">
      <button onclick="withBusy(this, () => reviewDecideDev('${esc(d.id)}','approve'))">✓ אשר — ייכנס למאגר</button>
      <button class="secondary" onclick="withBusy(this, () => reviewDecideDev('${esc(d.id)}','reject'))">✗ דחה</button>
      <button class="ghost" onclick="closeOverlay(); openThread('${esc(d.thread_id)}')">פתח בנושא ▸</button>
    </div>`)).join('');
  const relRows = (data.relations || []).map(r => reviewCard(`
    <div class="ref">${EV_GLYPH[r.evidence] || '?'} קשר מוצע
      <span class="badge proposed">${esc(r.rel_type)}</span>
      <span class="hint">בטחון ${(r.confidence * 100).toFixed(0)}% · ${esc(r.author)}</span></div>
    <div dir="auto"><span class="srcref" onclick='openReader(${attr(r.subject_label)})'>${esc(r.subject_label)}</span>
      ⟵ ${esc(r.rel_type)} ⟶
      <span class="srcref" onclick='openReader(${attr(r.object_label)})'>${esc(r.object_label)}</span></div>
    ${r.note ? `<div class="hint" dir="auto">${esc(r.note)}</div>` : ''}
    <div class="actions">
      <button onclick="withBusy(this, () => approveRelation('${esc(r.id)}'))">✓ אשר — אתה הערב לקשר</button>
      <button class="secondary" onclick="withBusy(this, () => rejectRelation('${esc(r.id)}'))">✗ דחה</button>
    </div>`)).join('');
  const inqRows = (data.inquiries || []).map(it => {
    const parts = Object.entries(it.priority_parts || {}).map(([k, v]) => `${k}(${v})`).join(' + ');
    const ask = it.kind === 'refused_question' && it.payload && it.payload.questions
      ? `<button class="ghost" onclick='closeOverlay(); prefillAsk(${attr(it.payload.questions[0])})'>שאל שוב ↩</button>` : '';
    return reviewCard(`
      <div class="ref">？ ${esc(it.title)}</div>
      <div class="hint">${esc(it.detail)}</div>
      <div class="hint" style="font-family:monospace" title="החישוב גלוי — התור מרוויח את זמנך ביושר">priority ${it.priority.toFixed(1)} = ${esc(parts)}</div>
      <div class="actions">
        <button onclick='answerInquiry(${attr(it.id)}, ${attr(it.title)})'>ענה ✓ — רשום מה נוצר</button>
        <button class="secondary" onclick='dismissInquiry(${attr(it.id)})'>דחה ✗</button>${ask}
      </div>`);
  }).join('');
  const inboxRows = (data.inbox || []).map(it => reviewCard(`
    <div class="ref">📥 מחשבה <span class="hint">(${esc(it.author)})</span></div>
    <div dir="auto">${esc(it.text)}</div>
    <div class="actions"><button class="ghost" onclick="closeOverlay(); openInbox()">מיין לנושא ▸</button></div>`)).join('');
  const sec = (key, rows, emptyMsg) => `<div class="review-sec">
    <h4>${esc(KIND_HE[key])} · ${(data.counts || {})[key] || 0}</h4>
    ${rows || `<div class="hint">${esc(emptyMsg)}</div>`}</div>`;
  const h = Object.entries(data.harvest || {});
  const harvest = h.length
    ? `<div class="hint" style="margin-bottom:10px">🌾 היום נענו → ${esc(h.map(([k, v]) => `${k}: ${v}`).join(' · '))}</div>` : '';
  const empty = !data.total
    ? `<div class="empty" style="margin:24px 0">אין הכרעות ממתינות — הכל נסקר ✓<br>
         <span class="hint">כשהמודל יציע פיתוח, קשר, או שאלה — זה יופיע כאן ויחכה לך.</span></div>` : '';
  mkOverlay(`<div class="reader-head" dir="rtl">
      <span class="title">⚖️ הכרעות — מה שמחכה לאישורך</span>
      <button class="ghost" title="חדש את שאלות לרב" onclick="generateInquiries()">↻ שאלות</button>
      <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
    <div class="reader-body" dir="rtl" style="font-family:inherit; font-size:15px; line-height:1.6">
      <div class="hint" style="margin-bottom:10px">שום דבר לא נכנס למאגר בלי הכרעה שלך.
        אישור מוסיף ידע (ונרשם כשאלת־זהב); דחייה שוקלת בדיוק כמו אישור.</div>
      ${harvest}${empty}
      ${data.total ? sec('developments', devRows, 'אין פיתוחים ממתינים') : ''}
      ${data.total ? sec('relations', relRows, 'אין קשרים ממתינים') : ''}
      ${data.total ? sec('inquiries', inqRows, 'אין שאלות פתוחות') : ''}
      ${data.total ? sec('inbox', inboxRows, 'אין מחשבות שממתינות למיון') : ''}
    </div>`);
}
window.openReview = openReview;

async function reviewDecideDev(devId, action) {
  const r = await fetch('/developments/' + devId + '/' + action, { method: 'POST' });
  if (r.ok) {
    toast(action === 'approve'
      ? 'אושר ✓ — נכנס למאגר כ־derived ונוסף כשאלת־זהב.' : 'נדחה — שום דבר לא נכנס.');
    openReview();
  } else { const e = await j(r); toast('שגיאה: ' + (e.detail || r.status)); }
}
window.reviewDecideDev = reviewDecideDev;

function requireAuthor(then) {
  const saved = (localStorage.getItem(AUTHOR_KEY) || '').trim();
  if (saved) { then(saved); return; }
  mkModal({
    title: 'מי מכריע?', context: 'אישור נרשם על שמך — פעם אחת, ונזכור.',
    fields: [{ id: 'author', label: 'השם שלך', placeholder: 'e.g. הרב רנדל' }],
    submitLabel: 'המשך',
    onSubmit: (v, err, close) => {
      if (!v.author) { err('שם נדרש.'); return; }
      localStorage.setItem(AUTHOR_KEY, v.author); close(); then(v.author);
    },
  });
}

async function approveRelation(id) {
  requireAuthor(async (author) => {
    const r = await fetch('/api/relations/' + id + '/approve', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ author }) });
    if (r.ok) { toast('הקשר אושר ✓ — מעכשיו הוא מרחיב חיפושים.'); openReview(); }
    else { const e = await j(r); toast('שגיאה: ' + (e.detail || r.status)); }
  });
}
async function rejectRelation(id) {
  const r = await fetch('/api/relations/' + id + '/reject', { method: 'POST' });
  if (r.ok) { toast('הקשר נדחה — לא ישפיע על חיפושים.'); openReview(); }
  else { const e = await j(r); toast('שגיאה: ' + (e.detail || r.status)); }
}
window.approveRelation = approveRelation; window.rejectRelation = rejectRelation;

async function generateInquiries() {
  try { await fetch('/api/inquiries/generate', { method: 'POST' }); } catch (e) {}
  openReview();
}
function answerInquiry(id, title) {
  mkModal({
    title: 'ענה ✓ — מה נוצר מהתשובה?', context: title,
    fields: [{ id: 'resolution', label: 'מה לימדת? (חיבור / מונח / פיתוח + מילה)',
               placeholder: 'e.g. חיבור תניא↔לקו"ת על אהבה', textarea: true }],
    submitLabel: 'סמן כנענתה',
    onSubmit: async (v, err, close) => {
      if (!v.resolution) { err('רשום מה נוצר — כך הקציר נמדד.'); return; }
      const r = await fetch(`/api/inquiries/${id}/answer`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution: v.resolution }) });
      if (r.ok) { close(); toast('נענתה ✓ — נוספה לקציר של היום.'); openReview(); }
      else { const e = await j(r); err('שגיאה: ' + (e.detail || r.status)); }
    },
  });
}
async function dismissInquiry(id) {
  await fetch(`/api/inquiries/${id}/dismiss`, { method: 'POST' });
  openReview();
}
function prefillAsk(q) { $('q').value = q; $('q').focus(); }
window.generateInquiries = generateInquiries; window.answerInquiry = answerInquiry;
window.dismissInquiry = dismissInquiry; window.prefillAsk = prefillAsk;
window.loadReviewCount = loadReviewCount;

// -- the Gold panel (שאלות זהב): the eval flywheel, visible (redesign R4) ----
// Every gated approval auto-drafts a regression example; this is where the
// scholar finally SEES the test set his teaching builds.
const ORIGIN_HE = { connection: 'חיבור', development: 'פיתוח', term: 'מונח', inquiry: 'שאלה שנענתה' };
async function openGold() {
  let g;
  try {
    const r = await fetch('/api/goldset');
    if (!r.ok) { toast('שאלות הזהב אינן זמינות בהתקנה זו.'); return; }
    g = await r.json();
  } catch (e) { toast('שאלות הזהב אינן זמינות.'); return; }
  const chips = Object.entries(g.by_origin || {})
    .map(([k, v]) => `<span class="kpi">${esc(ORIGIN_HE[k] || k)} <b>${v}</b></span>`).join('');
  const rep = g.last_report;
  const fmtPct = (x) => (x * 100).toFixed(0) + '%';
  const report = rep
    ? `<div class="review-sec"><h4>הריצה האחרונה · ${esc(rep.date.slice(0, 10))}</h4>
         ${Object.entries(rep.hit || {}).map(([k, v]) =>
           `<span class="kpi">hit@${esc(k)} <b>${fmtPct(v)}</b></span>`).join('')}
         <span class="kpi">MRR <b>${rep.mrr.toFixed(2)}</b></span>
         <span class="kpi">נענו <b>${fmtPct(rep.answer_rate)}</b></span>
         <div class="hint">${rep.n_ranked} שאלות מדורגות · ${rep.n_gate_only} בודקות רק את שער הסירוב</div>
       </div>`
    : `<div class="review-sec"><h4>מדידה</h4>
         <div class="hint">עדיין אין דוח. מריצים מהמסוף: <code>uv run maayan eval --captured</code> —
         והתוצאה תופיע כאן.</div></div>`;
  const rows = (g.examples || []).map(e => `
    <div class="src" dir="auto" style="${e.retracted ? 'opacity:.45' : ''}">
      <div class="ref">🏅 ${esc(e.question)}
        <span class="badge gold">${esc(ORIGIN_HE[e.origin_kind] || e.origin_kind)}</span>
        ${e.retracted ? '<span class="badge rejected">retracted</span>' : ''}</div>
      <div class="hint">${e.expected_refs.length
        ? 'צריך להעלות: ' + esc(e.expected_refs.join(', '))
        : 'בודקת את שער הסירוב (אסור לענות)'}</div>
    </div>`).join('') || '<div class="hint">עדיין אין שאלות זהב — הן נולדות מהאישורים שלך.</div>';
  mkOverlay(`<div class="reader-head" dir="rtl">
      <span class="title">🏅 שאלות זהב — המבחן שהלימוד שלך בונה</span>
      <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
    <div class="reader-body" dir="rtl" style="font-family:inherit; font-size:15px; line-height:1.6">
      <div class="hint" style="margin-bottom:10px">כל אישור שלך — חיבור, פיתוח, מונח, שאלה שנענתה —
        הופך אוטומטית למבחן קבוע. כך יודעים שהלימוד באמת עוזר: מלמדים, מודדים, רואים את המספרים עולים.</div>
      <span class="kpi">סה״כ <b>${g.total}</b></span>${chips}
      <span class="kpi">שער־בלבד <b>${g.gate_only}</b></span>
      ${report}
      <div class="review-sec"><h4>הדוגמאות האחרונות</h4>${rows}</div>
      <div class="hint">בצד שאלות הזהב שנקלטות מאליהן יש גם סטים שנערכים ביד
        (<code>eval/goldset.yaml</code> ואחיו) — זהב אמיתי עורכים, לא מקליקים.</div>
    </div>`);
}
window.openGold = openGold;

// -- the guide (G2): the walkthrough lives IN the app, offline ----------------
function openGuide() {
  mkOverlay(`<div class="reader-head" dir="rtl">
      <span class="title">? מדריך — איך המעיין גדל</span>
      <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
    <div class="reader-body" dir="rtl" style="font-family:inherit; font-size:15px; line-height:1.7">
      <div class="review-sec"><h4>הלולאה — ארבעה צעדים</h4>
        <div class="src"><b>1 · שאל</b> — כתוב שאלה (או 🎤 דבר). התשובה באה רק מהמקורות, עם ציטוטים —
          או סירוב כן. שאלה לא שומרת כלום.</div>
        <div class="src"><b>2 · לַמֵּד</b> — <b>חיבור:</b> סמן ✓ שני מקורות מתחת לתשובה וכתוב את הקשר ביניהם.
          <b>🌱 זרע:</b> כתוב ידע משלך והמודל יפתח אותו. <b>📖 מונח:</b> הגדר שם קדוש / מונח.
          <b>🎙 שיעור:</b> הקלט — תמלול יחכה לסקירתך.</div>
        <div class="src"><b>3 · הכרע</b> — כל מה שהמודל מציע מחכה לך ב־⚖️ הכרעות.
          אישור מכניס למאגר על שמך; דחייה — כלום לא נכנס. שום דבר לא עוקף אותך.</div>
        <div class="src"><b>4 · רְאֵה</b> — הידע החדש עולה בתשובות הבאות עם תג
          <span class="badge expert">expert</span>, כל אישור נוסף כ־🏅 שאלת־זהב (מבחן קבוע),
          ו״בדוק שהוא עולה →״ מראה מיד שהחיפוש מוצא אותו.</div>
      </div>
      <div class="review-sec"><h4>מי ערב לכל פריט — סימני העדות</h4>
        <div class="hint">● expert — אתה לימדת · ◆ curated — נאסף ביד · ⚙ deterministic — חושב מהטקסט
          · ◐ derived — המודל הציע ואתה אישרת · ◌ bootstrap — טיוטת מודל שעוד מחכה לאישור</div>
      </div>
      <div class="review-sec"><h4>תגי מקור</h4>
        <div class="hint"><span class="badge">sefaria</span> טקסט מודפס (לקריאה בלבד)
          · <span class="badge expert">expert</span> החיבורים שלך
          · <span class="badge derived">derived</span> פיתוח שאושר
          · <span class="badge term">term</span> מילון
          · <span class="badge shiur">shiur</span> משיעור מוקלט
          — כל מה שאינו מודפס ניתן למחיקה (Retract) עם סיבה.</div>
      </div>
      <div class="review-sec"><h4>הכלל האחד</h4>
        <div class="hint">שום דבר לא נכנס למאגר בלי הכרעה שלך — והמערכת לעולם לא עונה
          מהזיכרון של המודל, רק מהמקורות שנשלפו.</div>
      </div>
    </div>`);
}
window.openGuide = openGuide;

// -- verify (R5): "did it learn?" — retrieval only, honest either way --------
async function verifyLearned(question, ref, statusId) {
  const el = $(statusId); if (el) el.textContent = 'בודק…';
  let v;
  try {
    const r = await fetch('/api/verify?question=' + encodeURIComponent(question)
      + '&ref=' + encodeURIComponent(ref));
    if (!r.ok) { if (el) el.textContent = 'הבדיקה אינה זמינה בהתקנה זו.'; return; }
    v = await r.json();
  } catch (e) { if (el) el.textContent = 'הבדיקה נכשלה.'; return; }
  if (el) el.textContent = v.found
    ? `✓ נלמד! עולה במקום ${v.rank} מתוך ${v.top.length} בחיפוש על השאלה הזו.`
    : 'עדיין לא עולה בחיפוש הזה — נסה לנסח את התובנה קרוב יותר ללשון השאלה.';
}
window.verifyLearned = verifyLearned;

async function loadStats() {
  try {
    const s = await j(await fetch('/stats'));
    const bySrc = Object.entries(s.chunks_by_source || {})
      .map(([k, v]) => `${esc(k)} ${v}`).join(' · ') || '—';
    const dev = s.developments_by_status || {};
    $('statsPanel').innerHTML =
      `<div><b>${s.total_chunks}</b> live chunks`
      + (s.qdrant_points != null ? ` · ${s.qdrant_points} indexed` : '') + `</div>`
      + `<div>${bySrc}</div>`
      + `<div>devs: ${(dev.approved||0)} approved · ${(dev.proposed||0)} proposed`
      + ` · ${(dev.retracted||0)} retracted</div>`
      + `<div><span class="srcref" title="What left the corpus, and why"
           onclick="openRetractions()">${s.retractions} retraction(s)</span>`
      + ` · ${s.threads} thread(s) · ${s.terms} term(s)</div>`;
  } catch (e) { $('statsPanel').innerHTML = '<div class="hint">stats unavailable</div>'; }
}
window.loadStats = loadStats;

// -- the retraction ledger: the audit trail of what left the corpus, and why.
// Read-only (no write path); an empty ledger is a statement, not an error.
async function openRetractions() {
  let rows;
  try { rows = await j(await fetch('/retractions')); }
  catch (e) { toast('Ledger unavailable.'); return; }
  const body = (rows && rows.length)
    ? rows.map(r => `<div class="margin-item">
         <div class="ref"><span class="srcref" onclick='openReader(${attr(r.ref)})'>${esc(r.ref)}</span>
           <span class="badge ${esc(r.source)}">${esc(r.source)}</span></div>
         <div class="hint" dir="auto">${esc(r.author)}${r.reason ? ' — ' + esc(r.reason) : ''}</div>
       </div>`).join('')
    : '<div class="hint">שום דבר לא נמחק — the corpus is whole.</div>';
  mkOverlay(`<div class="reader-head">
      <span class="title">מה נמחק · Retraction ledger</span>
      <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
    <div class="reader-body" dir="rtl">${body}</div>`);
}
window.openRetractions = openRetractions;

async function newTopic(title) {
  const t = await j(await fetch('/threads', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ title }) }));
  active = t.id; await loadThreads(); await openThread(t.id); return t.id;
}

async function openThread(id) {
  active = id; $('answerSources').innerHTML = '';
  document.body.classList.remove('drawer-open');  // close the mobile drawer on pick
  const d = await j(await fetch('/threads/' + id));
  [...document.querySelectorAll('.thread-item')].forEach(el =>
    el.classList.toggle('active', el.dataset.id === id));
  renderTurns(d.turns);
}

// The loop strip (G1): the four steps, taught where the work starts —
// an empty thread. Dismissible, remembered, reopenable from the ? guide.
const LOOPSTRIP_KEY = 'maayan.loopstrip.dismissed';
function loopStripHTML() {
  if (localStorage.getItem(LOOPSTRIP_KEY)) return '';
  return `<div class="loopstrip" dir="rtl">
    <button class="ghost dismiss" onclick="dismissLoopStrip()" title="הסתר (יישאר במדריך ?)">✕</button>
    <b>איך המעיין גדל</b> <span class="hint">— ארבעה צעדים, שוב ושוב:</span>
    <div class="steps">
      <div class="step"><b>1 · שאל</b><span class="hint">תשובה מצוטטת מהמקורות — או סירוב כן. כלום לא נשמר.</span></div>
      <div class="step"><b>2 · לַמֵּד</b><span class="hint">סמן ✓ שני מקורות ולמד חיבור, או 🌱 זרע / 📖 מונח / 🎙 שיעור.</span></div>
      <div class="step"><b>3 · הכרע</b><span class="hint">מה שהמודל מציע מחכה ב־⚖️ — אישור או דחייה שלך.</span></div>
      <div class="step"><b>4 · רְאֵה</b><span class="hint">הידע עולה בתשובות הבאות, וכל אישור נהיה 🏅 שאלת־זהב.</span></div>
    </div></div>`;
}
function dismissLoopStrip() {
  localStorage.setItem(LOOPSTRIP_KEY, '1');
  const el = document.querySelector('.loopstrip'); if (el) el.remove();
}
window.dismissLoopStrip = dismissLoopStrip;

function renderTurns(turns) {
  if (!turns.length) {
    $('turns').innerHTML = '<div class="empty">שאל שאלה — או פתח 🌱 זרע ולַמֵּד ידע חדש.</div>'
      + loopStripHTML();
    return;
  }
  lastTurns = turns;
  $('turns').innerHTML = turns.map((t, i) => {
    let extra = '';
    if (t.turn_type === 'seed' && t.is_seed) {
      if (t.directive) extra += `<div class="hint">הנחיה לפיתוח: ${esc(t.directive)}</div>`;
      extra += `<div class="actions"><button class="ghost" onclick="withBusy(this, () => developSeed('${t.record_id}'))"
        title="המודל יציע פיתוח מצוטט — ואתה תכריע">פתח ▸ Develop</button></div>`;
    }
    if (t.turn_type === 'development') {
      if (t.grounded_in && t.grounded_in.length) extra += `<div class="hint">מבוסס על: ${esc(t.grounded_in.join(', '))}</div>`;
      if (t.status === 'proposed' && t.grounded)
        extra += `<div class="actions"><button onclick="withBusy(this, () => decide('${t.record_id}','approve'))"
                    title="ייכנס למאגר כ־derived על שמך">✓ אשר</button>`
               + `<button class="secondary" onclick="withBusy(this, () => decide('${t.record_id}','reject'))"
                    title="שום דבר לא ייכנס">✗ דחה</button></div>`;
    }
    if (['ask', 'development', 'seed'].includes(t.turn_type) && t.text) {
      extra += `<div class="actions"><button class="ghost" title="הורד כ־Markdown (RTL)" onclick="downloadTurn(${i})">⬇︎ .md</button>`
             + `<button class="ghost" title="הדפס / שמור כ־PDF / שתף" onclick="printTurn(${i})">🖨 שתף</button></div>`;
    }
    const statusBadge = t.status ? `<span class="badge ${t.status}">${t.status}</span>` : '';
    return `<div class="turn ${t.turn_type}">
      <div class="who">${t.turn_type} · ${esc(t.author)}${statusBadge}</div>
      <div class="body" dir="auto">${esc(t.text)}</div>${extra}</div>`;
  }).join('');
  $('turns').scrollTop = $('turns').scrollHeight;
}

// --- share / export: a properly-formatted RTL Markdown download, or a print/PDF view ---
function _docMarkdown(title, text, refs, meta) {
  let md = '# ' + (title || 'מעיין') + '\n\n' + (text || '').trim() + '\n';
  if (refs && refs.length) md += '\n## מקורות\n' + refs.map(r => '- ' + r).join('\n') + '\n';
  if (meta) md += '\n---\n\n' + meta + '\n';
  return md;
}
function _mdFilename(title) {
  const base = (title || 'maayan').replace(/[\\/:*?"<>|\n\r]+/g, ' ').trim().slice(0, 60);
  return (base || 'maayan') + '.md';
}
function downloadMd(title, text, refs, meta) {
  const blob = new Blob([_docMarkdown(title, text, refs, meta)], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = _mdFilename(title);
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('הורד ✓ ' + _mdFilename(title));
}
// Self-contained RTL document in a new window → the browser's print dialog also gives
// "Save as PDF", so this is the share/print path. No external resources (CSP-safe).
function printRtl(title, text, refs, meta) {
  const refsHtml = (refs && refs.length)
    ? '<h2>מקורות</h2><ul>' + refs.map(r => '<li>' + esc(r) + '</li>').join('') + '</ul>' : '';
  const metaHtml = meta ? '<hr><p class="meta">' + esc(meta) + '</p>' : '';
  const html = '<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8"><title>'
    + esc(title || 'מעיין') + '</title><style>'
    + 'body{font-family:"Frank Ruhl Libre",Georgia,serif;max-width:44rem;margin:2rem auto;'
    + 'padding:0 1rem;line-height:1.9;color:#1a1a1a}h1{font-size:1.5rem}h2{font-size:1.1rem;'
    + 'margin-top:1.4rem}.body{white-space:pre-wrap}.meta{color:#666;font-size:.85rem}'
    + 'ul{padding-inline-start:1.2rem}@media print{body{margin:0}}</style></head><body>'
    + '<h1>' + esc(title || 'מעיין') + '</h1><div class="body">' + esc(text || '') + '</div>'
    + refsHtml + metaHtml + '</body></html>';
  const w = window.open('', '_blank');
  if (!w) { toast('החלון נחסם — אפשר חלונות קופצים כדי להדפיס/לשתף.'); return; }
  w.document.write(html); w.document.close(); w.focus();
  setTimeout(() => w.print(), 350);
}
function _answerPayload(d) {
  const refs = (d.sources || []).map(s => s.ref).filter(Boolean);
  return { title: d.question || 'תשובה', text: d.answer || '',
           refs, meta: [new Date().toLocaleDateString('he-IL'), 'מעיין'].join(' · ') };
}
function downloadAnswer() { const p = _answerPayload(lastAnswer || {}); downloadMd(p.title, p.text, p.refs, p.meta); }
function printAnswer() { const p = _answerPayload(lastAnswer || {}); printRtl(p.title, p.text, p.refs, p.meta); }
window.downloadAnswer = downloadAnswer; window.printAnswer = printAnswer;
let lastTurns = [];
function _turnPayload(t) {
  const refs = (t.grounded_in && t.grounded_in.length) ? t.grounded_in : (t.cited_refs || []);
  const title = t.directive
    || (t.turn_type === 'development' ? 'פיתוח' : t.turn_type === 'seed' ? 'זרע' : 'לימוד');
  const meta = [t.author, t.turn_type, new Date().toLocaleDateString('he-IL')]
    .filter(Boolean).join(' · ') + ' · מעיין';
  return { title, text: t.text || '', refs, meta };
}
function downloadTurn(i) { const t = lastTurns[i]; if (t) { const p = _turnPayload(t); downloadMd(p.title, p.text, p.refs, p.meta); } }
function printTurn(i) { const t = lastTurns[i]; if (t) { const p = _turnPayload(t); printRtl(p.title, p.text, p.refs, p.meta); } }
window.downloadTurn = downloadTurn; window.printTurn = printTurn;

function renderAnswerSources(data) {
  lastAnswer = data;
  const cls = data.grounded ? '' : ' refused';
  const sources = data.sources || [];
  const srcs = sources.map((s, i) => {
    const badge = s.source === 'expert' ? '<span class="badge expert">expert</span>'
                : s.source === 'derived' ? '<span class="badge derived">derived</span>'
                : s.source === 'term' ? '<span class="badge term">term</span>'
                : s.source === 'shiur' ? '<span class="badge shiur">shiur</span>' : '';
    // A cited shiur source can play from its moment in the recording.
    const play = (s.source === 'shiur' && s.audio_id)
      ? `<button class="ghost" title="Play from here"
            onclick="playCitation('${esc(s.audio_id)}', ${s.start_s || 0})">▶ ${fmtTs(s.start_s || 0)}</button>` : '';
    // Only layered knowledge (expert/derived/term/shiur) is retractable; printed text never is.
    const retract = ['expert', 'derived', 'term', 'shiur'].includes(s.source)
      ? `<button class="ghost" style="color:#a33;margin-left:auto"
            title="Retract this layered-knowledge chunk" onclick="retractSource(${i})">Retract ✕</button>` : '';
    // The via-line (graph expansion provenance): WHY this source appeared.
    // Seed hits have no via — the absence is the design.
    const via = s.via ? `<div class="vialine" dir="auto">↳ via ${esc(s.via.rel_type)}
        <span class="ev-${esc(s.via.evidence)}">${EV_GLYPH[s.via.evidence] || '?'}</span>
        (${esc(s.via.author)}) from <span class="srcref"
        onclick='openReader(${attr(s.via.seed_ref)}, ${attr(s.lang)})'>${esc(s.via.seed_ref)}</span></div>` : '';
    // The margins affordance (Prompt 36): the daf's apparatus for this source.
    const margins = `<button class="ghost" title="הגליון — מה ידוע סביב המקור"
        onclick='openMargins(${attr(s.ref)})'>גליון ▸</button>`;
    return `<div class="src ${s.source}">
      <div class="ref"><input type="checkbox" class="srcpick" data-idx="${i}" title="tick to connect">
        <span class="srcref ${s.cited ? 'cited' : ''}" onclick='openReader(${attr(s.ref)}, ${attr(s.lang)})' title="Read in context">${s.cited ? '✦ ' : ''}${esc(s.ref)}</span>${badge}${play}${margins}${retract}</div>
      ${via}<div dir="auto">${esc(s.text)}</div></div>`;
  }).join('');
  // Teach a connection: tick ≥2 sources (e.g. one Tanya + one Likutei Torah) and link them.
  const connect = sources.length >= 2 ? `
    <div class="connect">
      <div class="hint"><b>לַמֵּד חיבור</b> — סמן ✓ שניים או יותר מהמקורות למעלה
        (למשל תניא ↔ לקוטי תורה), כתוב את הקשר ביניהם, ולחץ. החיבור נשמר על שמך
        ויעלה בשאלות הבאות.</div>
      <input id="connectBody" dir="auto" placeholder="התובנה שמקשרת את המקורות המסומנים…" />
      <div class="row" style="margin-top:6px">
        <input id="connectAuthor" placeholder="השם שלך (חובה — הידע נרשם עליך)" />
        <button onclick="withBusy(this, () => connectSelected())">חבר ✓ Connect →</button>
      </div>
      <span id="connectStatus" class="hint"></span>
    </div>` : '';
  // A refusal is not a dead end (C7): the corpus can't answer — so teach it.
  // The question was already logged to שאלות לרב by the ask telemetry.
  const teach = !data.grounded ? `
    <div class="connect" style="border-color:var(--seed)">
      <div class="hint">אין למעיין מקורות לשאלה זו — <b>עדיין</b>. השאלה נרשמה בשאלות לרב;
        אפשר ללמד אותה עכשיו:</div>
      <div class="actions">
        <button class="secondary" onclick="teachFromRefusal()">🌱 לַמֵּד מזה — פתח זרע עם השאלה</button>
        <button class="ghost" onclick="openGuide()">איך מלמדים? ▸</button>
      </div>
    </div>` : '';
  // Chavrusa answers (Prompt 39) carry a link to the study trace — the stepper that
  // shows how the sugya was worked. A refusal has no trace (nothing was studied).
  const traceLink = data.trace_id
    ? `<div class="actions"><button class="ghost" onclick="openTrace('${esc(data.trace_id)}')"
         title="How the chavrusa studied this — search, open, follow, conclude">כיצד נלמד? ▸</button></div>` : '';
  const readHint = data.grounded && sources.length
    ? `<div class="hint">הקש על מקור לקריאה בהקשר · גליון ▸ מראה מה ידוע סביבו</div>` : '';
  const share = data.grounded ? `<div class="actions">`
      + `<button class="ghost" title="הורד כ־Markdown (RTL)" onclick="downloadAnswer()">⬇︎ הורד .md</button>`
      + `<button class="ghost" title="הדפס או שמור כ־PDF / שתף" onclick="printAnswer()">🖨 הדפס / שתף</button></div>` : '';
  $('answerSources').innerHTML = `<div class="turn ask"><div class="who">latest answer${data.trace_id ? ' · חברותא' : ''}</div>
    <div class="body${cls}" dir="auto">${esc(data.answer)}</div>${share}${traceLink}${teach}${readHint}${srcs}${connect}</div>`;
  const ca = $('connectAuthor');
  if (ca) ca.value = localStorage.getItem(AUTHOR_KEY) || '';
  const cb = $('connectBody');                       // dictation + OCR on the connection insight
  if (cb) { cb.insertAdjacentElement('afterend', mkOcr(cb)); cb.insertAdjacentElement('afterend', mkMic(cb)); }
}

// C7: turn a refusal into teaching — the question becomes the seed's directive.
function teachFromRefusal() {
  const q = lastAnswer ? lastAnswer.question : '';
  $('seedBox').classList.remove('hidden');
  if (q && !$('directive').value) $('directive').value = q;
  $('seedBox').scrollIntoView({ block: 'center', behavior: 'smooth' });
  $('seedBody').focus();
  toast('כתוב את הידע שלך בזרע; השאלה כבר ממתינה כהנחיה לפיתוח.');
}
window.teachFromRefusal = teachFromRefusal;

// A connection is retrievable knowledge, but a SEED is *developable*. This plants an
// insight as a seed in the current thread, where the model develops it (grounded +
// cited) and the expert adjudicates — the full teaching loop, not a dead end. Shared by
// the connect confirmation and the contributions panel.
let lastConnection = null;
async function plantSeedFrom(body, refs, directive, author) {
  author = (author || $('connectAuthor').value.trim() || localStorage.getItem(AUTHOR_KEY) || '').trim();
  if (!author) { toast('שם נדרש — הזרע נרשם עליך.'); return; }
  if (!body) { toast('אין תוכן להפוך לזרע.'); return; }
  localStorage.setItem(AUTHOR_KEY, author);
  if (!active) await newTopic(body.slice(0, 48));
  const r = await fetch('/threads/' + active + '/seed', { method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ author, kind: 'connection', body,
      directive: directive || null, linked_refs: refs || [] }) });
  if (r.ok) {
    toast('נפתח כזרע ✓ — בשיחה, לחץ “פתח ▸ Develop” כדי שהמודל יפתח אותו.');
    await openThread(active);
  } else { const e = await j(r); toast('שגיאה: ' + (e.detail || r.status)); }
}
async function seedFromConnection() {
  if (!lastConnection) return;
  await plantSeedFrom(lastConnection.body, lastConnection.refs, lastConnection.question, null);
}
window.seedFromConnection = seedFromConnection;

// Contributions panel: browse everything the expert has taught (connections/corrections/
// seeds) so a saved connection isn't invisible — and promote any of them into a seed.
let contributions = [];
async function loadContributions() {
  let items = [];
  try { const d = await j(await fetch('/api/contributions?limit=50')); items = d.contributions || []; }
  catch (e) { $('contribList').innerHTML = '<div class="hint">לא זמין.</div>'; return; }
  contributions = items;
  if (!items.length) {
    $('contribList').innerHTML = '<div class="hint">עדיין אין תרומות — סמן ✓ מקורות ולַמֵּד חיבור.</div>';
    return;
  }
  $('contribList').innerHTML = items.map((c, i) => {
    const refs = (c.linked_refs || []).length
      ? `<div class="hint">↔ ${esc(c.linked_refs.join(' · '))}</div>` : '';
    const dev = c.opens_aspect ? '<span class="hint">🌱 זרע</span>'
      : `<button class="ghost" title="הפוך את התרומה לזרע ופתח לפיתוח"
           onclick="withBusy(this, () => developContribution(${i}))">🌱 פתח כזרע</button>`;
    return `<div style="border:1px solid var(--line); border-radius:6px; padding:6px; margin-top:6px">
      <div class="row" style="justify-content:space-between; gap:6px; align-items:center">
        <span class="badge">${esc(c.kind)}</span>${dev}</div>
      <div dir="auto" style="margin-top:4px">${esc((c.body || '').slice(0, 160))}</div>
      ${refs}<div class="hint">${esc(c.author)}</div></div>`;
  }).join('');
}
window.loadContributions = loadContributions;
async function developContribution(i) {
  const c = contributions[i]; if (!c) return;
  await plantSeedFrom(c.body, c.linked_refs || [], c.directive, c.author);
}
window.developContribution = developContribution;

async function connectSelected() {
  const status = $('connectStatus');
  const picks = [...document.querySelectorAll('.srcpick:checked')];
  const refs = picks.map(el => lastAnswer.sources[+el.dataset.idx].ref);
  if (refs.length < 2) { status.textContent = 'סמן ✓ לפחות שני מקורות — חיבור צריך שני קצוות.'; return; }
  const author = $('connectAuthor').value.trim();
  if (!author) { status.textContent = 'שם נדרש — החיבור נרשם עליך.'; $('connectAuthor').focus(); return; }
  const body = $('connectBody').value.trim();
  if (!body) { status.textContent = 'כתוב את התובנה שמקשרת ביניהם.'; return; }
  localStorage.setItem(AUTHOR_KEY, author);
  const r = await fetch('/annotate', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ session_id: lastAnswer.session_id, author, kind: 'connection', body, linked_refs: refs }) });
  if (r.ok) {
    // C4: confirm with consequences — what entered, that a gold example was
    // captured, and a one-click retrieval check ("did it learn?").
    const resp = await j(r);
    const vref = 'Expert · connection · ' + String(resp.annotation_id).slice(0, 8);
    // Remember what was connected so it can be promoted into a developable seed.
    lastConnection = { body, refs, question: lastAnswer.question };
    status.innerHTML = `נשמר ✓ החיבור נכנס למאגר (${refs.length} מקורות מקושרים)`
      + ` — וגם נוסף כ־🏅 שאלת־זהב (מבחן קבוע).<br>`
      + `<button class="ghost" onclick='verifyLearned(${attr(lastAnswer.question)}, ${attr(vref)}, "connectStatus2")'>בדוק שהוא עולה →</button>`
      + ` <button class="secondary" onclick='withBusy(this, () => seedFromConnection())' title="הפוך את החיבור לזרע שהמודל יפתח, ואתה תכריע">🌱 פתח כזרע — Develop it →</button>`
      + `<span id="connectStatus2" class="hint"></span>`;
    $('connectBody').value = '';
    picks.forEach(el => { el.checked = false; });
    loadReviewCount(); loadContributions();
  } else { const e = await j(r); status.textContent = 'שגיאה: ' + (e.detail || r.status); }
}
window.connectSelected = connectSelected;

function retractSource(i) {
  const src = lastAnswer && lastAnswer.sources[i];
  if (!src) return;
  // The audited eraser deserves a real form (R6): target shown, reason recorded,
  // author sticky. Cancel does nothing.
  mkModal({
    title: 'מחיקה מהמאגר · Retract',
    context: '"' + src.ref + '"\nהמחיקה נרשמת (מי ולמה) ונשמרת גם אחרי בנייה מחדש. הטקסט המודפס לעולם אינו נמחק.',
    fields: [
      { id: 'author', label: 'השם שלך (חובה)', value: localStorage.getItem(AUTHOR_KEY) || '' },
      { id: 'reason', label: 'למה? (e.g. הוחלף / טעות / שגוי)', placeholder: 'הסיבה נשמרת ביומן' },
    ],
    submitLabel: 'מחק ✕',
    onSubmit: async (v, err, close) => {
      if (!v.author) { err('שם נדרש — מחיקה נרשמת.'); return; }
      localStorage.setItem(AUTHOR_KEY, v.author);
      const r = await fetch('/retract', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ target: src.ref, author: v.author, reason: v.reason }) });
      if (r.ok) {
        close();
        toast(`נמחק ✓ — "${src.ref}" יצא מהמאגר (וגם שאלת־הזהב שנולדה ממנו הוסרה).`);
        loadStats();
      } else { const e = await j(r); err('לא ניתן למחוק: ' + (e.detail || r.status)); }
    },
  });
}
window.retractSource = retractSource;

// A failed ask (e.g. a transient model hiccup returning an empty response) must not
// leave the user staring at a dead, empty thread — show the reason and a one-click retry.
function renderAskError(msg, q) {
  $('q').value = q;  // keep the question so "Retry" (or Enter) just re-asks it
  $('answerSources').innerHTML = `<div class="turn ask"><div class="who">שגיאה</div>
    <div class="body refused" dir="auto">התשובה לא נוצרה — ${esc(msg)}</div>
    <div class="actions"><button id="askRetry" class="secondary">נסה שוב · Retry</button></div></div>`;
  const rb = $('askRetry'); if (rb) rb.onclick = () => ask();
}

async function ask() {
  const q = $('q').value.trim(); if (!q) return;
  $('askBtn').disabled = true; $('askBtn').textContent = '…';
  try {
    if (chavrusaOn) {
      // חברותא: a bounded study loop, outside any thread (the agent takes no thread
      // context, mirroring `ask --agent`). The answer renders with a "כיצד נלמד?" link.
      const data = await jPost('/ask', { question: q, agent: true });
      $('q').value = '';
      renderAnswerSources(data);
      return;
    }
    if (!active) await newTopic(q.slice(0, 48));
    const data = await jPost('/threads/' + active + '/ask', { question: q });
    $('q').value = '';
    await openThread(active);
    renderAnswerSources(data);
  } catch (e) {
    renderAskError(e && e.message ? e.message : 'הבקשה נכשלה', q);
  } finally { $('askBtn').disabled = false; $('askBtn').textContent = 'שאל · Ask'; }
}

async function plantSeed() {
  const author = $('author').value.trim();
  if (!author) { $('seedStatus').textContent = 'שם נדרש — הזרע נרשם עליך.'; $('author').focus(); return; }
  const body = $('seedBody').value.trim();
  if (!body) { $('seedStatus').textContent = 'כתוב קודם את הידע עצמו.'; return; }
  if (!active) await newTopic(body.slice(0, 48));
  localStorage.setItem(AUTHOR_KEY, author);
  const r = await fetch('/threads/' + active + '/seed', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ author, kind: $('kind').value, body, directive: $('directive').value.trim() || null }) });
  if (r.ok) { $('seedBody').value = ''; $('directive').value = '';
    $('seedStatus').textContent = 'הזרע נשתל ✓ עכשיו: לחץ “פתח ▸ Develop” בשיחה — המודל יציע פיתוח, ואתה תכריע.';
    await openThread(active);
  } else { const e = await j(r); $('seedStatus').textContent = 'שגיאה: ' + (e.detail || r.status); }
}

const splitList = (v) => v.split(',').map(s => s.trim()).filter(Boolean);

async function defineTerm() {
  const author = $('termAuthor').value.trim();
  if (!author) { $('termStatus').textContent = 'שם נדרש — המונח נרשם עליך.'; $('termAuthor').focus(); return; }
  const canonical = $('termCanonical').value.trim();
  const definition = $('termDef').value.trim();
  if (!canonical || !definition) { $('termStatus').textContent = 'צורה קנונית והגדרה — שתיהן נדרשות.'; return; }
  localStorage.setItem(AUTHOR_KEY, author);
  const gem = $('termGematria').value.trim();
  const body = {
    canonical, definition, author, term_type: $('termType').value,
    surface_forms: splitList($('termSurfaces').value),
    related_terms: splitList($('termRelated').value),
    gematria: gem ? parseInt(gem, 10) : null, sacred: $('termSacred').checked,
  };
  const r = await fetch('/terms', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
  if (r.ok) { const t = await j(r);
    $('termStatus').textContent = `"${t.canonical}" הוגדר ✓ — נכנס למילון, יעלה בחיפושים, ונוסף כ־🏅 שאלת־זהב.`;
    ['termCanonical','termDef','termSurfaces','termRelated','termGematria'].forEach(id => $(id).value = '');
    $('termSacred').checked = false; await loadTerms();
  } else { const e = await j(r); $('termStatus').textContent = 'שגיאה: ' + (e.detail || r.status); }
}

async function developSeed(seedId) {
  toast('המודל מפתח את הזרע — מצוטט מהמקורות, או סירוב כן…');
  const r = await fetch('/threads/' + active + '/develop', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ seed_id: seedId }) });
  if (r.ok) { await openThread(active); loadReviewCount(); }
  else { const e = await j(r); toast('שגיאה: ' + (e.detail || r.status)); }
}

async function decide(devId, action) {
  const r = await fetch('/developments/' + devId + '/' + action, { method:'POST' });
  if (r.ok) {
    toast(action === 'approve'
      ? 'אושר ✓ — נכנס למאגר כ־derived, ונוסף כ־🏅 שאלת־זהב.'
      : 'נדחה — שום דבר לא נכנס למאגר.');
    await openThread(active); loadReviewCount();
  } else { const e = await j(r); toast('שגיאה: ' + (e.detail || r.status)); }
}
window.developSeed = developSeed; window.decide = decide;

// -- Compose: brief → outline → fill → review → export ------------------
let lastComposition = null;

function renderComposition(c) {
  lastComposition = c;
  const gated = !c.sections.some(s => s.text);  // outline-only (no fills yet)
  const rows = c.sections.map((s, i) => {
    const badge = s.supported
      ? '<span class="badge derived">grounded</span>'
      : (s.text ? '<span class="badge" style="background:#a33;color:#fff">honest gap</span>' : '');
    const cites = s.cited_refs && s.cited_refs.length
      ? `<div class="hint">Cited: ${esc(s.cited_refs.join(', '))}</div>` : '';
    const body = s.text ? `<div dir="auto">${esc(s.text)}</div>` : `<div class="hint">↳ ${esc(s.query)}</div>`;
    const promote = (s.grounded_in && s.grounded_in.length)
      ? `<button class="ghost" onclick="composePromote(${i})" title="Promote this connection into the corpus">Promote connection →</button>` : '';
    return `<div class="src"><div class="ref"><b>${i + 1}. ${esc(s.heading)}</b> ${badge} ${promote}</div>${body}${cites}</div>`;
  }).join('');
  const actions = `<div class="actions" style="margin-top:8px">
    ${gated ? `<button onclick="composeFill()">Fill sections →</button>` : ''}
    <button class="secondary" onclick="composeReview('approve')">Approve</button>
    <button class="secondary" onclick="composeReview('reject')">Reject</button>
    <button class="secondary" onclick="composeExport()">Export ⤓</button>
    <span class="hint">status: ${esc(c.status)} · ${c.supported_sections} grounded · ${c.gap_sections} gap(s)</span>
  </div>`;
  $('composeDoc').innerHTML = rows + actions;
}

async function composeOutline() {
  const author = $('composeAuthor').value.trim();
  if (!author) { $('composeStatus').textContent = 'Author is required.'; return; }
  const title = $('composeTitle').value.trim(), intent = $('composeIntent').value.trim();
  if (!title || !intent) { $('composeStatus').textContent = 'Title and intent are required.'; return; }
  localStorage.setItem(AUTHOR_KEY, author);
  $('composeStatus').textContent = 'Proposing outline…';
  const r = await fetch('/compose', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ title, intent, author, content_type: $('composeType').value, thread_id: active }) });
  if (r.ok) { $('composeStatus').textContent = 'Outline ready — edit mentally, then Fill.'; renderComposition(await j(r)); }
  else { const e = await j(r); $('composeStatus').textContent = 'Error: ' + (e.detail || r.status); }
}
async function composeFill() {
  if (!lastComposition) return;
  $('composeStatus').textContent = 'Filling section by section (refusing where the corpus is silent)…';
  const r = await fetch('/compositions/' + lastComposition.id + '/fill', { method:'POST' });
  if (r.ok) { $('composeStatus').textContent = 'Filled.'; renderComposition(await j(r)); }
  else { const e = await j(r); $('composeStatus').textContent = 'Error: ' + (e.detail || r.status); }
}
async function composeReview(action) {
  if (!lastComposition) return;
  const r = await fetch('/compositions/' + lastComposition.id + '/' + action, { method:'POST' });
  if (r.ok) renderComposition(await j(r));
}
async function composeExport() {
  if (!lastComposition) return;
  const r = await fetch('/compositions/' + lastComposition.id + '/export');
  if (!r.ok) return;
  const md = (await j(r)).markdown;
  const blob = new Blob([md], { type: 'text/markdown' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'composition.md'; a.click();
}
function composePromote(i) {
  if (!lastComposition) return;
  const author = ($('composeAuthor').value || localStorage.getItem(AUTHOR_KEY) || '').trim();
  const s = lastComposition.sections[i];
  mkModal({
    title: 'קדם חיבור למאגר · Promote',
    context: (s ? s.heading + '\n' : '') + 'הפרוזה של הסעיף לא נכנסת — רק החיבור בין מקורותיו, על שמך.',
    fields: [
      ...(author ? [] : [{ id: 'author', label: 'השם שלך (חובה)' }]),
      { id: 'insight', label: 'התובנה שמקשרת את מקורות הסעיף', textarea: true },
    ],
    submitLabel: 'קדם →',
    onSubmit: async (v, err, close) => {
      const finalAuthor = author || v.author;
      if (!finalAuthor) { err('שם נדרש.'); return; }
      if (!v.insight) { err('כתוב את התובנה.'); return; }
      localStorage.setItem(AUTHOR_KEY, finalAuthor);
      const r = await fetch('/compositions/' + lastComposition.id + '/promote', { method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ section_index: i, author: finalAuthor, insight: v.insight }) });
      if (r.ok) {
        close();
        $('composeStatus').textContent = 'החיבור קודם למאגר ✓ (ונוסף כשאלת־זהב)';
        loadStats(); loadReviewCount();
      } else { const e = await j(r); err('לא ניתן לקדם: ' + (e.detail || r.status)); }
    },
  });
}
window.composeFill = composeFill; window.composeReview = composeReview;
window.composeExport = composeExport; window.composePromote = composePromote;

$('askBtn').onclick = ask;
$('chavrusaToggle').onclick = () => {
  chavrusaOn = !chavrusaOn;
  const b = $('chavrusaToggle');
  b.textContent = 'חברותא ' + (chavrusaOn ? '●' : '○');
  b.classList.toggle('active', chavrusaOn);
  if (chavrusaOn) toast('חברותא: the next Ask studies over several hops. Same refusal gate.');
};
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });
$('newBtn').onclick = () => { const t = $('newTitle').value.trim(); if (t) { $('newTitle').value=''; newTopic(t); } };
$('seedToggle').onclick = () => $('seedBox').classList.toggle('hidden');
$('seedBtn').onclick = plantSeed;
$('termBtn').onclick = defineTerm;
$('termToggle').onclick = () => {
  // Pre-fill surface forms from any text selected in a source/answer above.
  const sel = (window.getSelection && window.getSelection().toString().trim()) || '';
  if (sel) {
    if (!$('termSurfaces').value) $('termSurfaces').value = sel;
    if (!$('termCanonical').value) $('termCanonical').value = sel;
  }
  $('termBox').classList.toggle('hidden');
};
$('composeToggle').onclick = () => $('composeBox').classList.toggle('hidden');
$('composeBtn').onclick = composeOutline;
const savedAuthor = localStorage.getItem(AUTHOR_KEY) || '';
$('author').value = savedAuthor; $('termAuthor').value = savedAuthor;
$('composeAuthor').value = savedAuthor;
$('reviewBtn').onclick = () => openReview();
$('goldBtn').onclick = () => openGold();
$('guideBtn').onclick = () => openGuide();
loadKinds(); loadThreads(); loadTerms(); loadStats(); loadReviewCount(); loadContributions();
// First landing (no thread open yet): teach the loop where the work starts.
if (!active) $('turns').insertAdjacentHTML('beforeend', loopStripHTML());

// -- PWA: register the service worker (no-op where unsupported) ----------
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () =>
    navigator.serviceWorker.register('/sw.js').catch(() => {}));
}

// -- mobile chrome: slide-over drawer + bottom tab bar ------------------
let toastTimer = null;
function toast(msg) {
  const t = $('toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
}
window.toast = toast;
const closeDrawer = () => document.body.classList.remove('drawer-open');
$('menuBtn').onclick = () => document.body.classList.toggle('drawer-open');
$('scrim').onclick = closeDrawer;
[...document.querySelectorAll('#tabbar button')].forEach(btn => btn.onclick = () => {
  const tab = btn.dataset.tab;
  if (tab === 'threads') { document.body.classList.toggle('drawer-open'); return; }
  closeDrawer();
  if (tab === 'ask') {
    $('q').scrollIntoView({ block: 'center' }); $('q').focus();
  } else if (tab === 'capture') {
    $('seedBox').classList.remove('hidden');
    $('seedBox').scrollIntoView({ block: 'center', behavior: 'smooth' });
  } else if (tab === 'library') {
    openLibrary();
  }
});

// -- Voice dictation: Web Speech where available, MediaRecorder fallback --
// Typing nikkud/gershayim on a phone is the adoption blocker; speak instead.
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
const VOICE_LANG_KEY = 'maayan.voicelang';
const voiceLang = () => localStorage.getItem(VOICE_LANG_KEY) || 'he-IL';

function setupMic(btn, target) {
  if (!btn || !target) return;
  if (SpeechRec) {
    // continuous + auto-restart: keep dictating through pauses until the user taps
    // the mic again. Web Speech (Chrome esp.) ends a session on the first silence,
    // which is why the old continuous=false captured only the first phrase. onend
    // restarts the session; finalized text is committed so a restart never loses it.
    let rec = null, listening = false, stopping = false, committed = '';
    const startSession = () => {
      rec = new SpeechRec();
      rec.lang = voiceLang(); rec.interimResults = true; rec.continuous = true;
      rec.onresult = (e) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) committed += r[0].transcript; else interim += r[0].transcript;
        }
        target.value = committed + interim;
      };
      rec.onerror = (ev) => {  // permission errors are fatal; silence ('no-speech') is not
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') stopping = true;
      };
      rec.onend = () => {
        if (listening && !stopping) { try { rec.start(); return; } catch (_) { /* fall through */ } }
        listening = false; stopping = false; btn.classList.remove('recording'); target.focus();
      };
      rec.start();
    };
    btn.onclick = () => {
      if (listening) { stopping = true; if (rec) rec.stop(); return; }  // tap again = stop
      committed = target.value ? target.value + ' ' : '';
      listening = true; stopping = false; btn.classList.add('recording');
      startSession();
    };
  } else {
    setupServerMic(btn, target);  // graceful fallback (no Web Speech, e.g. iOS Safari)
  }
}

function setupServerMic(btn, target) {
  let recorder = null, chunks = [], recording = false;
  btn.onclick = async () => {
    if (recording) { if (recorder) recorder.stop(); return; }
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      toast('Voice typing needs a newer browser — server transcription arrives in Prompt 26.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = new MediaRecorder(stream); chunks = [];
      recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        recording = false; btn.classList.remove('recording');
        uploadForTranscription(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }), target);
      };
      recording = true; btn.classList.add('recording'); recorder.start();
    } catch (err) { toast('Microphone permission is needed for voice input.'); }
  };
}

// Server transcription for the dictation fallback: upload → job → fill the field.
async function uploadForTranscription(blob, target) {
  toast('Transcribing…');
  const tr = await transcribeBlob(blob, 'dictation.webm');
  if (!tr) { toast('Transcription failed.'); return; }
  const text = tr.segments.map(s => (s.edited_text != null ? s.edited_text : s.text)).join(' ');
  target.value = (target.value ? target.value + ' ' : '') + text;
  target.focus();
}

function mkMic(target) {  // build + wire a mic button for a dynamically-rendered field
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'mic'; b.textContent = '🎤';
  b.title = 'Dictate (voice)'; b.setAttribute('aria-label', 'Dictate');
  setupMic(b, target); return b;
}

function updateVoiceLangBtn() {
  const el = $('voiceLang'); if (!el) return;
  el.textContent = voiceLang() === 'he-IL' ? 'עב' : 'EN';
  el.title = 'Voice language: ' + voiceLang() + ' — tap to switch';
}
if ($('voiceLang')) $('voiceLang').onclick = () => {
  localStorage.setItem(VOICE_LANG_KEY, voiceLang() === 'he-IL' ? 'en-US' : 'he-IL');
  updateVoiceLangBtn();
};
updateVoiceLangBtn();
setupMic($('micQ'), $('q'));
setupMic($('micSeed'), $('seedBody'));
setupMic($('micTerm'), $('termDef'));

// -- Shiur transcription: upload/record → poll the job → show transcript --
const fmtTs = (sec) => { sec = Math.floor(sec || 0);
  return String(Math.floor(sec / 60)).padStart(2, '0') + ':' + String(sec % 60).padStart(2, '0'); };

async function transcribeBlob(blob, filename, onStatus) {
  const fd = new FormData();
  fd.append('file', blob, filename || 'recording.webm');
  let r = await fetch('/api/audio', { method: 'POST', body: fd });
  if (!r.ok) { if (onStatus) onStatus({ status: 'error', error: 'upload failed' }); return null; }
  const asset = await j(r);
  r = await fetch('/api/audio/' + asset.id + '/transcribe', { method: 'POST' });
  if (!r.ok) { if (onStatus) onStatus({ status: 'error', error: 'could not start' }); return null; }
  let job = await j(r);
  while (job.status === 'queued' || job.status === 'running') {
    if (onStatus) onStatus(job);
    await new Promise(res => setTimeout(res, 700));   // browser-side poll; no server-side wait
    job = await j(await fetch('/api/jobs/' + job.id));
  }
  if (onStatus) onStatus(job);
  if (job.status !== 'done' || !job.transcript_id) return null;
  return await j(await fetch('/api/transcripts/' + job.transcript_id));
}
window.transcribeBlob = transcribeBlob;

let currentTr = null;   // the transcript under review (with lexicon suggestions)

function renderTranscript(tr) {
  const box = $('shiurTranscript');
  if (!tr) { box.innerHTML = '<div class="hint refused">Transcription failed.</div>'; return; }
  currentTr = tr;
  const audio = tr.audio_id
    ? `<audio id="shiurAudio" controls preload="none" src="/api/audio/${esc(tr.audio_id)}/file" style="width:100%; margin-bottom:8px"></audio>`
    : '';
  const reviewed = tr.status === 'reviewed';
  const rows = tr.segments.map((s, i) => {
    const text = (s.edited_text != null ? s.edited_text : s.text);
    const chips = (s.suggestions || []).map((sg, k) =>
      `<button class="ghost" title="Use the lexicon form" onclick="acceptSuggestion(${i},${k})">`
      + `${esc(sg.surface)} → ${esc(sg.canonical)}</button>`).join(' ');
    return `<div class="src">
      <div class="ref">
        <button class="ghost" onclick="seekAudio(${s.start_s})" title="Play from here">▶ ${fmtTs(s.start_s)}</button>
        <span class="hint">–${fmtTs(s.end_s)}</span>
      </div>
      <textarea id="seg-${i}" rows="2" dir="auto" onchange="saveSegment(${i})">${esc(text)}</textarea>
      <div class="row" style="margin-top:4px">
        <input id="spk-${i}" placeholder="speaker (optional)" value="${esc(s.speaker || '')}" onchange="saveSegment(${i})" />
        <button class="ghost" onclick="defineTermFromSegment()" title="Define selected text as a term">Define term</button>
      </div>
      ${chips ? `<div style="margin-top:4px">${chips}</div>` : ''}
    </div>`;
  }).join('');
  const approved = tr.status === 'approved';
  const footer = `<div class="actions" style="margin-top:8px">
    <button onclick="markReviewed()" ${reviewed || approved ? 'disabled' : ''}>${reviewed || approved ? 'Reviewed ✓' : 'Mark reviewed'}</button>
    <button onclick="approveTranscript()" ${reviewed ? '' : 'disabled'} title="Add to the Knowledge base as a shiur source">Approve → corpus</button>
    <button class="secondary" onclick="rejectTranscript()" ${approved ? 'disabled' : ''}>Reject</button>
    <span class="hint">status: ${esc(tr.status)}</span>
  </div>`;
  box.innerHTML = `<div class="hint">Transcript (${esc(tr.lang)} · ${esc(tr.backend)}) — edit text, accept lexicon fixes, then mark reviewed.</div>`
    + audio + rows + footer;
}

function seekAudio(t) { const a = $('shiurAudio'); if (a) { a.currentTime = t || 0; a.play().catch(() => {}); } }
async function saveSegment(idx, rerender) {
  if (!currentTr) return;
  const r = await fetch('/api/transcripts/' + currentTr.id + '/segments/' + idx, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edited_text: $('seg-' + idx).value, speaker: $('spk-' + idx).value || null }) });
  if (!r.ok) { toast('Could not save segment.'); return; }
  currentTr = await j(r);
  if (rerender) renderTranscript(currentTr);   // reflect revalidated suggestions
}
function acceptSuggestion(i, k) {
  const seg = currentTr && currentTr.segments[i];
  const sg = seg && seg.suggestions && seg.suggestions[k];
  if (!sg) return;
  const ta = $('seg-' + i);
  ta.value = ta.value.replace(sg.surface, sg.canonical);
  saveSegment(i, true);
}
function defineTermFromSegment() {
  const sel = (window.getSelection && window.getSelection().toString().trim()) || '';
  if (sel) { if (!$('termSurfaces').value) $('termSurfaces').value = sel;
    if (!$('termCanonical').value) $('termCanonical').value = sel; }
  $('termBox').classList.remove('hidden');
  $('termBox').scrollIntoView({ block: 'center', behavior: 'smooth' });
}
async function markReviewed() {
  if (!currentTr) return;
  const r = await fetch('/api/transcripts/' + currentTr.id + '/review', { method: 'POST' });
  if (r.ok) { renderTranscript(await j(r)); toast('Marked reviewed ✓'); }
  else toast('Could not mark reviewed.');
}
async function approveTranscript() {
  if (!currentTr) return;
  const author = localStorage.getItem(AUTHOR_KEY) || '';
  if (!author) { toast('Set your name (author) first — e.g. in the Seed panel.'); return; }
  const r = await fetch('/api/transcripts/' + currentTr.id + '/approve', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ author }) });
  if (r.ok) {
    const d = await j(r);
    toast('Approved ✓ — added ' + d.chunk_count + ' shiur chunk(s) to the Knowledge base.');
    currentTr = { ...currentTr, status: 'approved' }; renderTranscript(currentTr); loadStats();
  } else { const e = await j(r); toast('Could not approve: ' + (e.detail || r.status)); }
}
async function rejectTranscript() {
  if (!currentTr) return;
  const r = await fetch('/api/transcripts/' + currentTr.id + '/reject', { method: 'POST' });
  if (r.ok) { renderTranscript(await j(r)); toast('Rejected.'); }
  else toast('Could not reject.');
}
function playCitation(audioId, startS) {
  let a = $('citeAudio');
  if (!a) { a = document.createElement('audio'); a.id = 'citeAudio'; a.style.display = 'none'; document.body.appendChild(a); }
  const src = '/api/audio/' + audioId + '/file';
  if (a.getAttribute('src') !== src) { a.setAttribute('src', src); a.load(); }
  const go = () => { a.currentTime = startS || 0; a.play().catch(() => {}); };
  if (a.readyState >= 1) go(); else a.addEventListener('loadedmetadata', go, { once: true });
}
window.seekAudio = seekAudio; window.saveSegment = saveSegment;
window.acceptSuggestion = acceptSuggestion; window.defineTermFromSegment = defineTermFromSegment;
window.markReviewed = markReviewed; window.approveTranscript = approveTranscript;
window.rejectTranscript = rejectTranscript; window.playCitation = playCitation;

function shiurStatus(job) {
  const m = { queued: 'Queued…', running: 'Transcribing…', done: 'Done ✓',
    error: 'Error: ' + (job.error || 'failed') };
  $('shiurStatus').textContent = m[job.status] || job.status;
}

async function handleShiurBlob(blob, filename) {
  $('shiurTranscript').innerHTML = '';
  renderTranscript(await transcribeBlob(blob, filename, shiurStatus));
}

let shiurRecorder = null, shiurChunks = [], shiurRecording = false;
if ($('shiurRec')) $('shiurRec').onclick = async () => {
  if (shiurRecording) { if (shiurRecorder) shiurRecorder.stop(); return; }
  if (!navigator.mediaDevices || !window.MediaRecorder) { toast('Recording needs a newer browser.'); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    shiurRecorder = new MediaRecorder(stream); shiurChunks = [];
    shiurRecorder.ondataavailable = (e) => { if (e.data.size) shiurChunks.push(e.data); };
    shiurRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      shiurRecording = false;
      $('shiurRec').textContent = '● Record'; $('shiurRec').classList.remove('recording');
      handleShiurBlob(new Blob(shiurChunks, { type: shiurRecorder.mimeType || 'audio/webm' }), 'shiur.webm');
    };
    shiurRecording = true;
    $('shiurRec').textContent = '■ Stop'; $('shiurRec').classList.add('recording');
    shiurRecorder.start();
  } catch (e) { toast('Microphone permission is needed to record.'); }
};
if ($('shiurFile')) $('shiurFile').onchange = (e) => {
  const f = e.target.files && e.target.files[0]; if (f) handleShiurBlob(f, f.name);
};
if ($('shiurToggle')) $('shiurToggle').onclick = () => $('shiurBox').classList.toggle('hidden');

// -- Reading experience: modes + source-in-context + sefer browser ------
const READ_MODE_KEY = 'maayan.readmode', READ_SCALE_KEY = 'maayan.readscale';
const READ_MODES = ['light', 'sepia', 'dark'];
const attr = (x) => JSON.stringify(x).replace(/'/g, '&#39;');  // safe in single-quoted attrs
function applyReading() {
  document.body.setAttribute('data-read-mode', localStorage.getItem(READ_MODE_KEY) || 'light');
  document.documentElement.style.setProperty('--read-scale', localStorage.getItem(READ_SCALE_KEY) || '1');
}
function cycleReadMode() {
  const cur = localStorage.getItem(READ_MODE_KEY) || 'light';
  localStorage.setItem(READ_MODE_KEY, READ_MODES[(READ_MODES.indexOf(cur) + 1) % READ_MODES.length]);
  applyReading();
}
function bumpReadScale(d) {
  let s = parseFloat(localStorage.getItem(READ_SCALE_KEY) || '1') + d;
  s = Math.max(0.8, Math.min(1.8, s));
  localStorage.setItem(READ_SCALE_KEY, s.toFixed(2)); applyReading();
}
applyReading();

function closeOverlay() { const o = $('overlay'); if (o) o.remove(); }
function mkOverlay(inner) {
  closeOverlay();
  const o = document.createElement('div'); o.className = 'overlay'; o.id = 'overlay';
  o.innerHTML = '<div class="reader">' + inner + '</div>';
  o.addEventListener('click', (e) => { if (e.target === o) closeOverlay(); });
  document.body.appendChild(o);
}

async function openReader(ref, lang) {
  let data;
  const q = '/api/source?ref=' + encodeURIComponent(ref) + (lang ? '&lang=' + encodeURIComponent(lang) : '');
  try { data = await j(await fetch(q)); }
  catch (e) { toast('Could not open source.'); return; }
  if (!data || !data.chunks) { toast('Source not found.'); return; }
  const segs = data.chunks.map(c =>
    `<div class="reader-seg ${c.cited ? 'cited' : ''}"${c.ref === ref ? ' id="citedSeg"' : ''}>
       <div class="seg-ref">${esc(c.ref)}</div><div dir="auto">${esc(c.text)}</div></div>`).join('');
  mkOverlay(
    `<div class="reader-head">
       <span class="title" dir="auto">${esc(data.label)} <span class="hint">${esc(data.book)}</span></span>
       <button class="ghost" onclick='openMargins(${attr(ref)})' title="הגליון — מה ידוע סביב המקור">גליון ▸</button>
       <button class="ghost" onclick="cycleReadMode()" title="Light / sepia / dark">◑</button>
       <button class="ghost" onclick="bumpReadScale(-0.1)" title="Smaller">A−</button>
       <button class="ghost" onclick="bumpReadScale(0.1)" title="Larger">A+</button>
       <button class="ghost" onclick="closeOverlay()" title="Close">✕</button>
     </div><div class="reader-body">${segs}</div>`);
  const c = $('citedSeg'); if (c) c.scrollIntoView({ block: 'center' });
}

// -- the margins (Prompt 36): the apparatus as a bottom sheet ---------------
// Groups render in the service's fixed order; every item is a click-through
// (study is walking); an empty apparatus is a statement, not an error.
async function openMargins(ref) {
  let a;
  try { a = await j(await fetch('/api/apparatus?ref=' + encodeURIComponent(ref))); }
  catch (e) { toast('Margins unavailable.'); return; }
  const relGroups = (a.relation_groups || []).map(g => {
    const rows = g.items.map(it => {
      const glyph = EV_GLYPH[it.relation.evidence] || '?';
      const cls = it.in_corpus ? 'srcref' : 'outref';
      const click = it.in_corpus ? ` onclick='closeMargins(); openReader(${attr(it.far_label)})'` : '';
      const snip = it.far_snippet ? `<div class="hint" dir="auto">${esc(it.far_snippet)}</div>` : '';
      return `<div class="margin-item">
        <span class="ev-${esc(it.relation.evidence)}">${glyph}</span>
        <span class="${cls}"${click} dir="auto">${esc(it.far_label)}</span>
        <span class="hint">(${esc(it.relation.author)})</span>${snip}</div>`;
    }).join('');
    return `<div class="margin-group"><div class="margin-head">${esc(g.rel_type)}</div>${rows}</div>`;
  }).join('');
  const terms = (a.terms || []).length
    ? `<div class="margin-group"><div class="margin-head">מונחים</div><div class="margin-item" dir="auto">`
      + a.terms.map(t => esc(t.canonical)).join(' · ') + `</div></div>` : '';
  const layer = (a.expert_layer || []).length
    ? `<div class="margin-group"><div class="margin-head">שכבת הרב</div>`
      + a.expert_layer.map(x => `<div class="margin-item" dir="auto">● <span class="srcref"
          onclick='closeMargins(); openReader(${attr(x.ref)})'>${esc(x.snippet)}</span>
          <span class="hint">(${esc(x.author || x.source)}${x.kind ? ', ' + esc(x.kind) : ''})</span></div>`).join('')
      + `</div>` : '';
  const devs = (a.developments || []).length
    ? `<div class="margin-group"><div class="margin-head">פיתוחים</div>`
      + a.developments.map(d => `<div class="margin-item" dir="auto">◐ ${esc(d.snippet)}
          <span class="hint">(${esc(d.author)})</span></div>`).join('') + `</div>` : '';
  const body = (a.total === 0)
    ? '<div class="hint" dir="rtl" style="padding:12px">הגליון עדיין ריק</div>'
    : relGroups + terms + layer + devs;
  closeMargins();
  const sheet = document.createElement('div');
  sheet.className = 'margins-sheet'; sheet.id = 'marginsSheet';
  sheet.innerHTML = `<div class="margins-head" dir="rtl">
      <span style="font-weight:650" dir="auto">גליון · ${a.total} — ${esc(a.ref)}</span>
      <button class="ghost" onclick="closeMargins()" title="Close">✕</button></div>
    <div class="margins-body" dir="rtl">${body}</div>`;
  document.body.appendChild(sheet);
}
function closeMargins() { const el = $('marginsSheet'); if (el) el.remove(); }
window.openMargins = openMargins; window.closeMargins = closeMargins;

// -- the study trace (Prompt 39): the chavrusa's notebook -------------------
// Rendered as a vertical stepper — a shiur transcript, not a debug log.
// Shareable: open the PWA with #trace=<id>.
const TRACE_VERB = {search:'🔍 חיפש', open_section:'📖 פתח', walk_graph:'🕸 הלך בגרף',
                    lookup_term:'📚 בדק מונח', conclude:'✔ סיכם'};
async function openTrace(id) {
  let t;
  try {
    const r = await fetch('/api/traces/' + encodeURIComponent(id));
    if (!r.ok) { toast('Trace not found.'); return; }
    t = await r.json();
  } catch (e) { toast('Trace unavailable.'); return; }
  const steps = (t.steps || []).map((s, i) => {
    const a = s.action || {};
    const target = a.query || a.ref || a.term || '';
    const hits = (s.digest.hits || []).length
      ? `<div class="hint">→ ${s.digest.hits.length} sources (top: ${esc(s.digest.hits[0].ref)})</div>` : '';
    const edges = (s.digest.edges || []).map(e =>
      `<div class="hint">→ ${EV_GLYPH[e.evidence] || '?'} ${esc(e.rel_type)} (${esc(e.author)}) → ${esc(e.far)}</div>`).join('');
    const note = s.digest.note ? `<div class="hint">→ ${esc(s.digest.note)}</div>` : '';
    const term = s.digest.term ? `<div class="hint">→ ${esc(s.digest.term)}</div>` : '';
    return `<div class="margin-item">${i + 1}. ${TRACE_VERB[a.verb] || esc(a.verb)}
      ${target ? `<b dir="auto">"${esc(target)}"</b>` : ''}${hits}${edges}${term}${note}</div>`;
  }).join('');
  const b = t.budgets || {};
  const forced = t.forced
    ? `<div class="hint">⏸ הגיע לגבול (${esc(b.exhausted || 'malformed')}) — סיכם עם מה שנאסף</div>` : '';
  mkOverlay(`<div class="reader-head">
      <span class="title" dir="auto">כיצד נלמד? — ${esc(t.question)}</span>
      <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
    <div class="reader-body" dir="rtl">${steps}${forced}
      <div class="hint">budgets: hops ${b.hops_used}/${b.hops_max} · chunks ${b.chunks_used}/${b.chunks_max} · calls ${b.calls_used}/${b.calls_max}</div>
    </div>`);
}
window.openTrace = openTrace;
if (location.hash.startsWith('#trace=')) openTrace(location.hash.slice(7));

async function openLibrary() {
  document.body.classList.remove('drawer-open');
  let lib;
  try { lib = await j(await fetch('/api/library')); } catch (e) { toast('Library unavailable.'); return; }
  const items = (lib.entries || []).map(e =>
    `<div class="lib-item" onclick='openBook(${attr(e.book)})'>
       <b dir="auto">${esc(e.book)}</b> <span class="badge ${esc(e.source)}">${esc(e.source)}</span>
       <span class="hint">· ${e.count}</span></div>`).join('') || '<div class="hint">Nothing indexed yet.</div>';
  mkOverlay(`<div class="reader-head"><span class="title">Library</span>
     <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
     <div class="lib-body">${items}</div>`);
}
async function openBook(book) {
  let data;
  try { data = await j(await fetch('/api/library/sections?book=' + encodeURIComponent(book))); }
  catch (e) { toast('Could not open book.'); return; }
  const items = (data.sections || []).map(s =>
    `<div class="lib-item" dir="auto" onclick='openReader(${attr(s.ref)}, ${attr(s.lang)})'>${esc(s.label)}</div>`).join('')
    || '<div class="hint">No sections.</div>';
  mkOverlay(`<div class="reader-head">
       <button class="ghost" onclick="openLibrary()" title="Back">←</button>
       <span class="title" dir="auto">${esc(book)}</span>
       <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
     <div class="lib-body">${items}</div>`);
}
window.openReader = openReader; window.openLibrary = openLibrary; window.openBook = openBook;
window.cycleReadMode = cycleReadMode; window.bumpReadScale = bumpReadScale; window.closeOverlay = closeOverlay;

// == Prompt 30: beyond typing — OCR + highlight-to-act + quick-capture inbox ==

// -- OCR capture: photograph a page → text → review field (never auto-ingested) --
async function ocrToField(file, target) {
  if (!file || !target) return;
  toast('Reading page…');
  let r;
  const fd = new FormData(); fd.append('file', file, file.name || 'page.jpg');
  try { r = await fetch('/api/ocr', { method: 'POST', body: fd }); }
  catch (e) { toast('OCR request failed.'); return; }
  if (!r.ok) { toast(r.status === 503 ? 'OCR is off — set OCR_BACKEND to enable it.' : 'OCR failed.'); return; }
  const text = ((await j(r)).text || '').trim();
  if (!text) { toast('No text found in the image.'); return; }
  target.value = (target.value ? target.value.trimEnd() + '\n' : '') + text;
  target.focus();
  toast('OCR text added — review before saving.');
}
function setupOcr(btn, target) {
  if (!btn || !target) return;
  const input = document.createElement('input');
  input.type = 'file'; input.accept = 'image/*'; input.setAttribute('capture', 'environment');
  input.style.display = 'none';
  input.addEventListener('change', () => {
    const f = input.files && input.files[0]; if (f) ocrToField(f, target); input.value = '';
  });
  document.body.appendChild(input);
  btn.addEventListener('click', () => input.click());
}
function mkOcr(target) {  // build + wire an OCR button for a dynamically-rendered field
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'mic'; b.textContent = '📷';
  b.title = 'Photograph a page (OCR → review)'; b.setAttribute('aria-label', 'Photograph page');
  setupOcr(b, target); return b;
}
window.mkOcr = mkOcr;
setupOcr($('ocrSeed'), $('seedBody'));
setupOcr($('ocrTerm'), $('termDef'));

// -- Highlight-to-act: select text in a source/answer → Connect / Define / Seed --
// Wires the EXISTING flows (tick-to-connect, term prefill, seed body); no new endpoints.
const selMenu = $('selMenu');
let selInfo = null;  // { text, srcEl } captured when the menu is shown (survives selection loss)
function hideSelMenu() { if (selMenu) selMenu.classList.add('hidden'); selInfo = null; }
function actionableSelection() {
  const sel = window.getSelection && window.getSelection();
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null;
  const text = sel.toString().trim();
  if (text.length < 2) return null;
  const node = sel.anchorNode;
  const host = node && (node.nodeType === 1 ? node : node.parentElement);
  // Only over a source/answer or the reader body — not our own inputs or this menu.
  if (!host || !host.closest || !host.closest('#answerSources, .reader-body')) return null;
  return { text, rect: sel.getRangeAt(0).getBoundingClientRect(), srcEl: host.closest('.src') };
}
function maybeShowSelMenu() {
  if (!selMenu) return;
  const info = actionableSelection();
  if (!info) { hideSelMenu(); return; }
  selInfo = info;
  selMenu.style.left = Math.round(info.rect.left + info.rect.width / 2) + 'px';
  selMenu.style.top = Math.round(info.rect.top - 8) + 'px';
  selMenu.classList.remove('hidden');
}
document.addEventListener('mouseup', () => setTimeout(maybeShowSelMenu, 0));
document.addEventListener('touchend', () => setTimeout(maybeShowSelMenu, 0));
document.addEventListener('scroll', hideSelMenu, true);
if (selMenu) [...selMenu.querySelectorAll('button')].forEach(b => b.addEventListener('click', () => {
  const act = b.dataset.act, info = selInfo;
  if (!info) return;
  if (act === 'term') {                       // → existing Term flow (POST /terms)
    if (!$('termSurfaces').value) $('termSurfaces').value = info.text;
    if (!$('termCanonical').value) $('termCanonical').value = info.text;
    $('termBox').classList.remove('hidden');
    $('termBox').scrollIntoView({ block: 'center', behavior: 'smooth' });
  } else if (act === 'seed') {                // → existing Seed flow (POST /threads/{id}/seed)
    const t = $('seedBody'); t.value = (t.value ? t.value.trimEnd() + '\n' : '') + info.text;
    $('seedBox').classList.remove('hidden');
    $('seedBox').scrollIntoView({ block: 'center', behavior: 'smooth' }); t.focus();
  } else if (act === 'connect') {             // → existing Connect flow (POST /annotate)
    if (info.srcEl) { const cb = info.srcEl.querySelector('.srcpick'); if (cb) cb.checked = true; }
    const body = $('connectBody');
    if (body) { body.scrollIntoView({ block: 'center', behavior: 'smooth' }); body.focus();
      toast('Source ticked — tick one more and write the insight, then Connect.'); }
    else { toast('Ask a question first to connect its sources.'); }
  }
  hideSelMenu();
  if (window.getSelection) window.getSelection().removeAllRanges();
}));

// -- Quick-capture inbox: park a thought → triage into a thread later -----------
async function openInbox() {
  document.body.classList.remove('drawer-open');
  let items = [];
  try { items = await j(await fetch('/api/inbox')); } catch (e) { /* 503 when off */ }
  let threadOpts = '';
  try {
    const ts = await j(await fetch('/threads'));
    threadOpts = (ts || []).map(t => `<option value="${esc(t.id)}">${esc(t.title)}</option>`).join('');
  } catch (e) { /* threads optional */ }
  const author = localStorage.getItem(AUTHOR_KEY) || '';
  const list = (items || []).map(it => `
    <div class="inbox-item" data-id="${esc(it.id)}">
      <div dir="auto">${esc(it.text)}</div>
      <div class="meta">
        <span class="hint">${esc(it.author)}</span>
        <select class="moveThread"><option value="">העבר לנושא…</option>${threadOpts}</select>
        <button class="ghost" data-move="${esc(it.id)}">העבר 🌱</button>
      </div>
    </div>`).join('') || '<div class="hint">אין מחשבות ממתינות — קלוט אחת למעלה, ומיין כשנוח.</div>';
  mkOverlay(`<div class="reader-head"><span class="title">📥 מחשבות — קלוט עכשיו, מיין אחר כך</span>
       <button class="ghost" onclick="closeOverlay()" title="Close">✕</button></div>
     <div class="reader-body" style="font-family:inherit; font-size:15px; line-height:1.6">
       <div class="hint" style="margin-bottom:8px">מחשבה שנקלטת כאן היא פתק פרטי — היא לא נכנסת למאגר.
         כשתעביר אותה לנושא היא תהפוך לזרע 🌱 שמחכה להכרעתך.</div>
       <div class="inbox-item">
         <label class="field with-mic"><span>קלוט מחשבה</span>
           <button id="micInbox" type="button" class="mic" title="Dictate">🎤</button></label>
         <textarea id="inboxText" rows="2" dir="auto" placeholder="רעיון חולף — תמיין לנושא אחר כך…"></textarea>
         <div class="meta">
           <input id="inboxAuthor" placeholder="השם שלך (חובה)" value="${esc(author)}" />
           <button id="inboxSaveBtn">קלוט 📥</button><span id="inboxStatus" class="hint"></span>
         </div>
       </div>
       ${list}
     </div>`);
  setupMic($('micInbox'), $('inboxText'));   // dictation on the capture field too
  $('inboxSaveBtn').onclick = captureThought;
  [...document.querySelectorAll('[data-move]')].forEach(btn => btn.onclick = () => {
    const item = btn.closest('.inbox-item');
    moveInbox(btn.dataset.move, item.querySelector('.moveThread').value);
  });
}
async function captureThought() {
  const text = $('inboxText').value.trim(), authorEl = $('inboxAuthor');
  const author = authorEl.value.trim();
  if (!author) { $('inboxStatus').textContent = 'Author is required.'; authorEl.focus(); return; }
  if (!text) { $('inboxStatus').textContent = 'Write a thought first.'; return; }
  localStorage.setItem(AUTHOR_KEY, author);
  const r = await fetch('/api/inbox', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, author }) });
  if (r.ok) { loadReviewCount(); openInbox(); }   // re-render with the new item parked
  else { const e = await j(r); $('inboxStatus').textContent = 'שגיאה: ' + ((e && e.detail) || r.status); }
}
async function moveInbox(itemId, threadId) {
  if (!threadId) { toast('בחר נושא להעביר אליו.'); return; }
  const r = await fetch('/api/inbox/' + itemId + '/move', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ thread_id: threadId }) });
  if (r.ok) { toast('עבר לנושא כזרע 🌱 — שם תלחץ “פתח ▸ Develop” ותכריע.'); loadReviewCount(); openInbox(); }
  else { const e = await j(r); toast('לא ניתן להעביר: ' + ((e && e.detail) || r.status)); }
}
window.openInbox = openInbox;
if ($('inboxBtn')) $('inboxBtn').onclick = openInbox;

// --- module scope: inline handlers still need these on `window` --------------
// This file is loaded as `type="module"`, so top-level declarations are NO LONGER
// global. Everything invoked from an `onclick="…"` attribute — in the markup or in
// generated HTML — must be reachable from the global scope, which is why ~54
// `window.x = x` assignments already appear above. `openThread` is called from a
// generated handler in the review overlay ("פתח בנושא ▸") and was relying on the
// old classic-script global leak; without this line that button silently breaks.
window.openThread = openThread;
