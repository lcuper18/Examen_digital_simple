// Núcleo del panel docente: sesión, API, diálogos, avisos y navegación por módulos
const Panel = {
  token: sessionStorage.getItem('docenteToken'),
  modulos: [],
  moduloActivo: null,
  temporizadorSesion: null,
  GRUPOS: [
    { titulo: 'Hoy', ids: ['resumen'] },
    { titulo: 'Mis clases', ids: ['asistencia', 'actividades', 'notas'] },
    { titulo: 'Exámenes', ids: ['examenes', 'resultados'] },
    { titulo: 'Estudiantes', ids: ['estudiantes'] },
    { titulo: 'Informes', ids: ['reportes'] },
    { titulo: 'Sistema', ids: ['ajustes', 'bitacora'] },
  ],
  ICONOS: {
    resumen: '<path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10"/>',
    asistencia: '<path d="M9 11l3 3 8-8M20 12v7a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h9"/>',
    actividades: '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2M9 12h6M9 16h6"/>',
    notas: '<path d="M4 4h16v16H4zM4 10h16M4 15h16M10 4v16"/>',
    examenes: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
    resultados: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    estudiantes: '<path d="M17 21v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2M10 11a4 4 0 100-8 4 4 0 000 8M21 21v-2a4 4 0 00-3-3.9M16 3.1a4 4 0 010 7.8"/>',
    reportes: '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8zM14 3v5h5M9 13h6M9 17h6"/>',
    ajustes: '<path d="M12 15a3 3 0 100-6 3 3 0 000 6M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
    bitacora: '<path d="M12 8v4l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>',
  },
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

// Sube un archivo tal cual (cuerpo binario) y devuelve el JSON; lanza Error con el detalle del servidor
Panel.subir = async function (url, archivo) {
  const response = await Panel.api(url, {
    method: 'POST', body: await archivo.arrayBuffer(), headers: { 'Content-Type': 'application/octet-stream' },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((Array.isArray(data.detail) ? 'Datos no válidos' : data.detail) || 'Error del servidor');
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

// ========== LENGUAJE CLARO ==========
Panel.ETIQUETA_ALERTA = {
  riesgo: 'En riesgo', asistencia: 'Ausencias', pendientes: 'Sin entrega', examen: 'Examen pendiente',
  vencido: 'Tiempo agotado', salidas: 'Salió de la pestaña', bloqueados: 'Acceso bloqueado', temporales: 'Clave temporal',
  sospechosos: 'Intento sospechoso', respaldo: 'Copia de respaldo',
};

Panel.FRASES = {
  guardar_notas: 'Guardaste notas', importar_prueba: 'Importaste las notas de un examen', importar_hoja: 'Cargaste una hoja de notas',
  guardar_ponderaciones: 'Cambiaste la ponderación', publicar_notas: 'Publicaste notas a los estudiantes', ocultar_notas: 'Ocultaste notas a los estudiantes',
  pasar_lista: 'Pasaste lista', eliminar_lista: 'Eliminaste una lista de asistencia', crear_actividad: 'Creaste una actividad',
  editar_actividad: 'Editaste una actividad', eliminar_actividad: 'Eliminaste una actividad', calificar_actividad: 'Calificaste una actividad',
  importar_actividad: 'Importaste una actividad desde Excel', configurar_examen: 'Configuraste un examen', guardar_ajustes: 'Guardaste los ajustes',
  guardar_ficha: 'Actualizaste la ficha de un estudiante', agregar_observacion: 'Agregaste una observación', eliminar_observacion: 'Eliminaste una observación',
  importar_encargados: 'Importaste datos de encargados', importar_estudiantes: 'Importaste estudiantes', crear_estudiante: 'Creaste un estudiante',
  eliminar_estudiante: 'Eliminaste un estudiante', activar_cuenta: 'Activaste una cuenta', desactivar_cuenta: 'Desactivaste una cuenta',
  cambiar_seccion: 'Cambiaste a un estudiante de grupo', reiniciar_password: 'Reiniciaste una contraseña', reiniciar_seccion: 'Reiniciaste las contraseñas de un grupo',
  desbloquear_login: 'Desbloqueaste el acceso de un estudiante', reiniciar_intento: 'Permitiste repetir un examen', anular_intento: 'Anulaste un intento de examen',
  restaurar_intento: 'Restauraste un intento de examen', marcar_sospechoso: 'Marcaste un intento como sospechoso', quitar_sospechoso: 'Quitaste la marca de sospechoso',
  cerrar_examen_en_curso: 'Cerraste y calificaste los intentos abiertos de un examen',
  exigir_cambio_clave: 'Pediste a un grupo que cambie su contraseña', cambiar_clave_docente: 'Cambiaste tu contraseña del panel',
  cerrar_intento: 'Cerraste un examen en curso', tiempo_extra: 'Diste tiempo extra', cierre_curso: 'Cerraste el curso lectivo',
};
Panel.frase = (accion) => Panel.FRASES[accion] || accion.replace(/_/g, ' ');

// Botón de ayuda «?» con explicación breve (visible con el ratón, el foco y los lectores de pantalla)
Panel.ayuda = (texto) => `<button type="button" class="doc-ayuda" aria-label="Ayuda: ${Panel.esc(texto)}" title="${Panel.esc(texto)}">?</button>`;

// Desactiva el botón y muestra «Guardando…» mientras dura la operación
Panel.conCarga = async function (boton, operacion, texto = 'Guardando…') {
  const original = boton.textContent;
  boton.disabled = true;
  boton.textContent = texto;
  try { return await operacion(); } finally { boton.disabled = false; boton.textContent = original; }
};

// ========== MENÚ DESPLEGABLE (acciones secundarias) ==========
// items: [{ texto, accion, peligro? }, { grupo: 'Título' }, { separador: true }]. Se cierra al elegir, con Escape, Tab o al hacer clic fuera.
Panel.menuDesplegable = function (boton, items) {
  boton.setAttribute('aria-haspopup', 'menu');
  boton.setAttribute('aria-expanded', 'false');
  let menu = null;
  const cerrar = () => {
    if (!menu) return;
    menu.remove();
    menu = null;
    boton.setAttribute('aria-expanded', 'false');
    document.removeEventListener('mousedown', fuera, true);
    document.removeEventListener('keydown', teclas, true);
  };
  const fuera = (e) => { if (menu && !menu.contains(e.target) && e.target !== boton) cerrar(); };
  const teclas = (e) => {
    if (!menu) return;
    const opciones = [...menu.querySelectorAll('[role=menuitem]')];
    const i = opciones.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.stopPropagation(); cerrar(); boton.focus(); }
    if (e.key === 'Tab') cerrar();
    if (e.key === 'Home') { e.preventDefault(); opciones[0].focus(); }
    if (e.key === 'End') { e.preventDefault(); opciones[opciones.length - 1].focus(); }
    if (e.key === 'ArrowDown') { e.preventDefault(); opciones[(i + 1) % opciones.length].focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); opciones[(i - 1 + opciones.length) % opciones.length].focus(); }
  };
  const abrir = () => {
    menu = document.createElement('div');
    menu.className = 'doc-menu';
    menu.setAttribute('role', 'menu');
    if (boton.id) menu.setAttribute('aria-labelledby', boton.id);
    menu.innerHTML = items.map((it, k) => {
      if (it.separador) return '<div class="doc-menu-sep" role="separator"></div>';
      if (it.grupo) return `<div class="doc-menu-grupo" role="presentation">${Panel.esc(it.grupo)}</div>`;
      return `<button type="button" role="menuitem" class="doc-menu-item ${it.peligro ? 'peligro' : ''}" data-k="${k}">${Panel.esc(it.texto)}</button>`;
    }).join('');
    menu.addEventListener('click', (e) => {
      const b = e.target.closest('[data-k]');
      if (!b) return;
      cerrar();
      Promise.resolve(items[Number(b.dataset.k)].accion()).catch(err => Panel.toast(err.message, 'error'));
    });
    document.body.appendChild(menu);
    const r = boton.getBoundingClientRect();
    menu.style.top = `${Math.min(r.bottom + 4, window.innerHeight - menu.offsetHeight - 8) + window.scrollY}px`;
    menu.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - menu.offsetWidth - 8)) + window.scrollX}px`;
    boton.setAttribute('aria-expanded', 'true');
    document.addEventListener('mousedown', fuera, true);
    document.addEventListener('keydown', teclas, true);
    menu.querySelector('[role=menuitem]').focus();
  };
  boton.addEventListener('click', () => (menu ? cerrar() : abrir()));
};

// ========== NAVEGACIÓN POR CELDAS (hojas de notas) ==========
// Enter o flecha abajo pasa a la misma columna de la fila siguiente; flecha arriba, a la anterior.
Panel.navegarCeldas = function (tabla) {
  tabla.addEventListener('keydown', (e) => {
    const campo = e.target;
    if (!campo.matches || !campo.matches('input[type=number]')) return;
    const baja = e.key === 'Enter' || e.key === 'ArrowDown';
    if (!baja && e.key !== 'ArrowUp') return;
    const celda = campo.closest('td');
    const fila = campo.closest('tr');
    const vecina = baja ? fila.nextElementSibling : fila.previousElementSibling;
    if (!vecina) return;
    const destino = vecina.children[[...fila.children].indexOf(celda)].querySelector('input[type=number]');
    if (destino) { e.preventDefault(); destino.focus(); destino.select(); }
  });
};

// ========== TABLAS ORDENABLES ==========
// Orden por columnas: los encabezados <th> con <button data-orden="clave"> alternan asc/desc.
Panel.ordenable = function (tabla, getters, estado, alCambiar) {
  const pintar = () => tabla.querySelectorAll('th').forEach(th => {
    const b = th.querySelector('[data-orden]');
    if (!b) return;
    const activo = b.dataset.orden === estado.clave;
    th.setAttribute('aria-sort', activo ? (estado.dir === 1 ? 'ascending' : 'descending') : 'none');
    b.querySelector('.doc-flecha').textContent = activo ? (estado.dir === 1 ? '▲' : '▼') : '';
  });
  tabla.addEventListener('click', e => {
    const b = e.target.closest('[data-orden]');
    if (!b) return;
    estado.dir = estado.clave === b.dataset.orden ? -estado.dir : 1;
    estado.clave = b.dataset.orden;
    pintar();
    alCambiar();
  });
  pintar();
  return function ordenar(lista) {
    const get = getters[estado.clave];
    if (!get) return lista;
    return [...lista].sort((a, b) => {
      const x = get(a), y = get(b);
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;   // vacíos siempre al final
      if (y === null || y === undefined) return -1;
      return (typeof x === 'string' ? x.localeCompare(y, 'es') : x - y) * estado.dir;
    });
  };
};

Panel.th = (clave, texto) =>
  `<th scope="col" aria-sort="none"><button type="button" class="doc-th" data-orden="${clave}">${texto} <span class="doc-flecha" aria-hidden="true"></span></button></th>`;

// ========== AVISOS ==========
Panel.toast = function (mensaje, tipo = 'ok') {
  const t = document.createElement('div');
  t.className = `doc-toast ${tipo}`;
  t.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  const texto = document.createElement('span');
  texto.textContent = mensaje;
  const cerrar = document.createElement('button');
  cerrar.type = 'button';
  cerrar.className = 'doc-toast-cerrar';
  cerrar.setAttribute('aria-label', 'Cerrar aviso');
  cerrar.textContent = '×';
  cerrar.addEventListener('click', () => t.remove());
  t.append(texto, cerrar);
  $('doc-toasts').appendChild(t);
  setTimeout(() => t.remove(), tipo === 'error' ? 8000 : 4000);
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
          ${botones.map((b, i) => `<button type="button" class="btn ${b.peligro ? 'btn-danger' : b.primario ? 'btn-primary' : 'btn-secondary'}" data-i="${i}">${Panel.esc(b.texto)}</button>`).join('')}
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
    botones: [{ texto: 'Cancelar', valor: false }, { texto, valor: true, primario: !peligro, peligro }],
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

// Imprime (o guarda como PDF desde el diálogo de impresión) un fragmento HTML con estilo institucional claro
const ESTILO_IMPRESION = `
  body { font-family: 'DM Sans', Arial, sans-serif; color: #111; margin: 24px; font-size: 12px; }
  h1 { font-size: 18px; margin: 0 0 2px; } h2 { font-size: 14px; margin: 18px 0 6px; border-bottom: 1px solid #999; padding-bottom: 2px; }
  .rep-meta { color: #555; margin: 0 0 10px; } .rep-vacio { color: #777; font-style: italic; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 8px; } th, td { border: 1px solid #bbb; padding: 4px 6px; text-align: left; }
  th { background: #eee; } .num { text-align: right; } .rep-aprobado { color: #0a7a45; font-weight: 700; } .rep-reprobado { color: #b3261e; font-weight: 700; }
  .rep-kpis { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 12px; } .rep-kpi { border: 1px solid #bbb; padding: 6px 12px; min-width: 90px; }
  .rep-kpi strong { display: block; font-size: 16px; } .rep-firma { margin-top: 48px; display: flex; gap: 48px; }
  .rep-firma div { border-top: 1px solid #333; padding-top: 4px; width: 200px; text-align: center; }
  svg text { fill: #333; } @page { margin: 14mm; }
  .rep-centro { text-align: center; } .rep-firma-centro { justify-content: center; margin-top: 60px; }
  .rep-pagina { page-break-after: always; } .rep-pagina:last-of-type { page-break-after: auto; } .rep-acta { line-height: 1.6; }`;

Panel.imprimirHtml = function (titulo, html) {
  const marco = document.createElement('iframe');
  marco.setAttribute('aria-hidden', 'true');
  marco.style.cssText = 'position:fixed;width:0;height:0;border:0;';
  document.body.appendChild(marco);
  const doc = marco.contentWindow.document;
  doc.open();
  doc.write(`<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>${Panel.esc(titulo)}</title>
    <style>${ESTILO_IMPRESION}</style></head><body>${html}</body></html>`);
  doc.close();
  setTimeout(() => {
    marco.contentWindow.focus();
    marco.contentWindow.print();
    setTimeout(() => marco.remove(), 1500);
  }, 150);
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
    $('doc-sesion').innerHTML = `<span class="doc-sesion-pref">Sesión: </span>${m >= 60 ? Math.floor(m / 60) + ' h ' + (m % 60) + ' min' : m + ' min'}`;
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
  const ids = Panel.GRUPOS.flatMap(g => g.ids);
  const ordenados = ids.map(id => Panel.modulos.find(m => m.id === id)).filter(Boolean);
  const icono = (id) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${Panel.ICONOS[id] || ''}</svg>`;
  $('doc-nav').innerHTML = Panel.GRUPOS.map(g => {
    const items = g.ids.map(id => Panel.modulos.find(m => m.id === id)).filter(Boolean);
    return items.length ? `<div class="doc-nav-grupo"><p class="doc-nav-titulo">${Panel.esc(g.titulo)}</p>${items.map(m =>
      `<button type="button" class="doc-nav-item" id="tabbtn-${m.id}" data-tab="${m.id}" title="${Panel.esc(m.titulo)}">${icono(m.id)}<span>${Panel.esc(m.titulo)}</span></button>`).join('')}</div>` : '';
  }).join('') + '<button type="button" class="doc-nav-contraer" id="doc-nav-contraer" aria-pressed="false" title="Contraer el menú"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg><span>Contraer menú</span></button>';
  $('doc-contenido').innerHTML = `<div id="doc-vacio-ctx" class="doc-vacio" hidden><h2>Aún no hay materias</h2><p>Esta sección trabaja sobre un grupo y una materia. Cuando haya estudiantes y materias registrados, aparecerán en el selector de arriba.</p></div>` + ordenados.map(m =>
    `<section id="tab-${m.id}" class="doc-section" aria-labelledby="tabbtn-${m.id}" hidden></section>`
  ).join('');
  ordenados.forEach(m => { if (m.init) m.init($(`tab-${m.id}`)); });
  Panel.ordenados = ordenados;
  let compacto = false;
  try { compacto = localStorage.getItem('menuCompacto') === '1'; } catch (e) { /* sin almacenamiento */ }
  Panel.menuCompacto(compacto);
};

Panel.menuCompacto = function (valor) {
  document.querySelector('.doc-cuerpo').classList.toggle('doc-nav-compacto', valor);
  $('doc-nav-contraer').setAttribute('aria-pressed', valor ? 'true' : 'false');
  $('doc-nav-contraer').title = valor ? 'Expandir el menú' : 'Contraer el menú';
  try { localStorage.setItem('menuCompacto', valor ? '1' : '0'); } catch (e) { /* sin almacenamiento */ }
};

Panel.abrirMenu = function (abrir) {
  $('doc-nav').classList.toggle('abierto', abrir);
  $('doc-nav-fondo').hidden = !abrir;
  $('doc-menu-btn').setAttribute('aria-expanded', abrir ? 'true' : 'false');
};

Panel.irA = async function (id) {
  const modulo = Panel.ordenados.find(m => m.id === id);
  if (!modulo) return;
  Panel.moduloActivo = id;
  Panel.abrirMenu(false);
  document.querySelectorAll('.doc-nav-item').forEach(b => {
    const activa = b.dataset.tab === id;
    b.classList.toggle('active', activa);
    if (activa) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  $('doc-contexto').hidden = !modulo.usaContexto;
  const sinMaterias = modulo.usaContexto && !Panel.contexto.id();
  $('doc-vacio-ctx').hidden = !sinMaterias;
  Panel.ordenados.forEach(m => { $(`tab-${m.id}`).hidden = m.id !== id || sinMaterias; });
  sessionStorage.setItem('docenteTab', id);
  if (!modulo.mostrar || sinMaterias) return;
  const seccion = $(`tab-${id}`);
  seccion.classList.add('doc-cargando');
  seccion.setAttribute('aria-busy', 'true');
  seccion.querySelectorAll(':scope > .doc-aviso-error').forEach(e => e.remove());
  try {
    await modulo.mostrar();
  } catch (e) {
    if (e.message === 'Sesión expirada') return;
    Panel.toast(e.message, 'error');
    const aviso = document.createElement('div');
    aviso.className = 'doc-aviso-error';
    aviso.setAttribute('role', 'alert');
    aviso.innerHTML = `<span>No se pudo cargar esta sección: ${Panel.esc(e.message)}</span><button type="button" class="btn btn-secondary">Reintentar</button>`;
    aviso.querySelector('button').addEventListener('click', () => Panel.irA(id));
    seccion.prepend(aviso);
  } finally {
    seccion.classList.remove('doc-cargando');
    seccion.removeAttribute('aria-busy');
  }
};

// ========== CONTRASEÑA DEL DOCENTE ==========
// Muestra el aviso fijo mientras se use la contraseña de fábrica (que es pública).
Panel.avisoClave = function (deFabrica) {
  $('doc-aviso-clave').hidden = !deFabrica;
};

Panel.cambiarClaveDocente = async function () {
  for (;;) {
    const datos = await Panel.dialogo({
      titulo: 'Cambiar la contraseña del docente',
      cuerpo: `<p class="doc-muted">Usa al menos 8 caracteres. Se guarda cifrada en este computador.</p>
        <label class="doc-campo">Contraseña actual <input type="password" id="clave-actual" autocomplete="current-password"></label>
        <label class="doc-campo">Contraseña nueva <input type="password" id="clave-nueva" autocomplete="new-password" minlength="8"></label>
        <label class="doc-campo">Repite la nueva <input type="password" id="clave-repetir" autocomplete="new-password"></label>`,
      botones: [{ texto: 'Cancelar', valor: null }, { texto: 'Cambiar contraseña', primario: true, valor: f => ({
        actual: f.querySelector('#clave-actual').value, nueva: f.querySelector('#clave-nueva').value,
        repetir: f.querySelector('#clave-repetir').value }) }],
    });
    if (!datos) return false;
    if (datos.nueva !== datos.repetir) { Panel.toast('Las contraseñas nuevas no coinciden', 'error'); continue; }
    try {
      await Panel.json('/api/docente/cambiar-password', { method: 'POST', body: { actual: datos.actual, nueva: datos.nueva } });
    } catch (e) { Panel.toast(e.message, 'error'); continue; }
    Panel.avisoClave(false);
    Panel.toast('Contraseña cambiada. Úsala la próxima vez que entres.');
    return true;
  }
};

// ========== CONTEXTO: grupo, período y materia compartidos por las pestañas ==========
// Las pestañas con `usaContexto: true` leen Panel.contexto.materia() en lugar de tener su propio selector.
Panel.contexto = {
  materias: [],
  actual: null,

  async cargar() {
    const [data, ajustes] = await Promise.all([Panel.json('/api/docente/materias'), Panel.json('/api/docente/ajustes')]);
    this.materias = data.materias;
    Panel.avisoClave(ajustes.clave_de_fabrica);
    let guardada = null;
    try { guardada = Number(localStorage.getItem('contextoMateria')) || null; } catch (e) { /* sin almacenamiento */ }
    const periodo = Number(ajustes.ajustes.periodo_actual);
    this.actual = this.materias.find(m => m.id === guardada)
      || this.materias.find(m => m.periodo === periodo) || this.materias[0] || null;
    this.dibujar();
  },

  materia() { return this.actual; },
  id() { return this.actual ? this.actual.id : null; },

  // Botones segmentados (un toque) para pocas opciones: Grupo y Período
  segmentos(id, opciones, actual) {
    $(id).innerHTML = opciones.map(o => `<button type="button" role="radio" class="doc-seg-op" data-valor="${Panel.esc(String(o.valor))}"
      aria-checked="${String(o.valor) === String(actual)}" tabindex="${String(o.valor) === String(actual) ? 0 : -1}"
      ${o.aria ? `aria-label="${Panel.esc(o.aria)}"` : ''}>${Panel.esc(o.texto)}</button>`).join('');
  },

  dibujar() {
    const m = this.actual;
    const unicos = (lista) => [...new Set(lista)];
    this.segmentos('ctx-seccion', unicos(this.materias.map(x => x.seccion)).map(s => ({ valor: s, texto: s, aria: `Grupo ${s}` })), m && m.seccion);
    if (!m) return;
    this.segmentos('ctx-periodo', unicos(this.materias.filter(x => x.seccion === m.seccion).map(x => x.periodo))
      .map(p => ({ valor: p, texto: `${p}.º`, aria: `${p}.º período` })), m.periodo);
    $('ctx-materia').innerHTML = this.materias.filter(x => x.seccion === m.seccion && x.periodo === m.periodo)
      .map(x => `<option value="${x.id}">${Panel.esc(x.nombre)}</option>`).join('');
    $('ctx-materia').value = String(m.id);
    $('ctx-materia').title = m.nombre;
  },

  // Cambia a la materia que corresponde a (sección, período, materia) pidiendo permiso a la pestaña activa
  async elegir(seccion, periodo, materiaId) {
    const modulo = Panel.ordenados.find(x => x.id === Panel.moduloActivo);
    const previa = this.actual;
    let destino = this.materias.find(x => x.id === materiaId);
    if (!destino) {
      if (periodo === null) {
        const delGrupo = this.materias.filter(x => x.seccion === seccion);
        periodo = previa && delGrupo.some(x => x.periodo === previa.periodo) ? previa.periodo : (delGrupo[0] || {}).periodo;
      }
      const mismas = this.materias.filter(x => x.seccion === seccion && x.periodo === periodo);
      destino = (previa && mismas.find(x => x.nombre === previa.nombre)) || mismas[0]
        || this.materias.find(x => x.seccion === seccion) || previa;
    }
    if (destino === previa) return this.dibujar();
    if (modulo && modulo.hayCambios && modulo.hayCambios() &&
        !(await Panel.confirmar('Tienes cambios sin guardar; se descartarán al cambiar de materia.', { texto: 'Cambiar de materia' }))) {
      return this.dibujar();
    }
    this.actual = destino;
    try { localStorage.setItem('contextoMateria', String(destino.id)); } catch (e) { /* sin almacenamiento */ }
    this.dibujar();
    if (!materiaId && previa && destino.nombre !== previa.nombre) {
      Panel.toast(`Ahora en ${destino.seccion} · ${destino.periodo}.º período · ${destino.nombre}`);
    }
    if (modulo && modulo.usaContexto && modulo.mostrar) {
      try { await modulo.mostrar(); } catch (e) { Panel.toast(e.message, 'error'); }
    }
  },
};

Panel.mostrarPanel = function () {
  $('doc-login').style.display = 'none';
  $('doc-panel').style.display = 'block';
  Panel.iniciarTemporizadorSesion();
  if (!Panel.ordenados) Panel.construirNavegacion();
  fetch('/api/config').then(r => r.json()).then(c => {
    if (c.institucion) $('doc-marca').textContent = c.institucion;
    if (c.version) $('doc-version').textContent = `· versión ${c.version}`;
  }).catch(() => {});
  const guardada = sessionStorage.getItem('docenteTab');
  Panel.contexto.cargar().catch(e => Panel.toast(e.message, 'error')).finally(() =>
    Panel.irA(Panel.ordenados.some(m => m.id === guardada) ? guardada : Panel.ordenados[0].id));
};

document.addEventListener('DOMContentLoaded', () => {
  $('doc-login-btn').addEventListener('click', Panel.entrar);
  $('doc-aviso-clave-btn').addEventListener('click', () => Panel.cambiarClaveDocente());
  $('doc-password').addEventListener('keypress', e => { if (e.key === 'Enter') Panel.entrar(); });
  $('doc-logout').addEventListener('click', () => Panel.salir());
  $('doc-nav').addEventListener('click', e => {
    const b = e.target.closest('[data-tab]');
    if (b) Panel.irA(b.dataset.tab);
    if (e.target.closest('#doc-nav-contraer')) Panel.menuCompacto(!document.querySelector('.doc-cuerpo').classList.contains('doc-nav-compacto'));
  });
  $('doc-menu-btn').addEventListener('click', () => Panel.abrirMenu(!$('doc-nav').classList.contains('abierto')));
  $('doc-nav-fondo').addEventListener('click', () => Panel.abrirMenu(false));
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('doc-nav').classList.contains('abierto')) Panel.abrirMenu(false); });
  const seg = (id) => $(id).querySelector('[aria-checked="true"]').dataset.valor;
  $('ctx-seccion').addEventListener('click', e => {
    const b = e.target.closest('[data-valor]');
    if (b) Panel.contexto.elegir(b.dataset.valor, null, null);
  });
  $('ctx-periodo').addEventListener('click', e => {
    const b = e.target.closest('[data-valor]');
    if (b) Panel.contexto.elegir(seg('ctx-seccion'), Number(b.dataset.valor), null);
  });
  // Flechas dentro del grupo de botones (como un radiogroup nativo)
  document.querySelectorAll('.doc-seg').forEach(g => g.addEventListener('keydown', e => {
    const dir = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!dir) return;
    const ops = [...g.querySelectorAll('[role=radio]')];
    const sig = ops[(ops.indexOf(document.activeElement) + dir + ops.length) % ops.length];
    e.preventDefault();
    sig.click();
    // dibujar() rehace los botones: devolver el foco al que quedó marcado
    const marcado = g.querySelector('[aria-checked="true"]');
    if (marcado) marcado.focus();
  }));
  $('ctx-materia').addEventListener('change', () => Panel.contexto.elegir(null, null, Number($('ctx-materia').value)));
  if (Panel.token && expiracionToken(Panel.token) > Date.now()) Panel.mostrarPanel();
  else Panel.salir();
});
