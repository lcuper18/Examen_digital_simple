// Pestaña Resultados: intentos de examen, detalle pregunta por pregunta y reinicio
(function () {
  let intentos = [];
  let el;

  const porcentaje = (i) => (i.total ? Math.round((i.puntuacion / i.total) * 1000) / 10 : 0);

  function estadoDe(i) {
    if (i.anulado) return 'anulado';
    return i.fecha_fin ? 'enviado' : 'abierto';
  }

  function duracionUsada(i) {
    if (!i.fecha_fin) return '—';
    const min = Math.round((new Date(i.fecha_fin) - new Date(i.fecha_inicio)) / 60000);
    return `${min} min`;
  }

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
    const estado = $('f-estado').value;
    const lista = intentos.filter(i =>
      (!examen || i.codigo_examen === examen) && (!seccion || i.seccion === seccion) &&
      (!estado || (estado === 'sospechoso' ? i.sospechoso : estadoDe(i) === estado)));
    const enviados = lista.filter(i => i.fecha_fin && !i.anulado);
    const promedio = enviados.length ? (enviados.reduce((s, i) => s + porcentaje(i), 0) / enviados.length).toFixed(1) : '—';
    $('res-resumen').textContent =
      `${lista.length} intentos · ${enviados.length} enviados · promedio ${promedio}` +
      (enviados.length < lista.length ? ` · ${lista.length - enviados.length} sin enviar o anulados` : '');

    $('tabla-intentos').querySelector('tbody').innerHTML = lista.map(i => {
      const est = estadoDe(i);
      const pill = { enviado: '<span class="doc-pill ok">Enviado</span>', abierto: '<span class="doc-pill wait">En curso</span>',
        anulado: '<span class="doc-pill warn">Anulado</span>' }[est];
      const sospechoso = i.sospechoso ? ' <span class="doc-pill warn" title="Marcado como sospechoso">Sospechoso</span>' : '';
      const salidas = i.incidencias > 0 ? `<span class="doc-pill warn">${i.incidencias}</span>` : '0';
      return `<tr class="${est === 'anulado' ? 'doc-fila-anulada' : ''}">
        <th scope="row">${Panel.esc(Panel.nombre(i))}</th>
        <td>${Panel.esc(i.seccion)}</td>
        <td>${Panel.esc(i.codigo_examen)}</td>
        <td>${i.fecha_fin ? `${i.puntuacion}/${i.total} (${porcentaje(i)})` : '<span class="doc-pending">—</span>'}</td>
        <td>${pill}${sospechoso}</td>
        <td>${duracionUsada(i)}${i.minutos_extra ? ` <small class="doc-muted">+${i.minutos_extra}</small>` : ''}</td>
        <td>${salidas}</td>
        <td class="doc-actions">
          <button class="btn btn-secondary" data-ver="${i.id}">Detalle</button>
          <button class="btn btn-secondary" data-acciones="${i.id}" aria-haspopup="dialog">Acciones…</button>
        </td>
      </tr>`;
    }).join('') || '<tr><td colspan="8" class="doc-pending">Sin intentos</td></tr>';
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
      cuerpo: `<p class="doc-muted">Sección ${Panel.esc(e.seccion)} ·
        ${intento.fecha_fin ? `${intento.puntuacion}/${intento.total}` : 'intento en curso (respuestas guardadas)'} ·
        Salidas de la pestaña: ${intento.incidencias}${intento.anulado ? ' · <strong>ANULADO</strong>' : ''}${intento.sospechoso ? ' · <strong>SOSPECHOSO</strong>' : ''}</p>
        ${intento.nota_docente ? `<p class="doc-muted">Nota del docente: ${Panel.esc(intento.nota_docente)}</p>` : ''}
        <div class="doc-detalle-lista">${items}</div>`,
    });
  }

  async function acciones(id) {
    const i = intentos.find(x => x.id === id);
    const abierto = !i.fecha_fin && !i.anulado;
    const accion = await Panel.dialogo({
      titulo: `${Panel.nombre(i)} · ${i.codigo_examen}`,
      cuerpo: '<p class="doc-muted">Elige una acción sobre este intento:</p>',
      botones: [
        ...(abierto ? [{ texto: 'Dar tiempo extra', valor: 'tiempo' }, { texto: 'Cerrar y calificar', valor: 'cerrar' }] : []),
        { texto: i.anulado ? 'Restaurar intento' : 'Anular intento', valor: 'anular' },
        { texto: i.sospechoso ? 'Quitar marca de sospechoso' : 'Marcar sospechoso', valor: 'sospechoso' },
        { texto: 'Reiniciar (borrar)', valor: 'reiniciar' },
        { texto: 'Cancelar', valor: null },
      ],
    });
    if (accion === 'tiempo') {
      const m = await Panel.pedir('Minutos adicionales (1-240)', '10', { titulo: 'Tiempo extra' });
      if (!m) return;
      await Panel.json(`/api/docente/intentos/${id}/tiempo-extra`, { method: 'POST', body: { minutos: Number(m) } });
      Panel.toast(`+${m} minutos. El estudiante los recibe en menos de 30 segundos.`);
    } else if (accion === 'cerrar') {
      if (!(await Panel.confirmar('Se calificará con las respuestas guardadas hasta ahora y el estudiante ya no podrá continuar.',
        { titulo: 'Cerrar intento', texto: 'Cerrar y calificar', peligro: true }))) return;
      const r = await Panel.json(`/api/docente/intentos/${id}/cerrar`, { method: 'POST' });
      Panel.toast(`Intento cerrado: ${r.puntuacion}/${r.total}`);
    } else if (accion === 'anular') {
      if (i.anulado) {
        await Panel.json(`/api/docente/intentos/${id}/anular`, { method: 'POST', body: { anulado: false } });
        Panel.toast('Intento restaurado');
      } else {
        const motivo = await Panel.pedir('Motivo (opcional, queda en la bitácora)', '', { titulo: 'Anular intento' });
        if (motivo === null && !(await Panel.confirmar('¿Anular sin indicar motivo?', { texto: 'Anular', peligro: true }))) return;
        await Panel.json(`/api/docente/intentos/${id}/anular`, { method: 'POST', body: { anulado: true, motivo: motivo || '' } });
        Panel.toast('Intento anulado: ya no cuenta en notas ni reportes');
      }
    } else if (accion === 'sospechoso') {
      if (i.sospechoso) {
        await Panel.json(`/api/docente/intentos/${id}/sospechoso`, { method: 'POST', body: { sospechoso: false } });
      } else {
        const nota = await Panel.pedir('Observación (qué te llamó la atención)', i.nota_docente || '', { titulo: 'Marcar sospechoso' });
        if (nota === null) return;
        await Panel.json(`/api/docente/intentos/${id}/sospechoso`, { method: 'POST', body: { sospechoso: true, nota } });
      }
      Panel.toast('Intento actualizado');
    } else if (accion === 'reiniciar') {
      if (!(await Panel.confirmar(
        `Se borrará el resultado de ${Panel.nombre(i)} en ${i.codigo_examen} y podrá presentar el examen de nuevo.`,
        { titulo: 'Reiniciar intento', texto: 'Reiniciar', peligro: true }))) return;
      await Panel.json(`/api/docente/intentos/${id}`, { method: 'DELETE' });
      Panel.toast('Intento reiniciado');
    } else {
      return;
    }
    await cargar();
  }

  Panel.registrar('resultados', 'Resultados', {
    init(seccion) {
      el = seccion;
      el.innerHTML = `
        <div class="doc-toolbar">
          <label>Examen <select id="f-examen"></select></label>
          <label>Sección <select id="f-seccion"></select></label>
          <label>Estado <select id="f-estado">
            <option value="">Todos</option><option value="abierto">En curso</option><option value="enviado">Enviados</option>
            <option value="anulado">Anulados</option><option value="sospechoso">Sospechosos</option></select></label>
          <button class="btn btn-secondary" id="btn-refrescar">Actualizar</button>
          <button class="btn btn-primary" id="btn-exportar-intentos">Exportar CSV</button>
        </div>
        <p id="res-resumen" class="doc-muted" aria-live="polite"></p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-intentos">
            <caption class="doc-solo-lectores">Intentos de examen</caption>
            <thead><tr>
              <th scope="col">Estudiante</th><th scope="col">Sección</th><th scope="col">Examen</th>
              <th scope="col">Nota</th><th scope="col">Estado</th><th scope="col">Tiempo usado</th>
              <th scope="col">Salidas</th><th scope="col">Acciones</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
      $('f-examen').addEventListener('change', render);
      $('f-seccion').addEventListener('change', render);
      $('f-estado').addEventListener('change', render);
      $('btn-refrescar').addEventListener('click', () => cargar().catch(e => Panel.toast(e.message, 'error')));
      $('btn-exportar-intentos').addEventListener('click', () => Panel.descargar('/api/docente/intentos-exportar', 'intentos.csv'));
      $('tabla-intentos').addEventListener('click', e => {
        const run = (fn) => fn().catch(err => Panel.toast(err.message, 'error'));
        if (e.target.dataset.ver) run(() => verDetalle(Number(e.target.dataset.ver)));
        if (e.target.dataset.acciones) run(() => acciones(Number(e.target.dataset.acciones)));
      });
    },
    mostrar: cargar,
  });
})();
