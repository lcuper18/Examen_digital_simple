// Pestaña Notas: notas ponderadas por materia
(function () {
  const COMPONENTES = ['trabajo_cotidiano', 'tareas', 'prueba01', 'prueba02', 'proyecto', 'asistencia'];
  const ETIQUETAS = {
    trabajo_cotidiano: 'TC', tareas: 'Tareas', prueba01: 'Prueba 01',
    prueba02: 'Prueba 02', proyecto: 'Proyecto', asistencia: 'Asistencia',
  };
  let ponderaciones = {};
  let sinGuardar = false;

  function calcularFinal(v) {
    return Math.round(COMPONENTES.reduce((s, c) => s + (v[c] || 0) * ponderaciones[c] / 100, 0) * 10) / 10;
  }

  function marcarCambios(valor) {
    sinGuardar = valor;
    $('notas-estado').textContent = valor ? 'Cambios sin guardar' : '';
  }

  async function cargarMaterias() {
    const data = await Panel.json('/api/docente/materias');
    ponderaciones = data.ponderaciones;
    document.querySelectorAll('[data-peso]').forEach(e => { e.textContent = `${ponderaciones[e.dataset.peso]}%`; });
    const select = $('n-materia');
    const actual = select.value;
    select.innerHTML = data.materias.map(m =>
      `<option value="${m.id}">${Panel.esc(m.seccion)} · Periodo ${m.periodo} · ${Panel.esc(m.nombre)}</option>`).join('');
    if (actual) select.value = actual;
    await cargarNotas();
  }

  async function cargarNotas() {
    const id = $('n-materia').value;
    if (!id) return;
    const data = await Panel.json(`/api/docente/notas?materia_id=${id}`);
    $('tabla-notas').querySelector('tbody').innerHTML = data.notas.map(n => `
      <tr data-id="${n.estudiante_id}">
        <th scope="row">${Panel.esc(Panel.nombre(n))}</th>
        ${COMPONENTES.map(c => `<td><input type="number" min="0" max="100" step="0.1" data-c="${c}"
          aria-label="${ETIQUETAS[c]} de ${Panel.esc(n.nombre)} ${Panel.esc(n.apellido1)}" value="${n[c] ?? ''}"></td>`).join('')}
        <td class="doc-final"></td>
      </tr>`).join('');
    document.querySelectorAll('#tabla-notas tbody tr').forEach(actualizarFila);
    actualizarResumen();
    marcarCambios(false);
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
    const v = valoresDeFila(tr);
    const final = calcularFinal(v);
    const vacia = COMPONENTES.every(c => v[c] === null);
    const celda = tr.querySelector('.doc-final');
    celda.textContent = vacia ? '—' : final.toFixed(1);
    celda.classList.toggle('doc-pending', vacia);
    celda.classList.toggle('low', !vacia && final < 70);
    celda.classList.toggle('good', !vacia && final >= 70);
  }

  function actualizarResumen() {
    const filas = [...document.querySelectorAll('#tabla-notas tbody tr')];
    const finales = filas.map(tr => {
      const v = valoresDeFila(tr);
      return COMPONENTES.every(c => v[c] !== null) ? calcularFinal(v) : null;
    }).filter(x => x !== null);
    $('notas-resumen').textContent = finales.length
      ? `${finales.length}/${filas.length} con notas completas · promedio ${(finales.reduce((a, b) => a + b, 0) / finales.length).toFixed(1)} · máx ${Math.max(...finales)} · mín ${Math.min(...finales)}`
      : `${filas.length} estudiantes · aún sin notas completas`;
  }

  async function guardar() {
    if (document.querySelector('#tabla-notas input.invalid')) return Panel.toast('Hay notas fuera del rango 0-100', 'error');
    const notas = [...document.querySelectorAll('#tabla-notas tbody tr')]
      .map(tr => ({ estudiante_id: Number(tr.dataset.id), ...valoresDeFila(tr) }));
    await Panel.json('/api/docente/notas', { method: 'PUT', body: { materia_id: Number($('n-materia').value), notas } });
    marcarCambios(false);
    Panel.toast('Notas guardadas');
  }

  async function importar(componente) {
    const codigo = await Panel.pedir(
      `Código del examen a importar como ${ETIQUETAS[componente]} (ej. SGC01)`, '',
      { titulo: `Importar ${ETIQUETAS[componente]}` });
    if (!codigo) return;
    if (sinGuardar && !(await Panel.confirmar('Tienes cambios sin guardar; se descartarán al importar.', { texto: 'Importar' }))) return;
    const data = await Panel.json('/api/docente/notas/importar-prueba', {
      method: 'POST',
      body: { materia_id: Number($('n-materia').value), componente, codigo_examen: codigo },
    });
    Panel.toast(`Se importaron ${data.importadas} notas`);
    await cargarNotas();
  }

  Panel.registrar('notas', 'Notas', {
    init(el) {
      el.innerHTML = `
        <div class="doc-toolbar">
          <label>Materia <select id="n-materia"></select></label>
          <button class="btn btn-secondary" id="btn-importar-p01">Importar Prueba 01</button>
          <button class="btn btn-secondary" id="btn-importar-p02">Importar Prueba 02</button>
          <button class="btn btn-secondary" id="btn-exportar-notas">Exportar CSV</button>
          <button class="btn btn-primary" id="btn-guardar-notas">Guardar notas</button>
        </div>
        <p class="doc-muted"><span id="notas-resumen" aria-live="polite"></span> <strong id="notas-estado" class="doc-sesion-alerta"></strong></p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-notas">
            <caption class="doc-solo-lectores">Notas de la materia seleccionada</caption>
            <thead><tr>
              <th scope="col">Estudiante</th>
              ${COMPONENTES.map(c => `<th scope="col">${ETIQUETAS[c]} <small data-peso="${c}"></small></th>`).join('')}
              <th scope="col">Nota final</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('n-materia').addEventListener('change', run(async () => {
        if (sinGuardar && !(await Panel.confirmar('Tienes cambios sin guardar; se descartarán.', { texto: 'Cambiar de materia' }))) return;
        await cargarNotas();
      }));
      $('tabla-notas').addEventListener('input', e => {
        if (!e.target.matches('input')) return;
        actualizarFila(e.target.closest('tr'));
        actualizarResumen();
        marcarCambios(true);
      });
      $('btn-guardar-notas').addEventListener('click', run(guardar));
      $('btn-importar-p01').addEventListener('click', run(() => importar('prueba01')));
      $('btn-importar-p02').addEventListener('click', run(() => importar('prueba02')));
      $('btn-exportar-notas').addEventListener('click', () => {
        const id = $('n-materia').value;
        if (id) Panel.descargar(`/api/docente/notas/exportar?materia_id=${id}`, `notas_${id}.csv`);
      });
    },
    mostrar: cargarMaterias,
  });
})();
