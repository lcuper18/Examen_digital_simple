// Pestaña Notas: notas ponderadas por materia
(function () {
  // Se notan en puntos (como en las hojas del docente); el servidor guarda 0-100 por componente.
  let COMPONENTES = ['trabajo_cotidiano', 'tareas', 'prueba01', 'prueba02', 'proyecto', 'asistencia'];
  let ETIQUETAS = {
    trabajo_cotidiano: 'Trabajo cotidiano', tareas: 'Tareas', prueba01: 'Prueba 1',
    prueba02: 'Prueba 2', proyecto: 'Proyecto', asistencia: 'Asistencia',
  };
  let ponderaciones = {};
  const redondear = (n, d = 2) => Math.round(n * 10 ** d) / 10 ** d;
  const aPuntos = (pct, c) => (pct === null || pct === undefined ? '' : redondear(pct * ponderaciones[c] / 100));
  const aPorcentaje = (pts, c) => (pts === null || !ponderaciones[c] ? (pts === null ? null : 0) : redondear(pts / ponderaciones[c] * 100, 4));
  let notaMinima = 70;
  let sinGuardar = false;

  function calcularFinal(v) {
    return Math.round(COMPONENTES.reduce((s, c) => s + (v[c] || 0), 0) * 10) / 10;
  }

  function marcarCambios(valor) {
    sinGuardar = valor;
    $('notas-estado').textContent = valor ? 'Cambios sin guardar' : 'Todo guardado';
  }

  async function cargarNotas() {
    const id = Panel.contexto.id();
    if (!id) return;
    const data = await Panel.json(`/api/docente/notas?materia_id=${id}`);
    ponderaciones = data.ponderaciones;
    notaMinima = data.nota_minima;
    mostrarPublicacion(data.publicado);
    document.querySelectorAll('[data-peso]').forEach(e => { e.textContent = `/${ponderaciones[e.dataset.peso]}`; });
    $('tabla-notas').querySelector('tbody').innerHTML = data.notas.map(n => `
      <tr data-id="${n.estudiante_id}">
        <th scope="row">${Panel.esc(Panel.nombre(n))}</th>
        ${COMPONENTES.map(c => `<td><input type="number" min="0" max="${ponderaciones[c]}" step="0.01" data-c="${c}"
          aria-label="${ETIQUETAS[c]} de ${Panel.esc(n.nombre)} ${Panel.esc(n.apellido1)} (puntos de ${ponderaciones[c]})" value="${aPuntos(n[c], c)}"></td>`).join('')}
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
      input.classList.toggle('invalid', num !== null && (Number.isNaN(num) || num < 0 || num > ponderaciones[input.dataset.c]));
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
    celda.classList.toggle('low', !vacia && final < notaMinima);
    celda.classList.toggle('good', !vacia && final >= notaMinima);
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
    if (document.querySelector('#tabla-notas input.invalid')) return Panel.toast('Hay notas que superan los puntos del componente', 'error');
    const notas = [...document.querySelectorAll('#tabla-notas tbody tr')]
      .map(tr => {
        const v = valoresDeFila(tr);
        return { estudiante_id: Number(tr.dataset.id), ...Object.fromEntries(COMPONENTES.map(c => [c, aPorcentaje(v[c], c)])) };
      });
    await Panel.json('/api/docente/notas', { method: 'PUT', body: { materia_id: Number(Panel.contexto.id()), notas } });
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
      body: { materia_id: Number(Panel.contexto.id()), componente, codigo_examen: codigo },
    });
    Panel.toast(`Se importaron ${data.importadas} notas`);
    await cargarNotas();
  }

  let publicado = false;
  function mostrarPublicacion(valor) {
    publicado = valor;
    $('n-publicado-sw').checked = valor;
    $('n-publicado-txt').textContent = valor ? 'Visible para los estudiantes en «Mis notas»' : 'Oculta para los estudiantes';
  }

  async function cambiarPublicacion() {
    const quiere = $('n-publicado-sw').checked;
    if (quiere && sinGuardar) { mostrarPublicacion(false); return Panel.toast('Guarda las notas antes de publicarlas', 'error'); }
    if (quiere && !(await Panel.confirmar(
      'Cada estudiante podrá ver sus notas, su asistencia y las observaciones de sus actividades de esta materia.',
      { titulo: 'Publicar notas', texto: 'Publicar' }))) return mostrarPublicacion(false);
    try {
      const data = await Panel.json(`/api/docente/materias/${Panel.contexto.id()}/publicacion`, {
        method: 'PUT', body: { publicado: quiere },
      });
      mostrarPublicacion(data.publicado);
      Panel.toast(data.publicado ? 'Notas publicadas a los estudiantes' : 'Notas ocultas');
    } catch (e) {
      mostrarPublicacion(publicado);
      throw e;
    }
  }

  async function importarVinculadas() {
    if (sinGuardar && !(await Panel.confirmar('Tienes cambios sin guardar; se descartarán al importar.', { texto: 'Importar' }))) return;
    const data = await Panel.json('/api/docente/notas/importar-prueba', {
      method: 'POST', body: { materia_id: Number(Panel.contexto.id()) },
    });
    Panel.toast(`Se importaron ${data.importadas} notas de ${data.examenes.join(', ')}`);
    await cargarNotas();
  }

  async function importarHoja() {
    const archivo = await Panel.dialogo({
      titulo: 'Importar hoja de notas',
      cuerpo: `<p class="doc-muted">CSV (separado por «;») o Excel con las columnas Id o Nombre, Trabajo cotidiano, Tareas, Prueba1, Prueba2, Proyecto y Asistencia,
        <strong>en puntos</strong> como en tus hojas. Las celdas vacías no cambian nada.</p>
        <label class="doc-campo">Archivo <input type="file" id="hoja-archivo" accept=".csv,.xlsx"></label>`,
      botones: [{ texto: 'Cancelar', valor: null },
        { texto: 'Importar', primario: true, valor: f => f.querySelector('#hoja-archivo').files[0] || null }],
    });
    if (!archivo) return;
    if (sinGuardar && !(await Panel.confirmar('Tienes cambios sin guardar; se descartarán al importar.', { texto: 'Importar' }))) return;
    const r = await Panel.subir(`/api/docente/notas/importar-hoja?materia_id=${Panel.contexto.id()}`, archivo);
    const detalle = [...r.sin_pareja.map(n => `Sin pareja: ${n}`), ...r.avisos];
    if (detalle.length) {
      await Panel.dialogo({ titulo: `Se importaron ${r.importados} estudiantes`,
        cuerpo: `<p>Revisa estas filas:</p><ul>${detalle.map(d => `<li>${Panel.esc(d)}</li>`).join('')}</ul>` });
    } else {
      Panel.toast(`Se importaron ${r.importados} estudiantes`);
    }
    await cargarNotas();
  }

  Panel.registrar('notas', 'Notas', {
    init(el) {
      el.innerHTML = `
        <div class="doc-toolbar doc-toolbar-fila">
          <label class="doc-interruptor"><input type="checkbox" role="switch" id="n-publicado-sw"><span id="n-publicado-txt"></span></label>
          <button class="btn btn-secondary" id="btn-mas-notas">Más ▾</button>
        </div>
        <p class="doc-muted" id="notas-resumen" aria-live="polite"></p>
        <div class="doc-table-wrap doc-hoja">
          <table class="doc-table" id="tabla-notas">
            <caption class="doc-solo-lectores">Notas de la materia seleccionada</caption>
            <thead><tr>
              <th scope="col">Estudiante</th>
              ${COMPONENTES.map(c => `<th scope="col">${ETIQUETAS[c]} <small data-peso="${c}"></small></th>`).join('')}
              <th scope="col">Nota final</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="doc-barra-fija">
          <strong id="notas-estado" class="doc-barra-estado" aria-live="polite"></strong>
          <button class="btn btn-primary" id="btn-guardar-notas">Guardar notas</button>
        </div>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('tabla-notas').addEventListener('input', e => {
        if (!e.target.matches('input')) return;
        actualizarFila(e.target.closest('tr'));
        actualizarResumen();
        marcarCambios(true);
      });
      $('btn-guardar-notas').addEventListener('click', run(() => Panel.conCarga($('btn-guardar-notas'), guardar)));
      $('n-publicado-sw').addEventListener('change', run(cambiarPublicacion));
      Panel.navegarCeldas($('tabla-notas'));
      Panel.menuDesplegable($('btn-mas-notas'), [
        { texto: 'Importar exámenes vinculados', accion: run(importarVinculadas) },
        { texto: 'Cargar una hoja de notas (Excel)…', accion: run(importarHoja) },
        { texto: 'Importar un examen como Prueba 1…', accion: run(() => importar('prueba01')) },
        { texto: 'Importar un examen como Prueba 2…', accion: run(() => importar('prueba02')) },
        { texto: 'Descargar notas (para Excel)', accion: () => {
          const id = Panel.contexto.id();
          if (id) Panel.descargar(`/api/docente/notas/exportar?materia_id=${id}`, `notas_${id}.csv`);
        } },
      ]);
    },
    usaContexto: true,
    hayCambios: () => sinGuardar,
    mostrar: cargarNotas,
  });
})();
