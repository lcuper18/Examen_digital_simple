// Núcleo del panel docente: sesión, API, diálogos, avisos y navegación por módulos
const Panel = {
  token: sessionStorage.getItem('docenteToken'),
  modulos: [],
  moduloActivo: null,
  temporizadorSesion: null,
  ORDEN: ['resumen', 'resultados', 'estudiantes', 'examenes', 'notas', 'reportes', 'bitacora'],
};

const $ = (id) => document.getElementById(id);

Panel.esc = function (value) {
  return String(value ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
};

Panel.formatoFecha = function (iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('es-CR', { dateStyle: 'short', timeStyle: 'short' });
};

Panel.nombre = function (e) {
  return `${e.apellido1} ${e.apellido2 || ''}, ${e.nombre}`.replace(/\s+/g, ' ').trim();
};

Panel.registrar = function (id, titulo, modulo) {
  Panel.modulos.push(Object.assign({ id, titulo }, modulo));
};

// ========== API ==========
Panel.api = async function (url, options = {}) {
  const headers = Object.assign({ Authorization: `Bearer ${Panel.token}` }, options.headers);
  const response = await fetch(url, Object.assign({}, options, { headers }));
  if (response.status === 401) {
    Panel.salir('Tu sesión expiró. Ingresa de nuevo.');
    throw new Error('Sesión expirada');
  }
  return response;
};

// Devuelve el JSON o lanza Error con el detalle del servidor
Panel.json = async function (url, options = {}) {
  if (options.body && typeof options.body !== 'string') {
    options = Object.assign({}, options, {
      body: JSON.stringify(options.body),
      headers: Object.assign({ 'Content-Type': 'application/json' }, options.headers),
    });
  }
  const response = await Panel.api(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detalle = Array.isArray(data.detail) ? 'Datos no válidos' : data.detail;
    throw new Error(detalle || 'Error del servidor');
  }
  return data;
};

Panel.descargar = async function (url, nombre) {
  try {
    const response = await Panel.api(url);
    if (!response.ok) throw new Error('No se pudo exportar');
    const blob = await response.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nombre;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    Panel.toast(e.message, 'error');
  }
};

// ========== AVISOS ==========
Panel.toast = function (mensaje, tipo = 'ok') {
  const t = document.createElement('div');
  t.className = `doc-toast ${tipo}`;
  t.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  t.textContent = mensaje;
  $('doc-toasts').appendChild(t);
  setTimeout(() => t.remove(), tipo === 'error' ? 6000 : 3500);
};

// Diálogo modal accesible. Devuelve una promesa con el valor del botón (o null si se cierra).
Panel.dialogo = function ({ titulo, cuerpo = '', botones = [{ texto: 'Cerrar', valor: null }], ancho = '' }) {
  return new Promise(resolve => {
    const previo = document.activeElement;
    const fondo = document.createElement('div');
    fondo.className = 'doc-dialogo-fondo';
    fondo.innerHTML = `
      <div class="doc-dialogo ${ancho}" role="dialog" aria-modal="true" aria-labelledby="dlg-titulo">
        <h2 id="dlg-titulo">${Panel.esc(titulo)}</h2>
        <div class="doc-dialogo-cuerpo">${cuerpo}</div>
        <div class="doc-dialogo-botones">
          ${botones.map((b, i) => `<button type="button" class="btn ${b.primario ? 'btn-primary' : 'btn-secondary'}" data-i="${i}">${Panel.esc(b.texto)}</button>`).join('')}
        </div>
      </div>`;
    const cerrar = (valor) => {
      fondo.remove();
      document.removeEventListener('keydown', teclas, true);
      if (previo && previo.focus) previo.focus();
      resolve(valor);
    };
    const valorBoton = (b) => (typeof b.valor === 'function' ? b.valor(fondo) : b.valor);
    const teclas = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); cerrar(null); }
      if (e.key === 'Tab') {
        const foco = [...fondo.querySelectorAll('button, input, select, textarea')].filter(x => !x.disabled);
        if (!foco.length) return;
        const primero = foco[0], ultimo = foco[foco.length - 1];
        if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
      }
    };
    fondo.addEventListener('click', e => {
      if (e.target === fondo) cerrar(null);
      const i = e.target.dataset && e.target.dataset.i;
      if (i !== undefined) cerrar(valorBoton(botones[Number(i)]));
    });
    document.addEventListener('keydown', teclas, true);
    document.body.appendChild(fondo);
    const campo = fondo.querySelector('input, select, textarea');
    (campo || fondo.querySelector('.btn-primary') || fondo.querySelector('button')).focus();
  });
};

Panel.confirmar = async function (mensaje, { titulo = 'Confirmar', texto = 'Aceptar', peligro = false } = {}) {
  const r = await Panel.dialogo({
    titulo,
    cuerpo: `<p>${Panel.esc(mensaje)}</p>`,
    botones: [{ texto: 'Cancelar', valor: false }, { texto, valor: true, primario: !peligro }],
  });
  return r === true;
};

// Pide un texto; devuelve el texto o null si cancela
Panel.pedir = async function (etiqueta, valor = '', { titulo = 'Dato requerido', placeholder = '' } = {}) {
  return Panel.dialogo({
    titulo,
    cuerpo: `<label class="doc-campo">${Panel.esc(etiqueta)}
      <input type="text" id="dlg-input" value="${Panel.esc(valor)}" placeholder="${Panel.esc(placeholder)}"></label>`,
    botones: [
      { texto: 'Cancelar', valor: null },
      { texto: 'Aceptar', primario: true, valor: (f) => f.querySelector('#dlg-input').value.trim() || null },
    ],
  });
};

