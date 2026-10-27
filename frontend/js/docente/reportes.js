// Pestaña Reportes: boleta del estudiante, resultado por examen, preguntas críticas y notas por sección
(function () {
  const TIPOS = {
    boleta: 'Boleta de un estudiante',
    examen: 'Resultado de un examen',
    criticas: 'Preguntas críticas de un examen',
    seccion: 'Notas por sección y periodo',
  };
  const NOTAS_ETIQUETA = {
    trabajo_cotidiano: 'TC', tareas: 'Tareas', prueba01: 'P01', prueba02: 'P02', proyecto: 'Proyecto', asistencia: 'Asist.',
  };
  let catalogos = null;
  let actual = null; // { titulo, html, excel }

  const num = (n, dec = 1) => (n === null || n === undefined ? '—' : Number(n).toFixed(dec).replace(/\.0$/, ''));
  const clase = (nota, minima) => (nota >= minima ? 'rep-aprobado' : 'rep-reprobado');
  const hoy = () => new Date().toLocaleDateString('es-CR', { dateStyle: 'long' });

  async function cargarCatalogos() {
    const [est, exa] = await Promise.all([
      Panel.json('/api/docente/estudiantes'), Panel.json('/api/docente/examenes'),
    ]);
    catalogos = { estudiantes: est.estudiantes, examenes: exa.examenes };
    catalogos.secciones = [...new Set(est.estudiantes.map(e => e.seccion))].sort();
  }

  function opciones(items, valor, etiqueta) {
    return items.map(x => `<option value="${Panel.esc(valor(x))}">${Panel.esc(etiqueta(x))}</option>`).join('');
  }

  function dibujarParametros() {
    const tipo = $('r-tipo').value;
    const seccion = `<label>Sección <select id="r-seccion"><option value="">Todas</option>${opciones(catalogos.secciones, s => s, s => s)}</select></label>`;
    const examen = `<label>Examen <select id="r-examen">${opciones(catalogos.examenes, e => e.codigo, e => `${e.codigo} · ${e.nombre}`)}</select></label>`;
    $('r-parametros').innerHTML = {
      boleta: `<label>Estudiante <select id="r-estudiante">${opciones(
        catalogos.estudiantes, e => e.id, e => `${Panel.nombre(e)} (${e.seccion})`)}</select></label>`,
      examen: examen + seccion,
      criticas: examen + seccion,
      seccion: `<label>Sección <select id="r-seccion">${opciones(catalogos.secciones, s => s, s => s)}</select></label>
        <label>Periodo <select id="r-periodo"><option value="1">1</option><option value="2">2</option></select></label>`,
    }[tipo];
    limpiarSalida();
  }

  function limpiarSalida() {
    actual = null;
    $('r-salida').innerHTML = '<p class="doc-muted">Elige los parámetros y pulsa «Generar».</p>';
    $('r-imprimir').disabled = true;
    $('r-excel').disabled = true;
  }

  // ---------- Constructores de reporte ----------
  function encabezado(titulo, institucion, meta) {
    return `<h1>${Panel.esc(titulo)}</h1>
      <p class="rep-meta">${institucion ? Panel.esc(institucion) + ' · ' : ''}${meta} · Generado el ${hoy()}</p>`;
  }

  function tablaTemas(temas) {
    return `<table class="rep-tabla"><thead><tr><th>Tema</th><th class="num">Aciertos</th><th class="num">Total</th><th class="num">%</th></tr></thead><tbody>
      ${temas.map(t => `<tr><td>${Panel.esc(t.tema)}</td><td class="num">${t.aciertos}</td><td class="num">${t.total}</td><td class="num">${num(t.porcentaje)}%</td></tr>`).join('')}
      </tbody></table>`;
  }

  function histogramaSvg(histograma) {
    const max = Math.max(1, ...histograma.map(h => h.cantidad));
    const ancho = 520, alto = 150, margen = 22, w = (ancho - margen) / histograma.length;
    const barras = histograma.map((h, i) => {
      const altura = (alto - 40) * h.cantidad / max;
      const x = margen + i * w + 4;
      return `<rect x="${x}" y="${alto - 22 - altura}" width="${w - 8}" height="${altura}" fill="#2b9e6e" rx="2"/>
        <text x="${x + (w - 8) / 2}" y="${alto - 8}" font-size="10" text-anchor="middle">${h.desde}</text>
        ${h.cantidad ? `<text x="${x + (w - 8) / 2}" y="${alto - 26 - altura}" font-size="10" text-anchor="middle">${h.cantidad}</text>` : ''}`;
    }).join('');
    return `<svg viewBox="0 0 ${ancho} ${alto}" width="100%" role="img" aria-label="Distribución de notas por rango de 10 puntos">
      <line x1="${margen}" y1="${alto - 22}" x2="${ancho}" y2="${alto - 22}" stroke="#888"/>${barras}</svg>`;
  }

  function htmlBoleta(d) {
    const minima = d.nota_minima;
    const examenes = d.examenes.length ? d.examenes.map(x => `
      <h2>${Panel.esc(x.codigo)} · ${Panel.esc(x.nombre)}</h2>
      <p class="rep-meta">Presentado el ${Panel.formatoFecha(x.fecha)} · ${x.puntuacion}/${x.total} aciertos ·
        Nota <span class="${clase(x.nota, minima)}">${num(x.nota)}</span> (${x.aprobado ? 'Aprobado' : 'Reprobado'})</p>
      ${tablaTemas(x.temas)}`).join('') : '<p class="rep-vacio">Aún no ha presentado exámenes.</p>';
    const comps = Object.keys(NOTAS_ETIQUETA);
    const notas = d.notas.length ? `<table class="rep-tabla"><thead><tr><th>Materia</th><th class="num">Periodo</th>
      ${comps.map(c => `<th class="num">${NOTAS_ETIQUETA[c]}</th>`).join('')}<th class="num">Nota final</th></tr></thead><tbody>
      ${d.notas.map(n => `<tr><td>${Panel.esc(n.materia)}</td><td class="num">${n.periodo}</td>
        ${comps.map(c => `<td class="num">${num(n[c])}</td>`).join('')}
        <td class="num ${clase(n.nota_final, minima)}">${num(n.nota_final)}${n.completa ? '' : '*'}</td></tr>`).join('')}
      </tbody></table><p class="rep-meta">* Nota parcial: faltan componentes por calificar.</p>`
      : '<p class="rep-vacio">Sin notas registradas por materia.</p>';
    return encabezado('Boleta de calificaciones', d.institucion,
        `${Panel.esc(d.estudiante.nombre)} · Sección ${Panel.esc(d.estudiante.seccion)} · Cédula ${Panel.esc(d.estudiante.cedula)}`) +
      `<h2>Exámenes presentados</h2>${examenes}<h2>Notas por materia</h2>${notas}
      <div class="rep-firma"><div>Docente</div><div>Sello institucional</div></div>`;
  }

  function htmlExamen(d) {
    const r = d.resumen, minima = d.nota_minima;
    const kpis = [['Enviados', r.enviados], ['Sin enviar', r.sin_enviar], ['Promedio', num(r.promedio)], ['Mediana', num(r.mediana)],
      ['Máxima', num(r.maxima)], ['Mínima', num(r.minima)], ['Aprobados', r.aprobados], ['Reprobados', r.reprobados]]
      .map(([k, v]) => `<div class="rep-kpi">${k}<strong>${v}</strong></div>`).join('');
    return encabezado(`Resultado del examen ${d.codigo}`, d.institucion,
        `${Panel.esc(d.nombre)} · Sección: ${Panel.esc(d.seccion)} · Nota mínima ${minima}`) +
      `<div class="rep-kpis">${kpis}</div><h2>Distribución de notas</h2>${histogramaSvg(d.histograma)}
      <h2>Rendimiento por tema</h2>${d.temas.length ? tablaTemas(d.temas) : '<p class="rep-vacio">Sin datos.</p>'}
      <h2>Clasificación</h2>${d.ranking.length ? `<table class="rep-tabla"><thead><tr><th class="num">#</th><th>Estudiante</th><th>Sección</th>
        <th class="num">Aciertos</th><th class="num">Nota</th></tr></thead><tbody>
        ${d.ranking.map((x, i) => `<tr><td class="num">${i + 1}</td><td>${Panel.esc(x.nombre)}</td><td>${Panel.esc(x.seccion)}</td>
          <td class="num">${x.puntuacion}/${x.total}</td><td class="num ${clase(x.nota, minima)}">${num(x.nota)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="rep-vacio">Nadie ha enviado este examen.</p>'}`;
  }

  function htmlCriticas(d) {
    const corto = (t) => (t.length > 150 ? t.slice(0, 147) + '…' : t);
    return encabezado(`Preguntas críticas · ${d.codigo}`, d.institucion,
        `${Panel.esc(d.nombre)} · Sección: ${Panel.esc(d.seccion)} · ${d.intentos} intentos analizados`) +
      (d.intentos ? `<p class="rep-meta">Ordenadas por porcentaje de error. El distractor es la opción incorrecta más elegida.</p>
      <table class="rep-tabla"><thead><tr><th class="num">N.º</th><th>Tema</th><th>Pregunta</th><th class="num">% error</th>
        <th class="num">Errores</th><th>Distractor más elegido</th></tr></thead><tbody>
        ${d.preguntas.map(q => `<tr><td class="num">${q.numero}</td><td>${Panel.esc(q.tema)}</td><td>${Panel.esc(corto(q.pregunta))}</td>
          <td class="num ${q.porcentaje_error >= 50 ? 'rep-reprobado' : ''}">${num(q.porcentaje_error)}%</td><td class="num">${q.errores}/${q.respondidas}</td>
          <td>${q.distractor ? `${Panel.esc(corto(q.distractor.texto))} (${q.distractor.veces})` : '—'}</td></tr>`).join('')}
        </tbody></table>` : '<p class="rep-vacio">Nadie ha enviado este examen.</p>');
  }

  function htmlSeccion(d) {
    const minima = d.nota_minima;
    return encabezado(`Notas · sección ${d.seccion} · periodo ${d.periodo}`, '', `Nota mínima ${minima}`) +
      `<table class="rep-tabla"><thead><tr><th>Estudiante</th>${d.materias.map(m => `<th class="num">${Panel.esc(m.nombre)}</th>`).join('')}
        <th class="num">Promedio</th></tr></thead><tbody>
        ${d.estudiantes.map(e => `<tr><td>${Panel.esc(e.nombre)}</td>
          ${d.materias.map(m => {
            const n = e.notas[String(m.id)];
            return n && n.completa ? `<td class="num ${clase(n.nota_final, minima)}">${num(n.nota_final)}</td>` : '<td class="num">—</td>';
          }).join('')}
          <td class="num ${e.promedio_general === null ? '' : clase(e.promedio_general, minima)}">${num(e.promedio_general)}</td></tr>`).join('')}
        </tbody><tfoot><tr><th>Promedio de la materia</th>
          ${d.promedios.map(p => `<th class="num">${num(p.promedio)}<br><small>${p.aprobados}/${p.completas} aprob.</small></th>`).join('')}<th></th></tr></tfoot></table>
      <p class="rep-meta">Solo se muestran notas completas (los seis componentes calificados).</p>`;
  }

  async function generar() {
    const tipo = $('r-tipo').value;
    const q = (id) => ($(id) ? $(id).value : '');
    const param = (nombre, valor) => (valor ? `?${nombre}=${encodeURIComponent(valor)}` : '');
    if (tipo === 'boleta') {
      const id = q('r-estudiante');
      if (!id) return Panel.toast('No hay estudiantes', 'error');
      const d = await Panel.json(`/api/docente/reportes/boleta/${id}`);
      actual = { titulo: `Boleta ${d.estudiante.nombre}`, html: htmlBoleta(d), excel: [`/api/docente/reportes/boleta/${id}/excel`, `boleta_${d.estudiante.username}.xlsx`] };
    } else if (tipo === 'examen') {
      const c = q('r-examen'), s = q('r-seccion');
      const d = await Panel.json(`/api/docente/reportes/examen/${c}${param('seccion', s)}`);
      actual = { titulo: `Resultado ${c}`, html: htmlExamen(d), excel: [`/api/docente/reportes/examen/${c}/excel${param('seccion', s)}`, `reporte_${c}.xlsx`] };
    } else if (tipo === 'criticas') {
      const c = q('r-examen'), s = q('r-seccion');
      const d = await Panel.json(`/api/docente/reportes/preguntas-criticas/${c}${param('seccion', s)}`);
      actual = { titulo: `Preguntas críticas ${c}`, html: htmlCriticas(d), excel: [`/api/docente/reportes/examen/${c}/excel${param('seccion', s)}`, `reporte_${c}.xlsx`] };
    } else {
      const s = q('r-seccion'), p = q('r-periodo');
      const d = await Panel.json(`/api/docente/reportes/seccion?seccion=${encodeURIComponent(s)}&periodo=${p}`);
      actual = { titulo: `Notas ${s} periodo ${p}`, html: htmlSeccion(d), excel: [`/api/docente/reportes/seccion/excel?seccion=${encodeURIComponent(s)}&periodo=${p}`, `notas_${s}_P${p}.xlsx`] };
    }
    $('r-salida').innerHTML = `<div class="rep">${actual.html}</div>`;
    $('r-imprimir').disabled = false;
    $('r-excel').disabled = false;
  }

  Panel.registrar('reportes', 'Reportes', {
    init(el) {
      el.innerHTML = `
        <div class="doc-toolbar">
          <label>Reporte <select id="r-tipo">${Object.entries(TIPOS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
          <span id="r-parametros" class="doc-toolbar-grupo"></span>
          <button class="btn btn-primary" id="r-generar">Generar</button>
          <button class="btn btn-secondary" id="r-imprimir" disabled>Imprimir / PDF</button>
          <button class="btn btn-secondary" id="r-excel" disabled>Excel</button>
        </div>
        <div id="r-salida" class="rep-pantalla" aria-live="polite"></div>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('r-tipo').addEventListener('change', () => catalogos && dibujarParametros());
      $('r-generar').addEventListener('click', run(generar));
      $('r-imprimir').addEventListener('click', () => actual && Panel.imprimirHtml(actual.titulo, actual.html));
      $('r-excel').addEventListener('click', () => actual && Panel.descargar(actual.excel[0], actual.excel[1]));
    },
    async mostrar() {
      await cargarCatalogos();
      dibujarParametros();
    },
  });
})();
