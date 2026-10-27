// Panel docente: resultados de exámenes y módulo de notas
const COMPONENTES = ['trabajo_cotidiano', 'tareas', 'prueba01', 'prueba02', 'proyecto', 'asistencia'];
let token = sessionStorage.getItem('docenteToken');
let intentos = [];
let materias = [];
let ponderaciones = {};
let notasActuales = [];

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

async function api(url, options = {}) {
  const headers = Object.assign({ Authorization: `Bearer ${token}` }, options.headers);
  const response = await fetch(url, Object.assign({}, options, { headers }));
  if (response.status === 401) {
    salir();
    throw new Error('Sesión expirada');
  }
  return response;
}

async function descargar(url, nombre) {
  const response = await api(url);
  if (!response.ok) return alert('No se pudo exportar');
  const blob = await response.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ========== ACCESO ==========
async function entrar() {
  const error = $('doc-login-error');
  error.style.display = 'none';
  const response = await fetch('/api/verificar-docente', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: $('doc-password').value })
  });
  const data = await response.json().catch(() => ({}));
  if (response.ok && data.ok) {
    token = data.token;
    sessionStorage.setItem('docenteToken', token);
    $('doc-password').value = '';
    mostrarPanel();
  } else {
    error.textContent = response.status === 429 ? (data.detail || 'Demasiados intentos') : (data.error || 'Contraseña incorrecta');
    error.style.display = 'block';
  }
}

function salir() {
  token = null;
  sessionStorage.removeItem('docenteToken');
  $('doc-panel').style.display = 'none';
  $('doc-login').style.display = 'flex';
}

async function mostrarPanel() {
  $('doc-login').style.display = 'none';
  $('doc-panel').style.display = 'block';
  await Promise.all([cargarIntentos(), cargarMaterias()]);
}

