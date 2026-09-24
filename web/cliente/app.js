'use strict';
// Cliente del panel de reportes: vanilla JS contra la API de web/app/main.py.
// Todo el texto que viene del servidor se inserta como texto (nunca como HTML).

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function h(tag, props = {}, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of hijos.flat()) if (c != null && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

async function api(ruta, opts = {}) {
  const r = await fetch(ruta, { headers: { 'Content-Type': 'application/json' }, ...opts });
  let d = null;
  try { d = await r.json(); } catch { /* respuesta sin JSON */ }
  if (!r.ok) {
    const det = d && d.detail;
    const e = new Error(typeof det === 'string' ? det : (det && det.mensaje) || `Error ${r.status}`);
    e.detalle = det;
    throw e;
  }
  return d;
}

const COLORES_AVISO = { info: 'bg-slate-900 text-white', ok: 'bg-emerald-600 text-white', error: 'bg-red-600 text-white' };
function aviso(msg, tipo = 'info') {
  const el = h('div', { class: `whitespace-pre-line rounded-lg px-4 py-3 text-sm shadow-lg ${COLORES_AVISO[tipo]}`, role: 'status' }, msg);
  $('#avisos').append(el);
  setTimeout(() => el.remove(), tipo === 'error' ? 10000 : 5000);
}

const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
const leer = k => { try { return localStorage.getItem(k) || ''; } catch { return ''; } };

const TIPOS = { completo: 'Proceso completo', extraer: 'Extracción', generar: 'Reportes', correos: 'Correos' };
const ESTADOS = {
  en_curso: ['En curso', 'bg-amber-100 text-amber-800'],
  ok: ['Terminado', 'bg-emerald-100 text-emerald-800'],
  fallo: ['Falló', 'bg-red-100 text-red-800'],
  interrumpido: ['Interrumpido', 'bg-slate-200 text-slate-700'],
};
const badge = e => { const [t, c] = ESTADOS[e] || [e, 'bg-slate-100 text-slate-700']; return h('span', { class: `chip text-xs ${c}` }, t); };
const fecha = s => new Date(s * 1000).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
const dur = s => s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
const ENLACE = 'font-medium text-marino underline decoration-marino/30 hover:decoration-marino';

let ESTADO = null, SEMANAS = [], fuente = null, siguiendo = null;

// ---------------- pestañas ----------------
function mostrarTab(n) {
  if (!['proceso', 'semanas', 'correos'].includes(n)) n = 'proceso';
  $$('.tab').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === n));
  $$('.panel').forEach(p => { p.hidden = p.id !== 'tab-' + n; });
  history.replaceState(null, '', '#' + n);
  if (n === 'semanas') cargarSemanas().catch(e => aviso(e.message, 'error'));
  if (n === 'correos') cargarCorreos().catch(e => aviso(e.message, 'error'));
}

// ---------------- estado y configuración ----------------
async function cargarEstado(seguirActual = true) {
  ESTADO = await api('api/estado');
  const c = ESTADO.config;
  const items = [['SQL Server', c.sql], ['Correo (SMTP)', c.smtp], ['Token', c.token_secreto],
                 ['Copia oculta', c.correo_cco && ESTADO.cco_valido], ['Correo Dirección', c.direccion_correo]];
  $('#chips').replaceChildren(...items.map(([n, ok]) =>
    h('span', { class: `chip ${ok ? 'bg-emerald-400/20 text-emerald-100' : 'bg-red-400/30 text-red-100'}`, title: ok ? 'configurado' : 'falta en el .env' },
      ok ? '✓' : '✗', n)));
  llenarExcels();
  $('#btn-ejecutar').disabled = !!ESTADO.trabajo_actual;
  if (seguirActual && ESTADO.trabajo_actual && siguiendo !== ESTADO.trabajo_actual.id) seguir(ESTADO.trabajo_actual.id);
}

async function cargarListaSemanas() {
  SEMANAS = await api('api/semanas');
  const generadas = SEMANAS.filter(s => s.generada);
  for (const sel of [$('#semana-form'), $('#semana-correos')]) {
    const prev = sel.value;
    sel.replaceChildren(...generadas.map(s =>
      h('option', { value: s.semana }, s.semana + (s.criticos ? ` · ${s.criticos} aviso(s) crítico(s)` : ''))));
    if (generadas.some(s => s.semana === prev)) sel.value = prev;
  }
}

// ---------------- formulario de trabajos ----------------
const tipoSel = () => $('input[name=tipo]:checked').value;
const modoSel = () => $('input[name=modo]:checked').value;
const conCorreos = t => t === 'completo' || t === 'correos';

