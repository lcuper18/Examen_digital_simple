// Pestaña Reportes: boleta del estudiante, resultado por examen, preguntas críticas y notas por sección
(function () {
  const TIPOS = {
    boleta: 'Boleta de un estudiante',
    examen: 'Resultado de un examen',
    criticas: 'Preguntas críticas de un examen',
    seccion: 'Notas por sección y periodo',
    acta: 'Acta de calificaciones',
    encargados: 'Informe para encargados',
    registro: 'Registro de notas (en puntos)',
  };
  const NOTAS_ETIQUETA = {
    trabajo_cotidiano: 'TC', tareas: 'Tareas', prueba01: 'P01', prueba02: 'P02', proyecto: 'Proyecto', asistencia: 'Asist.',
  };
  let catalogos = null;
  let actual = null; // { titulo, html, excel, csv }

  const num = (n, dec = 1) => (n === null || n === undefined ? '—' : Number(n).toFixed(dec).replace(/\.0$/, ''));
  const clase = (nota, minima) => (nota >= minima ? 'rep-aprobado' : 'rep-reprobado');
  const hoy = () => new Date().toLocaleDateString('es-CR', { dateStyle: 'long' });

  async function cargarCatalogos() {
    const [est, exa, mat] = await Promise.all([
      Panel.json('/api/docente/estudiantes'), Panel.json('/api/docente/examenes'), Panel.json('/api/docente/materias'),
    ]);
    catalogos = { estudiantes: est.estudiantes, examenes: exa.examenes, materias: mat.materias };
    catalogos.secciones = [...new Set(est.estudiantes.map(e => e.seccion))].sort();
  }

  function opciones(items, valor, etiqueta) {
    return items.map(x => `<option value="${Panel.esc(valor(x))}">${Panel.esc(etiqueta(x))}</option>`).join('');
  }

  function dibujarParametros() {
    const tipo = $('r-tipo').value;
    const seccion = `<label>Sección <select id="r-seccion"><option value="">Todas</option>${opciones(catalogos.secciones, s => s, s => s)}</select></label>`;
    const examen = `<label>Examen <select id="r-examen">${opciones(catalogos.examenes, e => e.codigo, e => `${e.codigo} · ${e.nombre}`)}</select></label>`;
    const ctx = Panel.contexto.materia();
    const materia = ctx ? `<p class="doc-muted doc-ctx-aviso">Materia elegida arriba: <strong>${Panel.esc(ctx.seccion)} · ${ctx.periodo}.º período · ${Panel.esc(ctx.nombre)}</strong></p>` : '';
    const grupo = ctx ? `<p class="doc-muted doc-ctx-aviso">Grupo elegido arriba: <strong>${Panel.esc(ctx.seccion)} · ${ctx.periodo}.º período</strong></p>` : '';
    $('r-parametros').innerHTML = {
      acta: materia,
      registro: materia,
      encargados: grupo + `<label>Estudiante <select id="r-estudiante"></select></label>`,
      boleta: `<label>Estudiante <select id="r-estudiante">${opciones(
        catalogos.estudiantes, e => e.id, e => `${Panel.nombre(e)} (${e.seccion})`)}</select></label>`,
      examen: examen + seccion,
      criticas: examen + seccion,
      seccion: grupo,
    }[tipo];
    if (tipo === 'encargados') {
      llenarEstudiantes();
    }
    limpiarSalida();
  }

  function llenarEstudiantes() {
    const seccion = Panel.contexto.materia() ? Panel.contexto.materia().seccion : '';
    $('r-estudiante').innerHTML = '<option value="">Toda la sección</option>' + opciones(
      catalogos.estudiantes.filter(e => e.seccion === seccion), e => e.id, e => Panel.nombre(e));
  }

  function limpiarSalida() {
    actual = null;
    $('r-salida').innerHTML = '<p class="doc-muted">Elige los parámetros y pulsa «Generar».</p>';
    $('r-imprimir').disabled = true;
    $('r-excel').disabled = true;
    $('r-csv').disabled = true;
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
        <th class="num">Promedio</th><th>Estado</th></tr></thead><tbody>
        ${d.estudiantes.map(e => `<tr><td>${Panel.esc(e.nombre)}</td>
          ${d.materias.map(m => {
            const n = e.notas[String(m.id)];
            return n && n.completa ? `<td class="num ${clase(n.nota_final, minima)}">${num(n.nota_final)}</td>` : '<td class="num">—</td>';
          }).join('')}
          <td class="num ${e.promedio_general === null ? '' : clase(e.promedio_general, minima)}">${num(e.promedio_general)}</td>
          <td class="${e.estado === 'Aprobado' ? 'rep-aprobado' : e.estado === 'Incompleto' ? '' : 'rep-reprobado'}">${Panel.esc(e.estado)}</td></tr>`).join('')}
        </tbody><tfoot><tr><th>Promedio de la materia</th>
          ${d.promedios.map(p => `<th class="num">${num(p.promedio)}<br><small>${p.aprobados}/${p.completas} aprob.</small></th>`).join('')}<th></th><th></th></tr></tfoot></table>
      <p class="rep-meta">Solo se muestran notas completas (los seis componentes calificados).</p>`;
  }

  const entero = (n) => (n === null || n === undefined ? '—' : String(n));

  function htmlActa(d) {
    const e = d.encabezado, minima = d.nota_minima;
    const parcial = d.estudiantes.some(x => !x.completa);
    return `<p class="rep-acta">Dirección Regional de Educación: <strong>DIRECCIÓN REGIONAL ${Panel.esc(e.direccion_regional.toUpperCase())}</strong><br>
        Circuito escolar: <strong>CIRCUITO ${Panel.esc(e.circuito)}</strong><br>
        Centro educativo: <strong>${Panel.esc(e.institucion.toUpperCase())}</strong><br>
        Curso lectivo: <strong>${Panel.esc(e.curso_lectivo)}</strong></p>
      <h1 class="rep-centro">${Panel.esc(e.institucion.toUpperCase())}</h1>
      <p class="rep-centro"><strong>Reportes</strong></p>
      <p class="rep-acta">Docente: <strong>${Panel.esc(e.docente.toUpperCase())}</strong><br>
        Asignatura: <strong>${Panel.esc(e.asignatura.toUpperCase())}.</strong><br>
        Nivel: <strong>${Panel.esc(e.nivel)}</strong><br>
        Sección: <strong>${Panel.esc(e.seccion)}</strong><br>
        Período: <strong>${e.periodo}° período</strong></p>
      <table class="rep-tabla"><thead><tr><th>Id</th><th>Nombre</th><th class="num">Nota</th></tr></thead><tbody>
        ${d.estudiantes.map(x => `<tr><td>${Panel.esc(x.cedula)}</td><td>${Panel.esc(x.nombre)}</td>
          <td class="num ${clase(x.nota, minima)}">${x.nota}${x.completa ? '' : '*'}</td></tr>`).join('')}</tbody></table>
      ${parcial ? '<p class="rep-meta">* Nota parcial: faltan componentes por calificar (cuentan como 0).</p>' : ''}
      <div class="rep-firma rep-firma-centro"><div>Firma</div></div>`;
  }

  function htmlMateriaEncargado(m, minima) {
    const pendientes = m.actividades.filter(a => a.estado === 'sin_entrega');
    const asis = m.asistencia;
    return `<h2>${Panel.esc(m.materia)}</h2>
      <table class="rep-tabla"><thead><tr><th>Componente</th><th class="num">Valor</th><th class="num">Puntos obtenidos</th></tr></thead><tbody>
        ${m.componentes.map(c => `<tr><td>${Panel.esc(c.etiqueta)}</td><td class="num">${num(c.peso, 2)}</td><td class="num">${num(c.puntos, 2)}</td></tr>`).join('')}
      </tbody><tfoot><tr><th colspan="2">Nota ${m.completa ? '' : '(parcial)'}</th>
        <th class="num ${clase(m.nota_final, minima)}">${num(m.nota_final)} · ${m.aprobado ? 'Aprobado' : 'Por debajo de ' + minima}</th></tr></tfoot></table>
      ${asis ? `<p class="rep-meta"><strong>Asistencia:</strong> ${asis.lecciones} lecciones impartidas · ${asis.ausencias} ausencias ·
        ${asis.tardias} tardías · ${asis.justificadas} justificadas · ${num(asis.porcentaje, 1)} % de ausencias injustificadas · ${asis.puntos} de ${asis.maximo} puntos.</p>`
        : '<p class="rep-meta"><strong>Asistencia:</strong> sin lista registrada en el período.</p>'}
      ${m.actividades.length ? `<table class="rep-tabla"><thead><tr><th>Actividad</th><th>Componente</th><th>Estado</th><th class="num">Puntos</th><th>Observación</th></tr></thead><tbody>
        ${m.actividades.map(a => `<tr><td>${Panel.esc(a.nombre)}</td><td>${Panel.esc(a.componente)}</td><td>${Panel.esc(a.estado_texto)}</td>
          <td class="num">${a.estado === 'sin_entrega' ? '0' : num(a.puntos, 2)} / ${num(a.puntos_max, 2)}</td><td>${Panel.esc(a.observacion)}</td></tr>`).join('')}</tbody></table>` : ''}
      ${pendientes.length ? `<p class="rep-reprobado">Pendiente: ${pendientes.map(a => Panel.esc(a.nombre)).join('; ')}.</p>` : ''}`;
  }

  function htmlEncargados(d) {
    const e = d.encabezado;
    return d.informes.map(i => `<div class="rep-pagina">
      <h1>Informe de calificaciones y asistencia</h1>
      <p class="rep-meta">${Panel.esc(e.institucion)} · Curso lectivo ${Panel.esc(e.curso_lectivo)} · ${Panel.esc(e.nivel)} · Sección ${Panel.esc(d.seccion)} · Período ${d.periodo}</p>
      <p><strong>${Panel.esc(i.estudiante.nombre)}</strong> · Cédula ${Panel.esc(i.estudiante.cedula)}</p>
      ${i.materias.map(m => htmlMateriaEncargado(m, d.nota_minima)).join('')}
      <div class="rep-firma"><div>${Panel.esc(e.docente)}<br><small>Docente</small></div><div>Recibido por el encargado</div></div>
    </div>`).join('') + `<p class="rep-meta">Informe generado el ${hoy()}.</p>`;
  }

  function htmlRegistro(d, materia) {
    const filas = d.notas;
    return encabezado(`Registro de notas · ${materia.nombre}`, '', `Sección ${Panel.esc(materia.seccion)} · Periodo ${materia.periodo} · puntos por componente`) +
      `<table class="rep-tabla"><thead><tr><th>Estudiante</th>${Object.keys(d.ponderaciones).map(c =>
        `<th class="num">${NOTAS_ETIQUETA[c]} <small>/${num(d.ponderaciones[c], 2)}</small></th>`).join('')}<th class="num">Nota</th></tr></thead><tbody>
      ${filas.map(f => `<tr><td>${Panel.esc(Panel.nombre(f))}</td>${Object.keys(d.ponderaciones).map(c =>
        `<td class="num">${f[c] === null ? '—' : num(f[c] * d.ponderaciones[c] / 100, 2)}</td>`).join('')}
        <td class="num ${clase(f.nota_final, d.nota_minima)}">${num(f.nota_final)}</td></tr>`).join('')}</tbody></table>`;
  }

  async function generar() {
    const tipo = $('r-tipo').value;
    const q = (id) => ($(id) ? $(id).value : '');
    const param = (nombre, valor) => (valor ? `?${nombre}=${encodeURIComponent(valor)}` : '');
    if (tipo === 'acta') {
      const id = Panel.contexto.id();
      const d = await Panel.json(`/api/docente/informes/acta?materia_id=${id}`);
      actual = { titulo: `Acta ${d.encabezado.asignatura} ${d.encabezado.seccion}`, html: htmlActa(d),
        excel: [`/api/docente/informes/acta/excel?materia_id=${id}`, `acta_${id}.xlsx`] };
    } else if (tipo === 'registro') {
      const id = Panel.contexto.id();
      const d = await Panel.json(`/api/docente/notas?materia_id=${id}`);
      actual = { titulo: `Registro ${d.materia.nombre}`, html: htmlRegistro(d, d.materia),
        excel: [`/api/docente/informes/registro/excel?materia_id=${id}`, `registro_${id}.xlsx`],
        csv: [`/api/docente/informes/registro?materia_id=${id}`, `registro_${id}.csv`] };
    } else if (tipo === 'encargados') {
      const s = Panel.contexto.materia().seccion, p = Panel.contexto.materia().periodo, e = q('r-estudiante');
      const d = await Panel.json(`/api/docente/informes/encargados?seccion=${encodeURIComponent(s)}&periodo=${p}${e ? `&estudiante_id=${e}` : ''}`);
      actual = { titulo: `Informe encargados ${s} P${p}`, html: htmlEncargados(d), excel: null };
    } else if (tipo === 'boleta') {
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
      const s = Panel.contexto.materia().seccion, p = Panel.contexto.materia().periodo;
      const d = await Panel.json(`/api/docente/reportes/seccion?seccion=${encodeURIComponent(s)}&periodo=${p}`);
      actual = { titulo: `Notas ${s} periodo ${p}`, html: htmlSeccion(d), excel: [`/api/docente/reportes/seccion/excel?seccion=${encodeURIComponent(s)}&periodo=${p}`, `notas_${s}_P${p}.xlsx`] };
    }
    $('r-salida').innerHTML = `<div class="rep">${actual.html}</div>`;
    $('r-imprimir').disabled = false;
    $('r-excel').disabled = !actual.excel;
    $('r-csv').disabled = !actual.csv;
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
          <button class="btn btn-secondary" id="r-csv" disabled>CSV</button>
        </div>
        <div id="r-salida" class="rep-pantalla" aria-live="polite"></div>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('r-tipo').addEventListener('change', () => catalogos && dibujarParametros());
      $('r-generar').addEventListener('click', run(generar));
      $('r-imprimir').addEventListener('click', () => actual && Panel.imprimirHtml(actual.titulo, actual.html));
      $('r-excel').addEventListener('click', () => actual && actual.excel && Panel.descargar(actual.excel[0], actual.excel[1]));
      $('r-csv').addEventListener('click', () => actual && actual.csv && Panel.descargar(actual.csv[0], actual.csv[1]));
    },
    usaContexto: true,
    async mostrar() {
      await cargarCatalogos();
      dibujarParametros();
    },
  });
})();
