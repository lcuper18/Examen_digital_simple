// Pantalla "Mis notas": lo que el docente publicó de las materias del estudiante (solo lectura)
function misNotasNum(n, dec = 2) {
  return n === null || n === undefined ? '—' : String(Math.round(n * 10 ** dec) / 10 ** dec);
}

function misNotasHtmlMateria(m, minima) {
  const e = escapeHtml;
  const asis = m.asistencia;
  const pendientes = m.actividades.filter(a => a.estado === 'sin_entrega');
  return `<section class="grades-card" aria-labelledby="mn-${e(m.materia)}-${m.periodo}">
    <h2 id="mn-${e(m.materia)}-${m.periodo}">${e(m.materia)}</h2>
    <p class="grades-periodo">Período ${m.periodo}</p>
    <div class="grades-final"><strong class="${m.aprobado ? 'ok' : 'low'}">${misNotasNum(m.nota_final, 1)}</strong>
      <span>${m.aprobado ? 'Vas aprobando' : 'Por debajo de ' + minima}${m.completa ? '' : ' · nota parcial: faltan componentes por calificar'}</span></div>
    <table class="grades-table"><caption class="grades-muted grades-caption">Componentes de la nota</caption>
      <thead><tr><th scope="col">Componente</th><th scope="col" class="num">Valor</th><th scope="col" class="num">Obtenido</th></tr></thead>
      <tbody>${m.componentes.map(c => `<tr><td>${e(c.etiqueta)}</td><td class="num">${misNotasNum(c.peso)}</td><td class="num">${misNotasNum(c.puntos)}</td></tr>`).join('')}</tbody></table>
    <h3>Asistencia</h3>
    ${asis ? `<p>${asis.lecciones} lecciones impartidas · ${asis.ausencias} ausencias · ${asis.tardias} tardías · ${asis.justificadas} justificadas.
        Ausencias injustificadas: ${misNotasNum(asis.porcentaje, 1)} % → <strong>${asis.puntos} de ${asis.maximo} puntos</strong>.</p>
      ${asis.detalle.length ? `<p class="grades-muted">${asis.detalle.map(d => `${d.fecha.split('-').reverse().join('/')}: ${e(misNotasEstado(d.estado))}`).join(' · ')}</p>` : ''}`
      : '<p class="grades-muted">Todavía no hay listas de asistencia en este período.</p>'}
    ${m.actividades.length ? `<h3>Actividades</h3><table class="grades-table"><thead><tr><th scope="col">Actividad</th><th scope="col">Estado</th>
        <th scope="col" class="num">Puntos</th></tr></thead><tbody>
      ${m.actividades.map(a => `<tr><td>${e(a.nombre)}<br><span class="grades-muted">${e(a.componente)}${a.observacion ? ' · ' + e(a.observacion) : ''}</span></td>
        <td>${e(a.estado_texto)}</td><td class="num">${a.estado === 'sin_entrega' ? '0' : misNotasNum(a.puntos)} / ${misNotasNum(a.puntos_max)}</td></tr>`).join('')}</tbody></table>` : ''}
    ${pendientes.length ? `<p class="grades-alert">Pendiente de entregar: ${pendientes.map(a => e(a.nombre)).join('; ')}.</p>` : ''}
  </section>`;
}

function misNotasEstado(codigo) {
  return { A: 'ausente', T: 'tardía', TM: 'tardía (más de 10 min)', AJ: 'ausencia justificada', TJ: 'tardía justificada' }[codigo] || codigo;
}

async function abrirMisNotas() {
  const overlay = document.getElementById('grades-overlay');
  const cont = document.getElementById('grades-content');
  cont.innerHTML = '<p class="grades-empty">Cargando…</p>';
  overlay.classList.add('active');
  try {
    const r = await authFetch('/api/mis-notas');
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'No se pudieron cargar tus notas');
    cont.innerHTML = `<p class="grades-sub">${escapeHtml(d.nombre)} · Sección ${escapeHtml(d.seccion)} · ${escapeHtml(d.institucion)} ${escapeHtml(d.curso_lectivo)}</p>` +
      (d.materias.length ? d.materias.map(m => misNotasHtmlMateria(m, d.nota_minima)).join('')
        : '<p class="grades-empty">Tu docente todavía no ha publicado notas.</p>');
  } catch (e) {
    cont.innerHTML = `<p class="grades-alert">${escapeHtml(e.message)}</p>`;
  }
}

function cerrarMisNotas() {
  document.getElementById('grades-overlay').classList.remove('active');
}