function llenarExcels() {
  if (!ESTADO) return;
  const sel = $('#excel'), prev = sel.value, ops = [];
  if (tipoSel() === 'completo') ops.push(h('option', { value: '' }, 'Extraer de SQL Server (nuevo)'));
  ESTADO.excels.forEach(f => ops.push(h('option', { value: f }, f)));
  sel.replaceChildren(...ops);
  if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
}

function actualizarForm() {
  const t = tipoSel(), m = modoSel();
  $$('[data-si]').forEach(el => { el.hidden = !el.dataset.si.split(' ').includes(t); });
  $$('[data-modo]').forEach(el => { el.hidden = !(conCorreos(t) && el.dataset.modo === m); });
  llenarExcels();
  const conf = t === 'correos' ? ($('#semana-form').value || 'la semana') : 'ENVIAR';
  $('#confirmacion').placeholder = conf;
  $('#ayuda-confirmacion').textContent = `Escribe ${conf} para confirmar el envío real.`;
  const real = conCorreos(t) && m === 'enviar';
  const btn = $('#btn-ejecutar');
  btn.textContent = real ? 'Ejecutar y enviar a los vendedores' : 'Ejecutar';
  btn.className = real ? 'boton-peligro w-full' : 'boton w-full';
}

$('#form-trabajo').addEventListener('submit', async e => {
  e.preventDefault();
  const f = new FormData(e.target), t = tipoSel();
  const body = {
    tipo: t,
    modo: conCorreos(t) ? modoSel() : 'vista',
    excel: (t === 'completo' || t === 'generar') ? (f.get('excel') || null) : null,
    semana: t === 'correos' ? f.get('semana') : null,
    correo_prueba: f.get('correo_prueba') || null,
    confirmacion: f.get('confirmacion') || null,
    ignorar_avisos: f.get('ignorar_avisos') === 'on',
  };
  if (body.correo_prueba) guardar('correo_prueba', body.correo_prueba);
  if (await lanzar(body)) $('#confirmacion').value = '';
});

async function lanzar(body) {
  try {
    const t = await api('api/trabajos', { method: 'POST', body: JSON.stringify(body) });
    aviso(`Inició: ${TIPOS[t.tipo]}`, 'ok');
    $('#btn-ejecutar').disabled = true;
    mostrarTab('proceso');
    seguir(t.id);
    cargarTrabajos();
    return true;
  } catch (e) {
    let msg = e.message;
    if (e.detalle && e.detalle.criticos) msg += '\n• ' + e.detalle.criticos.join('\n• ');
    aviso(msg, 'error');
    return false;
  }
}

// ---------------- log en vivo ----------------
function seguir(id) {
  if (fuente) fuente.close();
  siguiendo = id;
  const consola = $('#consola');
  consola.textContent = '';
  $('#titulo-log').textContent = `Consola · ${id}`;
  $('#estado-trabajo').replaceChildren(badge('en_curso'));
  const es = new EventSource(`api/trabajos/${encodeURIComponent(id)}/log`);
  fuente = es;
  es.onmessage = ev => {
    const abajo = consola.scrollHeight - consola.scrollTop - consola.clientHeight < 40;
    consola.append(JSON.parse(ev.data));
    if (abajo) consola.scrollTop = consola.scrollHeight;
  };
  es.addEventListener('fin', ev => {
    const r = JSON.parse(ev.data);
    es.close(); fuente = null;
    $('#estado-trabajo').replaceChildren(badge(r.estado));
    cargarTrabajos(); cargarEstado(false); cargarListaSemanas().then(actualizarForm);
  });
  es.onerror = () => {
    // EventSource reconectaría solo y repetiría el log desde el principio: mejor reconectar a mano
    es.close();
    if (fuente === es) { fuente = null; setTimeout(() => { if (siguiendo === id) seguir(id); }, 3000); }
  };
}

function detalleParams(p) {
  const partes = [];
  if (p.excel) partes.push(p.excel);
  if (p.semana) partes.push(p.semana);
  if (conCorreos(p.tipo)) partes.push({ vista: 'vista previa', prueba: `prueba → ${p.correo_prueba}`, enviar: 'ENVÍO REAL' }[p.modo]);
  return partes.length ? ' · ' + partes.join(' · ') : '';
}

