// Pestaña Resumen ("Inicio"): qué hacer hoy, primeros pasos, estudiantes que necesitan atención y estado de los exámenes
(function () {
  let refresco = null;

  const kpi = (etiqueta, valor, nota = '', clase = '') =>
    `<div class="rep-kpi ${clase}">${Panel.esc(etiqueta)}<strong>${Panel.esc(valor)}</strong>${nota ? `<small>${Panel.esc(nota)}</small>` : ''}</div>`;

  const ICONO = (id) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${Panel.ICONOS[id]}</svg>`;
  const ATAJOS = [
    ['asistencia', 'Pasar lista de hoy', 'Marca con un toque a quien tenga novedad'],
    ['actividades', 'Calificar una actividad', 'Tareas, proyectos y trabajo cotidiano'],
    ['notas', 'Ver y registrar notas', 'Notas por componente y publicación'],
    ['reportes', 'Sacar un informe', 'Acta, informe para encargados y más'],
  ];

  function saludo() {
    const h = new Date().getHours();
    return h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches';
  }

  function tarjetaEstudiante(e) {
    return `<li class="doc-tarjeta-alerta">
      <div><strong>${Panel.esc(e.nombre)}</strong> <small class="doc-muted">${Panel.esc(e.seccion)}${e.adecuacion ? ' · con adecuación' : ''}</small>
        <div class="doc-pills">${[...new Set(e.alertas.map(a => a.tipo))].map(t => {
          const alta = e.alertas.some(a => a.tipo === t && a.severidad === 'alta');
          return `<span class="doc-pill ${alta ? 'warn' : 'wait'}">${Panel.esc(Panel.ETIQUETA_ALERTA[t] || t)}</span>`;
        }).join('')}</div>
        <small class="doc-muted">${Panel.esc(e.alertas[0].materia)}: ${Panel.esc(e.alertas[0].detalle)}${e.alertas.length > 1 ? ` (y ${e.alertas.length - 1} más)` : ''}</small></div>
      <button type="button" class="btn btn-secondary" data-ficha="${e.estudiante_id}">Abrir ficha</button></li>`;
  }

  async function primerosPasos() {
    let descartado = false;
    try { descartado = localStorage.getItem('primerosPasosOculto') === '1'; } catch (e) { /* sin almacenamiento */ }
    const { pasos } = await Panel.json('/api/docente/primeros-pasos');
    const hechos = pasos.filter(p => p.hecho).length;
    const caja = $('res-pasos');
    if (descartado || hechos === pasos.length) { caja.hidden = true; return; }
    caja.hidden = false;
    caja.innerHTML = `<div class="doc-pasos-cab"><h2>Primeros pasos <small class="doc-muted">${hechos} de ${pasos.length}</small></h2>
      <button type="button" class="doc-enlace" data-ocultar-pasos>Ocultar</button></div>
      <ol class="doc-pasos">${pasos.map(p => `<li class="${p.hecho ? 'hecho' : ''}">
        <span class="doc-paso-marca" aria-hidden="true">${p.hecho ? '✓' : ''}</span>
        <span>${Panel.esc(p.texto)}${p.hecho ? ' <span class="doc-solo-lectores">(hecho)</span>' : ''}</span>
        ${p.hecho ? '' : `<button type="button" class="doc-enlace" data-ir="${Panel.esc(p.ir)}">Ir</button>`}</li>`).join('')}</ol>`;
  }

  async function cargar() {
    const [d, seg] = await Promise.all([Panel.json('/api/docente/resumen'), Panel.json('/api/docente/alertas')]);
    const ctx = Panel.contexto.materia();
    $('res-saludo').textContent = `${saludo()}, profe`;
    $('res-contexto').textContent = ctx ? `Trabajando en ${ctx.seccion} · ${ctx.nombre}` : '';

    const cuenta = (tipo) => seg.estudiantes.filter(e => e.alertas.some(a => a.tipo === tipo)).length;
    $('res-kpis').innerHTML = [
      kpi('En riesgo de reprobar', cuenta('riesgo'), `período ${seg.periodo}`, cuenta('riesgo') ? 'rep-kpi-alerta' : ''),
      kpi('Con muchas ausencias', cuenta('asistencia'), '', cuenta('asistencia') ? 'rep-kpi-alerta' : ''),
      kpi('Con tareas sin entregar', cuenta('pendientes')),
      kpi('Estudiantes activos', d.estudiantes.activos, d.estudiantes.secciones.map(s => `${s.seccion}: ${s.estudiantes}`).join(' · ')),
      kpi('Exámenes presentados', d.intentos.enviados, d.intentos.promedio === null ? '' : `promedio ${d.intentos.promedio}`),
      kpi('Presentando ahora', d.intentos.en_curso),
    ].join('');

    $('res-seguimiento-titulo').textContent = `Estudiantes que necesitan atención (período ${seg.periodo})`;
    $('res-seguimiento').innerHTML = seg.estudiantes.length
      ? seg.estudiantes.map(tarjetaEstudiante).join('')
      : '<li class="doc-pending">Por ahora nadie está en riesgo según las notas, la asistencia y las entregas registradas.</li>';

    $('res-alertas').innerHTML = d.alertas.length
      ? d.alertas.map(a => `<li><span class="doc-pill ${a.tipo === 'vencido' || a.tipo === 'sospechosos' || a.tipo === 'respaldo' ? 'warn' : 'wait'}">${Panel.esc(Panel.ETIQUETA_ALERTA[a.tipo] || a.tipo)}</span>
          ${Panel.esc(a.texto)} <button type="button" class="doc-enlace" data-ir="${Panel.esc(a.ir)}">Ver</button></li>`).join('')
      : '<li class="doc-pending">Sin avisos de exámenes ni de cuentas.</li>';

    $('res-curso').innerHTML = d.en_curso.length
      ? d.en_curso.map(c => `<tr><th scope="row">${Panel.esc(c.estudiante)}</th><td>${Panel.esc(c.seccion)}</td><td>${Panel.esc(c.codigo)}</td>
          <td>${c.vencido ? '<span class="doc-pill warn">Tiempo agotado</span>' : `${c.minutos_restantes} min`}</td>
          <td>${c.incidencias > 0 ? `<span class="doc-pill ${c.incidencias >= 3 ? 'warn' : 'wait'}">${c.incidencias}</span>` : '0'}</td></tr>`).join('')
      : '<tr><td colspan="5" class="doc-pending">Nadie está presentando un examen en este momento.</td></tr>';

    $('res-reciente').innerHTML = d.reciente.length
      ? d.reciente.map(r => `<li><small class="doc-muted">${Panel.formatoFecha(r.fecha)}</small><br>${Panel.esc(Panel.frase(r.accion))}${r.detalle ? ` <span class="doc-muted">· ${Panel.esc(r.detalle)}</span>` : ''}</li>`).join('')
      : '<li class="doc-pending">Todavía no hay actividad registrada.</li>';
    await primerosPasos();
  }

  Panel.registrar('resumen', 'Inicio', {
    init(el) {
      el.innerHTML = `
        <header class="doc-bienvenida"><h2 id="res-saludo"></h2><p class="doc-muted" id="res-contexto"></p></header>
        <section class="doc-atajos" aria-label="Accesos rápidos">${ATAJOS.map(([id, titulo, texto]) =>
          `<button type="button" class="doc-atajo" data-ir="${id}">${ICONO(id)}<span><strong>${titulo}</strong><small>${texto}</small></span></button>`).join('')}</section>
        <section id="res-pasos" class="doc-pasos-caja" hidden></section>
        <div class="rep-kpis" id="res-kpis"></div>
        <section aria-labelledby="res-seguimiento-titulo">
          <h2 id="res-seguimiento-titulo">Estudiantes que necesitan atención</h2>
          <ul class="doc-lista" id="res-seguimiento"></ul>
        </section>
        <div class="doc-rejilla">
          <section aria-labelledby="h-alertas"><h2 id="h-alertas">Avisos de exámenes y cuentas</h2><ul class="doc-lista" id="res-alertas"></ul></section>
          <section aria-labelledby="h-reciente"><h2 id="h-reciente">Lo último que hiciste</h2><ul class="doc-lista" id="res-reciente"></ul></section>
        </div>
        <h2>Presentando examen ahora</h2>
        <div class="doc-table-wrap">
          <table class="doc-table">
            <caption class="doc-solo-lectores">Exámenes en curso</caption>
            <thead><tr><th scope="col">Estudiante</th><th scope="col">Grupo</th><th scope="col">Examen</th>
              <th scope="col">Tiempo restante</th><th scope="col">Salidas de la pestaña</th></tr></thead>
            <tbody id="res-curso"></tbody>
          </table>
        </div>
        <p class="doc-muted">Se actualiza solo cada 30 segundos.</p>`;
      el.addEventListener('click', e => {
        const ir = e.target.closest('[data-ir]');
        if (ir) Panel.irA(ir.dataset.ir);
        const f = e.target.closest('[data-ficha]');
        if (f) Panel.abrirFicha(Number(f.dataset.ficha)).catch(err => Panel.toast(err.message, 'error'));
        if (e.target.closest('[data-ocultar-pasos]')) {
          try { localStorage.setItem('primerosPasosOculto', '1'); } catch (err) { /* sin almacenamiento */ }
          $('res-pasos').hidden = true;
        }
      });
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
