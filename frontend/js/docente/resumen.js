// Pestaña Resumen: tablero con totales, alertas, exámenes en curso y actividad reciente
(function () {
  let refresco = null;

  const kpi = (etiqueta, valor, nota = '') =>
    `<div class="rep-kpi">${Panel.esc(etiqueta)}<strong>${Panel.esc(valor)}</strong>${nota ? `<small>${Panel.esc(nota)}</small>` : ''}</div>`;

  async function cargar() {
    const d = await Panel.json('/api/docente/resumen');
    $('res-kpis').innerHTML = [
      kpi('Estudiantes activos', d.estudiantes.activos, d.estudiantes.secciones.map(s => `${s.seccion}: ${s.estudiantes}`).join(' · ')),
      kpi('Exámenes enviados', d.intentos.enviados),
      kpi('En curso ahora', d.intentos.en_curso),
      kpi('Promedio general', d.intentos.promedio === null ? '—' : d.intentos.promedio),
      kpi('Anulados', d.intentos.anulados),
      kpi('Exámenes deshabilitados', `${d.examenes.deshabilitados}/${d.examenes.total}`),
    ].join('');

    $('res-alertas').innerHTML = d.alertas.length
      ? d.alertas.map(a => `<li><span class="doc-pill ${a.tipo === 'vencido' || a.tipo === 'sospechosos' ? 'warn' : 'wait'}">${Panel.esc(a.tipo)}</span>
          ${Panel.esc(a.texto)} <button type="button" class="doc-enlace" data-ir="${Panel.esc(a.ir)}">Ver</button></li>`).join('')
      : '<li class="doc-pending">Sin alertas. Todo en orden.</li>';

    $('res-curso').innerHTML = d.en_curso.length
      ? d.en_curso.map(c => `<tr><th scope="row">${Panel.esc(c.estudiante)}</th><td>${Panel.esc(c.seccion)}</td><td>${Panel.esc(c.codigo)}</td>
          <td>${c.vencido ? '<span class="doc-pill warn">Vencido</span>' : `${c.minutos_restantes} min`}</td>
          <td>${c.incidencias > 0 ? `<span class="doc-pill ${c.incidencias >= 3 ? 'warn' : 'wait'}">${c.incidencias}</span>` : '0'}</td></tr>`).join('')
      : '<tr><td colspan="5" class="doc-pending">Nadie está presentando un examen.</td></tr>';

    $('res-reciente').innerHTML = d.reciente.length
      ? d.reciente.map(r => `<li><small class="doc-muted">${Panel.formatoFecha(r.fecha)}</small> ${Panel.esc(r.accion.replace(/_/g, ' '))}
          ${r.detalle ? `· ${Panel.esc(r.detalle)}` : ''}</li>`).join('')
      : '<li class="doc-pending">Sin actividad registrada.</li>';
  }

  Panel.registrar('resumen', 'Resumen', {
    init(el) {
      el.innerHTML = `
        <div class="rep-kpis" id="res-kpis"></div>
        <div class="doc-rejilla">
          <section aria-labelledby="h-alertas"><h2 id="h-alertas">Requiere atención</h2><ul class="doc-lista" id="res-alertas"></ul></section>
          <section aria-labelledby="h-reciente"><h2 id="h-reciente">Actividad reciente</h2><ul class="doc-lista" id="res-reciente"></ul></section>
        </div>
        <h2>Presentando examen ahora</h2>
        <div class="doc-table-wrap">
          <table class="doc-table">
            <caption class="doc-solo-lectores">Exámenes en curso</caption>
            <thead><tr><th scope="col">Estudiante</th><th scope="col">Sección</th><th scope="col">Examen</th>
              <th scope="col">Tiempo restante</th><th scope="col">Salidas</th></tr></thead>
            <tbody id="res-curso"></tbody>
          </table>
        </div>
        <p class="doc-muted">Se actualiza solo cada 30 segundos.</p>`;
      el.addEventListener('click', e => { if (e.target.dataset.ir) Panel.irA(e.target.dataset.ir); });
    },
    async mostrar() {
      await cargar();
      clearInterval(refresco);
      refresco = setInterval(() => {
        if (Panel.moduloActivo !== 'resumen' || !Panel.token) return clearInterval(refresco);
        cargar().catch(() => {});
      }, 30000);
    },
  });
})();