async function cargarTrabajos() {
  const ts = await api('api/trabajos');
  $('#lista-trabajos').replaceChildren(...(ts.length ? ts.map(t =>
    h('li', { class: 'flex cursor-pointer items-center justify-between gap-3 rounded px-2 py-2 hover:bg-slate-50', onclick: () => seguir(t.id) },
      h('div', { class: 'min-w-0' },
        h('div', { class: 'truncate font-medium' }, TIPOS[t.tipo] + detalleParams(t.params)),
        h('div', { class: 'text-xs text-slate-500' }, `${fecha(t.inicio)} · ${dur(t.duracion)}`)),
      badge(t.estado)))
    : [h('li', { class: 'py-2 text-slate-500' }, 'Todavía no hay trabajos.')]));
}

// ---------------- semanas ----------------
const td = (...c) => h('td', { class: 'px-4 py-3 align-top' }, ...c);

async function cargarSemanas() {
  await cargarListaSemanas();
  $('#tabla-semanas').replaceChildren(...(SEMANAS.length ? SEMANAS.map(s =>
    h('tr', { class: 'hover:bg-slate-50' },
      td(h('b', {}, s.semana)),
      td(s.excel ? h('a', { class: ENLACE, href: `api/semanas/${s.semana}/excel` }, s.excel) : '—'),
      td(s.generada ? `${s.destinatarios} destinatarios` : 'sin generar'),
      td(s.criticos ? h('span', { class: 'chip bg-red-100 text-xs text-red-800' }, `${s.criticos} crítico(s)`) : (s.avisos ? `${s.avisos} aviso(s)` : '—')),
      td(s.generada ? `${s.enviados} / ${s.con_correo}` : '—'),
      td(h('button', { class: 'boton-sec text-xs', onclick: () => verSemana(s.semana) }, 'Ver'))))
    : [h('tr', {}, h('td', { class: 'px-4 py-6 text-slate-500', colspan: 6 }, 'No hay semanas todavía.'))]));
}

