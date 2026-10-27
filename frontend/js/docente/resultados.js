// Pestaña Resultados: intentos de examen, detalle pregunta por pregunta y reinicio
(function () {
  let intentos = [];
  let el;

  const porcentaje = (i) => (i.total ? Math.round((i.puntuacion / i.total) * 1000) / 10 : 0);

  function llenarFiltro(id, valores, etiquetaTodos) {
    const select = $(id);
    const actual = select.value;
    select.innerHTML = `<option value="">${etiquetaTodos}</option>` +
      valores.map(v => `<option value="${Panel.esc(v)}">${Panel.esc(v)}</option>`).join('');
    select.value = valores.includes(actual) ? actual : '';
  }

  async function cargar() {
    intentos = (await Panel.json('/api/docente/intentos')).intentos;
    llenarFiltro('f-examen', [...new Set(intentos.map(i => i.codigo_examen))].sort(), 'Todos');
    llenarFiltro('f-seccion', [...new Set(intentos.map(i => i.seccion))].sort(), 'Todas');
    render();
  }

  function render() {
    const examen = $('f-examen').value;
    const seccion = $('f-seccion').value;
    const lista = intentos.filter(i => (!examen || i.codigo_examen === examen) && (!seccion || i.seccion === seccion));
    const enviados = lista.filter(i => i.fecha_fin);
    const promedio = enviados.length ? (enviados.reduce((s, i) => s + porcentaje(i), 0) / enviados.length).toFixed(1) : '—';
    $('res-resumen').textContent =
      `${lista.length} intentos · ${enviados.length} enviados · promedio ${promedio}` +
      (enviados.length < lista.length ? ` · ${lista.length - enviados.length} sin enviar` : '');

    $('tabla-intentos').querySelector('tbody').innerHTML = lista.map(i => {
      const enviado = !!i.fecha_fin;
      const estado = enviado ? '<span class="doc-pill ok">Enviado</span>' : '<span class="doc-pill wait">Sin enviar</span>';
      const salidas = i.incidencias > 0 ? `<span class="doc-pill warn">${i.incidencias}</span>` : '0';
      return `<tr>
        <td>${Panel.esc(Panel.nombre(i))}</td>
        <td>${Panel.esc(i.seccion)}</td>
        <td>${Panel.esc(i.codigo_examen)}</td>
        <td>${enviado ? `${i.puntuacion}/${i.total} (${porcentaje(i)})` : '<span class="doc-pending">—</span>'}</td>
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
    const { intento } = await Panel.json(`/api/docente/intentos/${id}`);
    const e = intento.estudiante;
    const items = intento.preguntas.map(p => {
      const n = String(p.numero);
      const dada = intento.respuestas[n];
      const correcta = intento.respuestas_correctas[n];
      const ok = dada === correcta;
      const texto = (letra) => letra ? `${letra}) ${Panel.esc(p.opciones[letra])}` : 'Sin contestar';
      return `<div class="result-item ${ok ? 'correct' : 'wrong'}">
        <div class="result-question-header">
          <span class="result-question-num">${Panel.esc(p.numero)}.</span>
          <span class="result-question-topic">[${Panel.esc(p.tema)}]</span>
        </div>
        <div class="result-question-text">${Panel.esc(p.pregunta)}</div>
        <div class="result-details">
          <span class="user-answer">Respuesta: ${texto(dada)}</span>
          ${ok ? '' : `<span class="correct-answer">Correcta: ${texto(correcta)}</span>`}
          <span class="result-status">${ok ? '✓' : '✗'}</span>
        </div>
      </div>`;
    }).join('');
    await Panel.dialogo({
      titulo: `${e.nombre} ${e.apellido1} · ${intento.codigo_examen}`,
      ancho: 'ancho',
      cuerpo: `<p class="doc-muted">Sección ${Panel.esc(e.seccion)} · ${intento.puntuacion}/${intento.total} ·
        Salidas de la pestaña: ${intento.incidencias}</p><div class="doc-detalle-lista">${items}</div>`,
    });
  }

  async function reiniciar(id) {
    const i = intentos.find(x => x.id === id);
    const ok = await Panel.confirmar(
      `Se borrará el resultado de ${Panel.nombre(i)} en ${i.codigo_examen} y podrá presentar el examen de nuevo.`,
      { titulo: 'Reiniciar intento', texto: 'Reiniciar', peligro: true });
    if (!ok) return;
    await Panel.json(`/api/docente/intentos/${id}`, { method: 'DELETE' });
    Panel.toast('Intento reiniciado');
    await cargar();
  }

  Panel.registrar('resultados', 'Resultados', {
    init(seccion) {
      el = seccion;
      el.innerHTML = `
        <div class="doc-toolbar">
          <label>Examen <select id="f-examen"></select></label>
          <label>Sección <select id="f-seccion"></select></label>
          <button class="btn btn-secondary" id="btn-refrescar">Actualizar</button>
          <button class="btn btn-primary" id="btn-exportar-intentos">Exportar CSV</button>
        </div>
        <p id="res-resumen" class="doc-muted" aria-live="polite"></p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-intentos">
            <caption class="doc-solo-lectores">Intentos de examen</caption>
            <thead><tr>
              <th scope="col">Estudiante</th><th scope="col">Sección</th><th scope="col">Examen</th>
              <th scope="col">Nota</th><th scope="col">Estado</th><th scope="col">Salidas</th><th scope="col">Acciones</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
      $('f-examen').addEventListener('change', render);
      $('f-seccion').addEventListener('change', render);
      $('btn-refrescar').addEventListener('click', () => cargar().catch(e => Panel.toast(e.message, 'error')));
      $('btn-exportar-intentos').addEventListener('click', () => Panel.descargar('/api/docente/intentos-exportar', 'intentos.csv'));
      $('tabla-intentos').addEventListener('click', e => {
        const run = (fn) => fn().catch(err => Panel.toast(err.message, 'error'));
        if (e.target.dataset.ver) run(() => verDetalle(Number(e.target.dataset.ver)));
        if (e.target.dataset.reiniciar) run(() => reiniciar(Number(e.target.dataset.reiniciar)));
      });
    },
    mostrar: cargar,
  });
})();
