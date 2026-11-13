// Pantalla "Mis notas": lo que el docente publicó de las materias del estudiante (solo lectura, pensada para el celular)
function misNotasNum(n, dec = 2) {
  return n === null || n === undefined ? '—' : String(Math.round(n * 10 ** dec) / 10 ** dec);
}

function misNotasEstado(codigo) {
  return { A: 'ausente', T: 'tardía', TM: 'tardía (más de 10 min)', AJ: 'ausencia justificada', TJ: 'tardía justificada' }[codigo] || codigo;
}

const MN_ICONO_OK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
const MN_ICONO_AVISO = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><path d="M12 8v5M12 17h.01"/><circle cx="12" cy="12" r="10"/></svg>';

function misNotasHtmlMateria(m, minima, indice) {
  const e = escapeHtml;
  const asis = m.asistencia;
  const pendientes = m.actividades.filter(a => a.estado === 'sin_entrega');
  const estado = m.aprobado
    ? `<span class="grades-chip ok">${MN_ICONO_OK} Vas aprobando</span>`
    : `<span class="grades-chip low">${MN_ICONO_AVISO} Por debajo de ${misNotasNum(minima, 0)}</span>`;
  return `<section class="grades-card" aria-labelledby="mn-titulo-${indice}">
    <h2 id="mn-titulo-${indice}">${e(m.materia)}</h2>
    <p class="grades-periodo">${m.periodo}.º período</p>
    <div class="grades-final"><strong class="${m.aprobado ? 'ok' : 'low'}">${misNotasNum(m.nota_final, 1)}</strong>
      <div>${estado}<span class="grades-muted">${m.completa ? '' : 'Nota parcial: faltan componentes por calificar.'}</span></div></div>
    <label class="grades-barra">
      <span class="grades-muted">Tu nota de 100 · mínimo para aprobar: ${misNotasNum(minima, 0)}</span>
      <progress class="${m.aprobado ? 'ok' : 'low'}" max="100" value="${Math.min(100, m.nota_final)}">${misNotasNum(m.nota_final, 1)}</progress>
    </label>
    <h3>Cómo se forma tu nota</h3>
    <ul class="grades-comp">${m.componentes.map(c => `<li>
      <span>${e(c.etiqueta)}</span>
      <progress max="${c.peso}" value="${c.puntos ?? 0}" aria-label="${e(c.etiqueta)}">${misNotasNum(c.puntos)}</progress>
      <strong>${misNotasNum(c.puntos)} <span class="grades-muted">de ${misNotasNum(c.peso)}</span></strong></li>`).join('')}</ul>
    <h3>Asistencia</h3>
    ${asis ? `<p>${asis.lecciones} lecciones · ${asis.ausencias} ausencias · ${asis.tardias} tardías · ${asis.justificadas} justificadas.
        Ausencias injustificadas: ${misNotasNum(asis.porcentaje, 1)} % → <strong>${asis.puntos} de ${asis.maximo} puntos</strong>.</p>
      ${asis.detalle.length ? `<p class="grades-muted">${asis.detalle.map(d => `${d.fecha.split('-').reverse().join('/')}: ${e(misNotasEstado(d.estado))}`).join(' · ')}</p>` : ''}`
      : '<p class="grades-muted">Todavía no hay listas de asistencia en este período.</p>'}
    ${m.actividades.length ? `<h3>Actividades</h3><ul class="grades-acts">${m.actividades.map(a => `<li>
        <div class="grades-act-cab"><strong>${e(a.nombre)}</strong>
          <span>${a.estado === 'sin_entrega' ? '0' : misNotasNum(a.puntos)} / ${misNotasNum(a.puntos_max)}</span></div>
        <span class="grades-muted">${e(a.componente)} · ${e(a.estado_texto)}</span>
        ${a.observacion ? `<p class="grades-obs">${e(a.observacion)}</p>` : ''}</li>`).join('')}</ul>` : ''}
    ${pendientes.length ? `<p class="grades-alert">Pendiente de entregar: ${pendientes.map(a => e(a.nombre)).join('; ')}.</p>` : ''}
  </section>`;
}

async function abrirMisNotas() {
  const overlay = document.getElementById('grades-overlay');
  const cont = document.getElementById('grades-content');
  cont.innerHTML = '<p class="grades-empty">Cargando…</p>';
  abrirDialogo('grades-overlay', 'grades-title');
  try {
    const r = await authFetch('/api/mis-notas');
    if (r.status === 401) {
      // La sesión venció (dura 12 horas): se cierra todo y se vuelve a la pantalla de entrada con un aviso
      cerrarDialogo('grades-overlay');
      logout();
      mostrarAviso('Tu sesión terminó. Vuelve a entrar con tu usuario y tu contraseña.');
      return;
    }
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'No se pudieron cargar tus notas');
    cont.innerHTML = `<p class="grades-sub">${escapeHtml(d.nombre)} · Sección ${escapeHtml(d.seccion)} · ${escapeHtml(d.institucion)} ${escapeHtml(d.curso_lectivo)}</p>` +
      (d.materias.length ? d.materias.map((m, i) => misNotasHtmlMateria(m, d.nota_minima, i)).join('')
        : '<p class="grades-empty">Tu docente todavía no ha publicado notas. Vuelve a revisar más tarde.</p>');
  } catch (e) {
    cont.innerHTML = `<p class="grades-alert">${escapeHtml(e.message)}</p>`;
  }
}

function cerrarMisNotas() {
  cerrarDialogo('grades-overlay'); // devuelve el foco al botón «Ver mis notas»
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && document.getElementById('grades-overlay').classList.contains('active')) cerrarMisNotas();
});