async function verSemana(sem) {
  const d = await api(`api/semanas/${sem}`);
  const cont = $('#detalle-semana');
  const avisos = d.avisos.length
    ? h('ul', { class: 'space-y-2 text-sm' }, d.avisos.map(a =>
        h('li', { class: `rounded-lg p-3 ${a.nivel === 'critico' ? 'bg-red-50 text-red-900 ring-1 ring-red-200' : 'bg-amber-50 text-amber-900'}` },
          h('b', {}, a.nivel === 'critico' ? 'Crítico: ' : 'Aviso: '), a.msg)))
    : h('p', { class: 'text-sm text-slate-500' }, 'Sin avisos de datos.');
  const ligas = h('table', { class: 'w-full text-left text-sm' },
    h('thead', { class: 'text-xs uppercase tracking-wide text-slate-500' },
      h('tr', {}, ...['Vendedor', 'Correo', 'Reporte', 'Enviado', ''].map(t => h('th', { class: 'px-4 py-2' }, t)))),
    h('tbody', { class: 'divide-y divide-slate-100' }, d.ligas.map(l =>
      h('tr', {},
        td(l.vendedor),
        td(l.correo || h('span', { class: 'text-red-600' }, 'sin correo')),
        td(h('a', { class: ENLACE, href: l.local || l.liga, target: '_blank', rel: 'noopener' }, 'abrir')),
        td(l.enviado ? '✓' : ''),
        td(h('button', { class: 'boton-sec text-xs', onclick: () => { $('#semana-correos').value = d.semana; mostrarTab('correos'); cargarDestinatarios(l.slug); } }, 'Ver correo'))))));
  const envios = d.envios.length
    ? h('table', { class: 'w-full text-left text-sm' },
        h('thead', { class: 'text-xs uppercase tracking-wide text-slate-500' },
          h('tr', {}, ...['Fecha', 'Vendedor', 'Correo', 'Estado', 'Detalle'].map(t => h('th', { class: 'px-4 py-2' }, t)))),
        h('tbody', { class: 'divide-y divide-slate-100' }, d.envios.map(r =>
          h('tr', {}, td(r.fecha), td(r.vendedor), td(r.correo),
            td(h('span', { class: `chip text-xs ${r.estado === 'enviado' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}` }, r.estado)),
            td(r.detalle)))))
    : h('p', { class: 'text-sm text-slate-500' }, 'Todavía no hay envíos reales de esta semana.');
  cont.replaceChildren(
    h('div', { class: 'flex flex-wrap items-center justify-between gap-3' },
      h('h2', { class: 'text-lg font-semibold' }, `Semana ${d.semana}`),
      d.excel ? h('a', { class: 'boton-sec', href: `api/semanas/${d.semana}/excel` }, `Descargar ${d.excel}`) : null),
    h('div', { class: 'card space-y-3' }, h('h3', { class: 'titulo' }, 'Avisos'), avisos),
    h('div', { class: 'card overflow-x-auto' }, h('h3', { class: 'titulo mb-3' }, 'Ligas por vendedor'), ligas),
    h('div', { class: 'card overflow-x-auto' }, h('h3', { class: 'titulo mb-3' }, 'Registro de envíos'), envios));
  cont.hidden = false;
  cont.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---------------- correos ----------------
async function cargarCorreos() {
  await Promise.all([cargarListaSemanas(), cargarEstado(false)]);
  const c = ESTADO.cco;
  $('#cco-info').replaceChildren(c.length
    ? h('div', {}, h('b', {}, 'Copia oculta en el envío real: '), c.join(', '))
    : h('div', { class: 'text-red-700' }, ESTADO.config.correo_cco ? 'CORREO_CCO tiene correos no válidos.' : 'Falta CORREO_CCO en el .env: el envío real no se puede hacer.'));
  if (!$('#c-prueba').value) $('#c-prueba').value = leer('correo_prueba');
  await cargarDestinatarios();
}

async function cargarDestinatarios(slugSel) {
  const sem = $('#semana-correos').value;
  if (!sem) {
    $('#destinatarios').replaceChildren(h('li', { class: 'py-2 text-slate-500' }, 'No hay semanas con reportes generados.'));
    return;
  }
  const d = await api(`api/semanas/${sem}`);
  $('#c-confirmacion').placeholder = sem;
  $('#destinatarios').replaceChildren(...d.ligas.map(l =>
    h('li', { class: 'flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-2 hover:bg-slate-50', 'data-slug': l.slug, onclick: () => verCorreo(sem, l) },
      h('div', { class: 'min-w-0' },
        h('div', { class: 'truncate font-medium' }, l.vendedor),
        h('div', { class: `truncate text-xs ${l.correo ? 'text-slate-500' : 'text-red-600'}` }, l.correo || 'sin correo: no se envía')),
      l.enviado ? h('span', { class: 'chip bg-emerald-100 text-xs text-emerald-800' }, 'enviado') : null)));
  const elegido = d.ligas.find(l => l.slug === slugSel) || d.ligas[0];
  if (elegido) verCorreo(sem, elegido);
}

async function verCorreo(sem, l) {
  $('#titulo-vista').textContent = `${l.vendedor} · ${l.correo || 'sin correo'}`;
  $$('#destinatarios li').forEach(li => li.classList.toggle('bg-sky-50', li.dataset.slug === l.slug));
  // srcdoc dentro del iframe con sandbox: el HTML del correo se muestra aislado del panel
  const r = await fetch(`api/semanas/${sem}/correos/${encodeURIComponent(l.slug)}`);
  $('#vista').srcdoc = r.ok ? await r.text() : `<p style="font-family:sans-serif;padding:1rem">No se pudo cargar la vista previa (${r.status}).</p>`;
}

$('#btn-c-prueba').addEventListener('click', () => {
  const correo = $('#c-prueba').value.trim();
  if (correo) guardar('correo_prueba', correo);
  lanzar({ tipo: 'correos', semana: $('#semana-correos').value, modo: 'prueba', correo_prueba: correo });
});

$('#btn-c-enviar').addEventListener('click', async () => {
  const sem = $('#semana-correos').value;
  const n = $$('#destinatarios li').length;
  if (!confirm(`¿Enviar los correos reales de la semana ${sem} a ${n} destinatario(s), con copia oculta a CORREO_CCO?`)) return;
  if (await lanzar({ tipo: 'correos', semana: sem, modo: 'enviar', confirmacion: $('#c-confirmacion').value, ignorar_avisos: $('#c-ignorar').checked }))
    $('#c-confirmacion').value = '';
});

// ---------------- arranque ----------------
$$('.tab').forEach(b => b.addEventListener('click', () => mostrarTab(b.dataset.tab)));
// atrás/adelante del navegador o un enlace a #semanas cambian solo el hash
window.addEventListener('hashchange', () => mostrarTab(location.hash.slice(1)));
$$('input[name=tipo], input[name=modo]').forEach(i => i.addEventListener('change', actualizarForm));
$('#semana-form').addEventListener('change', actualizarForm);
$('#semana-correos').addEventListener('change', () => cargarDestinatarios().catch(e => aviso(e.message, 'error')));
$('#correo-prueba').value = leer('correo_prueba');

(async () => {
  try {
    await Promise.all([cargarEstado(), cargarListaSemanas(), cargarTrabajos()]);
  } catch (e) { aviso(e.message, 'error'); }
  actualizarForm();
  mostrarTab(location.hash.slice(1));
})();
