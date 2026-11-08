// Pestaña Asistencia: pasar lista por fecha y resumen del período (art. 37 del Reglamento de Evaluación)
(function () {
  let estados = {};
  let sinGuardar = false;
  let sesionActual = null;
  let resumen = null;

  const hoyIso = () => {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  };
  const num = (n) => (n === null || n === undefined ? '—' : String(Math.round(n * 10) / 10));
  const fechaCorta = (iso) => { const [y, m, d] = iso.split('-'); return `${d}/${m}/${y}`; };

  function marcar(valor) {
    sinGuardar = valor;
    $('as-estado').textContent = valor ? 'Cambios sin guardar' : '';
  }

  function dibujarLista(d) {
    $('as-lecciones').value = d.lecciones;
    $('as-tema').value = d.tema;
    $('as-existe').textContent = d.existe ? 'Lista ya guardada: puedes corregirla.' : 'Lista nueva: todos aparecen presentes.';
    $('tabla-asistencia').querySelector('tbody').innerHTML = d.registros.map(r => `
      <tr data-id="${r.estudiante_id}">
        <th scope="row">${Panel.esc(Panel.nombre(r))}</th>
        <td><select data-campo="estado" aria-label="Estado de ${Panel.esc(r.nombre)} ${Panel.esc(r.apellido1)}">
          ${Object.entries(estados).map(([k, v]) => `<option value="${k}" ${k === r.estado ? 'selected' : ''}>${v}</option>`).join('')}
        </select></td>
        <td><input type="text" maxlength="200" data-campo="observacion" value="${Panel.esc(r.observacion)}"
          aria-label="Observación de ${Panel.esc(r.nombre)} ${Panel.esc(r.apellido1)}"></td>
      </tr>`).join('');
    marcar(false);
  }

  async function cargarLista() {
    const id = Panel.contexto.id();
    if (!id || !$('as-fecha').value) return;
    dibujarLista(await Panel.json(`/api/docente/asistencia/sesion?materia_id=${id}&fecha=${$('as-fecha').value}`));
  }

  async function cargarResumen() {
    const id = Panel.contexto.id();
    if (!id) return;
    resumen = await Panel.json(`/api/docente/asistencia/resumen?materia_id=${id}`);
    estados = resumen.estados;
    $('as-total').textContent = resumen.lecciones_totales
      ? `${resumen.lecciones_totales} lecciones impartidas en ${resumen.sesiones.length} fechas`
      : 'Aún no hay listas guardadas en este período.';
    $('tabla-as-resumen').querySelector('tbody').innerHTML = resumen.estudiantes.map(e => `
      <tr>
        <th scope="row">${Panel.esc(Panel.nombre(e))}</th>
        <td class="num">${e.ausencias}</td><td class="num">${e.tardias}</td><td class="num">${e.justificadas}</td>
        <td class="num">${num(e.injustificadas)}</td><td class="num">${num(e.porcentaje_ausencias)}%</td>
        <td class="num ${e.puntos !== null && e.puntos < 3 ? 'low' : ''}"><strong>${num(e.puntos)}</strong> / ${resumen.puntos_maximos}</td>
      </tr>`).join('');
    $('as-sesiones').innerHTML = resumen.sesiones.length ? resumen.sesiones.slice().reverse().map(s => `
      <li><button class="btn btn-secondary" data-ir="${s.fecha}">${fechaCorta(s.fecha)}</button>
        ${s.lecciones} lecc.${s.tema ? ' · ' + Panel.esc(s.tema) : ''}
        <button class="btn btn-secondary" data-borrar="${s.id}" aria-label="Eliminar la lista del ${fechaCorta(s.fecha)}">Eliminar</button></li>`).join('')
      : '<li class="doc-pending">Sin fechas guardadas</li>';
  }

  async function cargarTodo() {
    if (!$('as-fecha').value) $('as-fecha').value = hoyIso();
    await cargarResumen();
    await cargarLista();
  }

  async function guardar() {
    const registros = [...document.querySelectorAll('#tabla-asistencia tbody tr')].map(tr => ({
      estudiante_id: Number(tr.dataset.id),
      estado: tr.querySelector('[data-campo=estado]').value,
      observacion: tr.querySelector('[data-campo=observacion]').value,
    }));
    await Panel.json('/api/docente/asistencia/sesion', {
      method: 'PUT',
      body: {
        materia_id: Number(Panel.contexto.id()), fecha: $('as-fecha').value,
        lecciones: Number($('as-lecciones').value), tema: $('as-tema').value, registros,
      },
    });
    Panel.toast('Lista guardada. La nota de asistencia se actualizó.');
    await cargarResumen();
    await cargarLista();
  }

  async function confirmarCambios() {
    return !sinGuardar || Panel.confirmar('Tienes cambios sin guardar; se descartarán.', { texto: 'Continuar' });
  }

  function imprimir() {
    const d = resumen;
    const m = d.materia;
    const filas = d.estudiantes.map(e => `<tr><td>${Panel.esc(Panel.nombre(e))}</td><td class="num">${e.ausencias}</td>
      <td class="num">${e.tardias}</td><td class="num">${e.justificadas}</td><td class="num">${num(e.porcentaje_ausencias)}%</td>
      <td class="num">${num(e.puntos)}</td></tr>`).join('');
    const detalle = d.estudiantes.filter(e => e.detalle.length).map(e => `<tr><td>${Panel.esc(Panel.nombre(e))}</td>
      <td>${e.detalle.map(x => `${fechaCorta(x.fecha)} ${Panel.esc(d.estados[x.estado])}${x.observacion ? ' (' + Panel.esc(x.observacion) + ')' : ''}`).join('<br>')}</td></tr>`).join('');
    Panel.imprimirHtml(`Asistencia ${m.seccion}`, `
      <h1>Informe de asistencia</h1>
      <p class="rep-meta">${Panel.esc(m.seccion)} · ${Panel.esc(m.nombre)} · Periodo ${m.periodo} · ${d.lecciones_totales} lecciones impartidas · Generado el ${new Date().toLocaleDateString('es-CR')}</p>
      <table class="rep-tabla"><thead><tr><th>Estudiante</th><th class="num">Ausencias</th><th class="num">Tardías</th>
        <th class="num">Justificadas</th><th class="num">% ausencias inj.</th><th class="num">Puntos</th></tr></thead><tbody>${filas}</tbody></table>
      <p class="rep-meta">Cada llegada tardía injustificada menor de 10 minutos cuenta como media ausencia; mayor de 10 minutos, como una ausencia.</p>
      ${detalle ? `<h2>Detalle de novedades</h2><table class="rep-tabla"><thead><tr><th>Estudiante</th><th>Fechas</th></tr></thead><tbody>${detalle}</tbody></table>` : ''}
      <div class="rep-firma"><div>Docente</div><div>Sello institucional</div></div>`);
  }

  Panel.registrar('asistencia', 'Asistencia', {
    init(el) {
      el.innerHTML = `
        <div class="doc-toolbar">
          <label>Fecha <input type="date" id="as-fecha"></label>
          <label>Lecciones <input type="number" id="as-lecciones" min="1" max="12" value="2" class="doc-corto"></label>
          <label>Tema <input type="text" id="as-tema" maxlength="200" placeholder="opcional"></label>
          <button class="btn btn-secondary" id="btn-todos-presentes">Todos presentes</button>
          <button class="btn btn-primary" id="btn-guardar-lista">Guardar lista</button>
        </div>
        <p class="doc-muted"><span id="as-existe" aria-live="polite"></span> <strong id="as-estado" class="doc-sesion-alerta"></strong></p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-asistencia">
            <caption class="doc-solo-lectores">Lista de asistencia de la fecha</caption>
            <thead><tr><th scope="col">Estudiante</th><th scope="col">Estado</th><th scope="col">Observación</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <h2>Resumen del período</h2>
        <p class="doc-muted" id="as-total"></p>
        <div class="doc-toolbar">
          <button class="btn btn-secondary" id="btn-as-excel">Exportar Excel</button>
          <button class="btn btn-secondary" id="btn-as-imprimir">Imprimir informe</button>
        </div>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-as-resumen">
            <caption class="doc-solo-lectores">Resumen de asistencia por estudiante</caption>
            <thead><tr><th scope="col">Estudiante</th><th scope="col">Ausencias</th><th scope="col">Tardías</th>
              <th scope="col">Justificadas</th><th scope="col">Ausencias inj. (equiv.)</th><th scope="col">% ausencias</th><th scope="col">Puntos</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <h2>Fechas guardadas</h2>
        <ul id="as-sesiones" class="doc-lista"></ul>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('as-fecha').addEventListener('change', run(async () => { if (await confirmarCambios()) await cargarLista(); }));
      $('tabla-asistencia').addEventListener('input', () => marcar(true));
      $('as-lecciones').addEventListener('input', () => marcar(true));
      $('as-tema').addEventListener('input', () => marcar(true));
      $('btn-todos-presentes').addEventListener('click', () => {
        document.querySelectorAll('#tabla-asistencia [data-campo=estado]').forEach(s => { s.value = 'P'; });
        marcar(true);
      });
      $('btn-guardar-lista').addEventListener('click', run(guardar));
      $('btn-as-excel').addEventListener('click', () => {
        const id = Panel.contexto.id();
        if (id) Panel.descargar(`/api/docente/asistencia/excel?materia_id=${id}`, `asistencia_${id}.xlsx`);
      });
      $('btn-as-imprimir').addEventListener('click', () => resumen && imprimir());
      $('as-sesiones').addEventListener('click', run(async (ev) => {
        if (ev.target.dataset.ir) {
          if (!(await confirmarCambios())) return;
          $('as-fecha').value = ev.target.dataset.ir;
          await cargarLista();
        }
        if (ev.target.dataset.borrar) {
          if (!(await Panel.confirmar('Se elimina la lista de esa fecha y se recalcula la asistencia.', { texto: 'Eliminar' }))) return;
          await Panel.json(`/api/docente/asistencia/sesion/${ev.target.dataset.borrar}`, { method: 'DELETE' });
          Panel.toast('Lista eliminada');
          await cargarResumen();
          await cargarLista();
        }
      }));
    },
    usaContexto: true,
    hayCambios: () => sinGuardar,
    mostrar: cargarTodo,
  });
})();