function cambiarTab(nombre) {
  document.querySelectorAll('.doc-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === nombre));
  $('tab-resultados').style.display = nombre === 'resultados' ? 'block' : 'none';
  $('tab-notas').style.display = nombre === 'notas' ? 'block' : 'none';
}

// ========== RESULTADOS ==========
function nombreCompleto(i) {
  return `${i.apellido1} ${i.apellido2 || ''}, ${i.nombre}`.replace(/\s+/g, ' ');
}

function porcentaje(i) {
  return i.total ? Math.round((i.puntuacion / i.total) * 1000) / 10 : 0;
}

async function cargarIntentos() {
  const response = await api('/api/docente/intentos');
  intentos = (await response.json()).intentos;
  llenarFiltro('f-examen', [...new Set(intentos.map(i => i.codigo_examen))].sort());
  llenarFiltro('f-seccion', [...new Set(intentos.map(i => i.seccion))].sort());
  renderIntentos();
}

function llenarFiltro(id, valores) {
  const select = $(id);
  const actual = select.value;
  select.innerHTML = '<option value="">' + (id === 'f-examen' ? 'Todos' : 'Todas') + '</option>' +
    valores.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  select.value = valores.includes(actual) ? actual : '';
}

function renderIntentos() {
  const examen = $('f-examen').value;
  const seccion = $('f-seccion').value;
  const lista = intentos.filter(i => (!examen || i.codigo_examen === examen) && (!seccion || i.seccion === seccion));
  const enviados = lista.filter(i => i.fecha_fin);
  const promedio = enviados.length ? (enviados.reduce((s, i) => s + porcentaje(i), 0) / enviados.length).toFixed(1) : '-';
  $('res-resumen').textContent =
    `${lista.length} intentos · ${enviados.length} enviados · promedio ${promedio}` +
    (enviados.length < lista.length ? ` · ${lista.length - enviados.length} en curso o sin enviar` : '');

  $('tabla-intentos').querySelector('tbody').innerHTML = lista.map(i => {
    const enviado = !!i.fecha_fin;
    const estado = enviado ? '<span class="doc-pill ok">Enviado</span>' : '<span class="doc-pill wait">Sin enviar</span>';
    const salidas = i.incidencias > 0 ? `<span class="doc-pill warn">${i.incidencias}</span>` : '0';
    return `<tr>
      <td>${escapeHtml(nombreCompleto(i))}</td>
      <td>${escapeHtml(i.seccion)}</td>
      <td>${escapeHtml(i.codigo_examen)}</td>
      <td>${enviado ? `${i.puntuacion}/${i.total} (${porcentaje(i)})` : '<span class="doc-pending">-</span>'}</td>
      <td>${estado}</td>
      <td>${salidas}</td>
      <td class="doc-actions">
        ${enviado ? `<button class="btn btn-secondary" data-ver="${i.id}">Detalle</button>` : ''}
        <button class="btn btn-secondary" data-reiniciar="${i.id}">Reiniciar</button>
      </td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="doc-pending">Sin intentos</td></tr>';
}

async function verDetalle(id) {
  const response = await api(`/api/docente/intentos/${id}`);
  const { intento } = await response.json();
  const e = intento.estudiante;
  $('detalle-titulo').textContent = `${e.nombre} ${e.apellido1} ${e.apellido2 || ''}`.trim();
  $('detalle-sub').textContent =
    `${intento.codigo_examen} · Sección ${e.seccion} · ${intento.puntuacion}/${intento.total} · Salidas de la pestaña: ${intento.incidencias}`;
  $('detalle-lista').innerHTML = intento.preguntas.map(p => {
    const n = String(p.numero);
    const dada = intento.respuestas[n];
    const correcta = intento.respuestas_correctas[n];
    const ok = dada === correcta;
    const texto = (letra) => letra ? `${letra}) ${escapeHtml(p.opciones[letra])}` : 'Sin contestar';
    return `<div class="result-item ${ok ? 'correct' : 'wrong'}">
      <div class="result-question-header">
        <span class="result-question-num">${escapeHtml(p.numero)}.</span>
        <span class="result-question-topic">[${escapeHtml(p.tema)}]</span>
      </div>
      <div class="result-question-text">${escapeHtml(p.pregunta)}</div>
      <div class="result-details">
        <span class="user-answer">Respuesta: ${texto(dada)}</span>
        ${ok ? '' : `<span class="correct-answer">Correcta: ${texto(correcta)}</span>`}
        <span class="result-status">${ok ? '✓' : '✗'}</span>
      </div>
    </div>`;
  }).join('');
  $('detalle-overlay').classList.add('active');
}

async function reiniciar(id) {
  const i = intentos.find(x => x.id === id);
  if (!confirm(`¿Reiniciar el intento de ${nombreCompleto(i)} en ${i.codigo_examen}? Se borrará su resultado y podrá presentar el examen de nuevo.`)) return;
  await api(`/api/docente/intentos/${id}`, { method: 'DELETE' });
  await cargarIntentos();
}

// ========== NOTAS ==========
async function cargarMaterias() {
  const data = await (await api('/api/docente/materias')).json();
  materias = data.materias;
  ponderaciones = data.ponderaciones;
  document.querySelectorAll('[data-peso]').forEach(el => { el.textContent = `${ponderaciones[el.dataset.peso]}%`; });
  $('n-materia').innerHTML = materias.map(m =>
    `<option value="${m.id}">${escapeHtml(m.seccion)} · Periodo ${m.periodo} · ${escapeHtml(m.nombre)}</option>`).join('');
  await cargarNotas();
}

function calcularFinal(valores) {
  return Math.round(COMPONENTES.reduce((s, c) => s + (valores[c] || 0) * ponderaciones[c] / 100, 0) * 10) / 10;
}

async function cargarNotas() {
  const materiaId = $('n-materia').value;
  if (!materiaId) return;
  const data = await (await api(`/api/docente/notas?materia_id=${materiaId}`)).json();
  notasActuales = data.notas;
  $('tabla-notas').querySelector('tbody').innerHTML = notasActuales.map(n => `
    <tr data-id="${n.estudiante_id}">
      <td>${escapeHtml(`${n.apellido1} ${n.apellido2 || ''}, ${n.nombre}`.replace(/\s+/g, ' '))}</td>
      ${COMPONENTES.map(c => `<td><input type="number" min="0" max="100" step="0.1" data-c="${c}" value="${n[c] ?? ''}"></td>`).join('')}
      <td class="doc-final"></td>
    </tr>`).join('');
  document.querySelectorAll('#tabla-notas tbody tr').forEach(actualizarFila);
  actualizarResumenNotas();
}

function valoresDeFila(tr) {
  const valores = {};
  tr.querySelectorAll('input').forEach(input => {
    const v = input.value.trim();
    const num = v === '' ? null : Number(v);
    input.classList.toggle('invalid', num !== null && (Number.isNaN(num) || num < 0 || num > 100));
    valores[input.dataset.c] = num;
  });
  return valores;
}

function actualizarFila(tr) {
  const valores = valoresDeFila(tr);
  const final = calcularFinal(valores);
  const celda = tr.querySelector('.doc-final');
  const vacia = COMPONENTES.every(c => valores[c] === null);
  celda.textContent = vacia ? '—' : final.toFixed(1);
  celda.classList.toggle('doc-pending', vacia);
  celda.classList.toggle('low', !vacia && final < 70);
  celda.classList.toggle('good', !vacia && final >= 70);
}

function actualizarResumenNotas() {
  const finales = [...document.querySelectorAll('#tabla-notas tbody tr')].map(tr => {
    const v = valoresDeFila(tr);
    return COMPONENTES.every(c => v[c] !== null) ? calcularFinal(v) : null;
  }).filter(x => x !== null);
  const total = document.querySelectorAll('#tabla-notas tbody tr').length;
  $('notas-resumen').textContent = finales.length
    ? `${finales.length}/${total} estudiantes con notas completas · promedio ${(finales.reduce((a, b) => a + b, 0) / finales.length).toFixed(1)} · máx ${Math.max(...finales)} · mín ${Math.min(...finales)}`
    : `${total} estudiantes · aún sin notas completas`;
}

async function guardarNotas() {
  const filas = [...document.querySelectorAll('#tabla-notas tbody tr')];
  if (document.querySelector('#tabla-notas input.invalid')) return alert('Hay notas fuera del rango 0-100');
  const notas = filas.map(tr => ({ estudiante_id: Number(tr.dataset.id), ...valoresDeFila(tr) }));
  const response = await api('/api/docente/notas', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ materia_id: Number($('n-materia').value), notas })
  });
  alert(response.ok ? 'Notas guardadas' : 'No se pudieron guardar las notas');
}

async function importarPrueba(componente) {
  const codigo = prompt(`Código del examen a importar como ${componente === 'prueba01' ? 'Prueba 01' : 'Prueba 02'} (ej. SGC01):`);
  if (!codigo) return;
  if (!confirm('Esto reemplaza esa columna para los estudiantes que enviaron el examen. Las demás notas sin guardar se descartarán. ¿Continuar?')) return;
  const response = await api('/api/docente/notas/importar-prueba', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ materia_id: Number($('n-materia').value), componente, codigo_examen: codigo.trim() })
  });
  const data = await response.json();
  alert(response.ok ? `Se importaron ${data.importadas} notas` : (data.detail || 'No se pudo importar'));
  await cargarNotas();
}

// ========== INIT ==========
document.addEventListener('DOMContentLoaded', () => {
  $('doc-login-btn').addEventListener('click', entrar);
  $('doc-password').addEventListener('keypress', e => { if (e.key === 'Enter') entrar(); });
  $('doc-logout').addEventListener('click', salir);
  document.querySelectorAll('.doc-tab').forEach(b => b.addEventListener('click', () => cambiarTab(b.dataset.tab)));

  $('f-examen').addEventListener('change', renderIntentos);
  $('f-seccion').addEventListener('change', renderIntentos);
  $('btn-refrescar').addEventListener('click', cargarIntentos);
  $('btn-exportar-intentos').addEventListener('click', () => descargar('/api/docente/intentos-exportar', 'intentos.csv'));
  $('tabla-intentos').addEventListener('click', e => {
    if (e.target.dataset.ver) verDetalle(Number(e.target.dataset.ver));
    if (e.target.dataset.reiniciar) reiniciar(Number(e.target.dataset.reiniciar));
  });
  $('detalle-cerrar').addEventListener('click', () => $('detalle-overlay').classList.remove('active'));

  $('n-materia').addEventListener('change', cargarNotas);
  $('tabla-notas').addEventListener('input', e => {
    if (e.target.matches('input')) {
      actualizarFila(e.target.closest('tr'));
      actualizarResumenNotas();
    }
  });
  $('btn-guardar-notas').addEventListener('click', guardarNotas);
  $('btn-importar-p01').addEventListener('click', () => importarPrueba('prueba01'));
  $('btn-importar-p02').addEventListener('click', () => importarPrueba('prueba02'));
  $('btn-exportar-notas').addEventListener('click', () => {
    const id = $('n-materia').value;
    if (id) descargar(`/api/docente/notas/exportar?materia_id=${id}`, `notas_${id}.csv`);
  });

  if (token) mostrarPanel().catch(() => salir());
});