// ========== SESIÓN ==========
function expiracionToken(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[0].replace(/-/g, '+').replace(/_/g, '/')));
    return payload.exp * 1000;
  } catch (e) {
    return 0;
  }
}

Panel.iniciarTemporizadorSesion = function () {
  clearInterval(Panel.temporizadorSesion);
  const vence = expiracionToken(Panel.token);
  const tick = () => {
    const resta = Math.floor((vence - Date.now()) / 1000);
    if (resta <= 0) return Panel.salir('Tu sesión expiró. Ingresa de nuevo.');
    const m = Math.floor(resta / 60);
    $('doc-sesion').textContent = `Sesión: ${m >= 60 ? Math.floor(m / 60) + ' h ' + (m % 60) + ' min' : m + ' min'}`;
    $('doc-sesion').classList.toggle('doc-sesion-alerta', resta < 300);
  };
  tick();
  Panel.temporizadorSesion = setInterval(tick, 15000);
};

Panel.entrar = async function () {
  const error = $('doc-login-error');
  error.style.display = 'none';
  const response = await fetch('/api/verificar-docente', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: $('doc-password').value })
  });
  const data = await response.json().catch(() => ({}));
  if (response.ok && data.ok) {
    Panel.token = data.token;
    sessionStorage.setItem('docenteToken', Panel.token);
    $('doc-password').value = '';
    Panel.mostrarPanel();
  } else {
    error.textContent = response.status === 429 ? (data.detail || 'Demasiados intentos') : (data.error || 'Contraseña incorrecta');
    error.style.display = 'block';
  }
};

Panel.salir = function (mensaje) {
  Panel.token = null;
  clearInterval(Panel.temporizadorSesion);
  sessionStorage.removeItem('docenteToken');
  $('doc-panel').style.display = 'none';
  $('doc-login').style.display = 'flex';
  if (mensaje) {
    const error = $('doc-login-error');
    error.textContent = mensaje;
    error.style.display = 'block';
  }
};

// ========== NAVEGACIÓN ==========
Panel.construirNavegacion = function () {
  const ordenados = Panel.ORDEN.map(id => Panel.modulos.find(m => m.id === id)).filter(Boolean);
  const nav = $('doc-tabs');
  nav.innerHTML = ordenados.map(m =>
    `<button class="doc-tab" role="tab" id="tabbtn-${m.id}" aria-controls="tab-${m.id}" data-tab="${m.id}">${Panel.esc(m.titulo)}</button>`
  ).join('');
  $('doc-contenido').innerHTML = ordenados.map(m =>
    `<section id="tab-${m.id}" class="doc-section" role="tabpanel" aria-labelledby="tabbtn-${m.id}" hidden></section>`
  ).join('');
  ordenados.forEach(m => { if (m.init) m.init($(`tab-${m.id}`)); });
  Panel.ordenados = ordenados;
};

Panel.irA = async function (id) {
  const modulo = Panel.ordenados.find(m => m.id === id);
  if (!modulo) return;
  Panel.moduloActivo = id;
  document.querySelectorAll('.doc-tab').forEach(b => {
    const activa = b.dataset.tab === id;
    b.classList.toggle('active', activa);
    b.setAttribute('aria-selected', activa ? 'true' : 'false');
    b.tabIndex = activa ? 0 : -1;
  });
  Panel.ordenados.forEach(m => { $(`tab-${m.id}`).hidden = m.id !== id; });
  sessionStorage.setItem('docenteTab', id);
  if (modulo.mostrar) {
    try { await modulo.mostrar(); } catch (e) { if (e.message !== 'Sesión expirada') Panel.toast(e.message, 'error'); }
  }
};

Panel.mostrarPanel = function () {
  $('doc-login').style.display = 'none';
  $('doc-panel').style.display = 'block';
  Panel.iniciarTemporizadorSesion();
  if (!Panel.ordenados) Panel.construirNavegacion();
  const guardada = sessionStorage.getItem('docenteTab');
  Panel.irA(Panel.ordenados.some(m => m.id === guardada) ? guardada : Panel.ordenados[0].id);
};

document.addEventListener('DOMContentLoaded', () => {
  $('doc-login-btn').addEventListener('click', Panel.entrar);
  $('doc-password').addEventListener('keypress', e => { if (e.key === 'Enter') Panel.entrar(); });
  $('doc-logout').addEventListener('click', () => Panel.salir());
  $('doc-tabs').addEventListener('click', e => { if (e.target.dataset.tab) Panel.irA(e.target.dataset.tab); });
  $('doc-tabs').addEventListener('keydown', e => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const ids = Panel.ordenados.map(m => m.id);
    const i = ids.indexOf(Panel.moduloActivo);
    const sig = ids[(i + (e.key === 'ArrowRight' ? 1 : -1) + ids.length) % ids.length];
    Panel.irA(sig).then(() => $(`tabbtn-${sig}`).focus());
  });
  if (Panel.token && expiracionToken(Panel.token) > Date.now()) Panel.mostrarPanel();
  else Panel.salir();
});
