// Pestaña Actividades: tareas, proyectos y trabajo cotidiano con rúbrica; califica por criterio
(function () {
  const ETIQUETA = {
    trabajo_cotidiano: 'Trabajo cotidiano', tareas: 'Tareas', prueba01: 'Prueba 01', prueba02: 'Prueba 02', proyecto: 'Proyecto',
  };
  let actividades = [];
  let estados = {};
  let calificando = null;   // { actividad, calificaciones }
  let sinGuardar = false;

  const num = (n) => (n === null || n === undefined ? '—' : String(Math.round(n * 100) / 100));
  const fecha = (iso) => (iso ? iso.split('-').reverse().join('/') : '—');

  // ---------- lista ----------
  async function cargarLista() {
    const id = Panel.contexto.id();
    if (!id) return;
    const data = await Panel.json(`/api/docente/actividades?materia_id=${id}`);
    actividades = data.actividades;
    estados = data.estados;
    $('ac-vista-calificar').hidden = true;
    $('ac-vista-lista').hidden = false;
    calificando = null;
    $('tabla-actividades').querySelector('tbody').innerHTML = actividades.length ? actividades.map(a => `
      <tr>
        <th scope="row">${Panel.esc(a.nombre)}<br><small class="doc-muted">${ETIQUETA[a.componente]}${a.criterios.length ? ` · ${a.criterios.length} criterios` : ''}</small></th>
        <td>${fecha(a.fecha_entrega)}</td><td class="num">${num(a.puntos_max)}</td><td class="num">${a.calificadas}</td>
        <td class="doc-actions">
          <button class="btn btn-primary" data-calificar="${a.id}">Calificar</button>
          <button class="btn btn-secondary" data-menu-act="${a.id}" aria-label="Más acciones de ${Panel.esc(a.nombre)}">⋯</button>
        </td>
      </tr>`).join('') : '<tr><td colspan="5" class="doc-pending">Aún no hay actividades en esta materia. Crea la primera con «Nueva actividad» o impórtala desde tu hoja de Excel.</td></tr>';
    document.querySelectorAll('[data-menu-act]').forEach(b => {
      const a = actividades.find(x => String(x.id) === b.dataset.menuAct);
      Panel.menuDesplegable(b, [
        { texto: 'Editar…', accion: () => editar(a) },
        { texto: 'Eliminar…', peligro: true, accion: async () => {
          if (!(await Panel.confirmar(`Se elimina «${a.nombre}» con todas sus calificaciones.`, { texto: 'Eliminar', peligro: true }))) return;
          await Panel.json(`/api/docente/actividades/${a.id}`, { method: 'DELETE' });
          Panel.toast('Actividad eliminada');
          await cargarLista();
        } },
      ]);
    });
  }

  // ---------- crear / editar ----------
  const aTextoCriterios = (cs) => cs.map(c => `${c.nombre}: ${c.puntos}`).join('\n');
  function deTextoCriterios(texto) {
    return texto.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
      const m = l.match(/^(.*?)\s*[:|]\s*([\d.,]+)\s*$/);
      if (!m) throw new Error(`Criterio no válido: «${l}». Usa «Nombre: puntos».`);
      return { nombre: m[1] || 'Criterio', puntos: Number(m[2].replace(',', '.')) };
    });
  }

  async function editar(a) {
    const datos = await Panel.dialogo({
      titulo: a ? 'Editar actividad' : 'Nueva actividad', ancho: 'doc-dialogo-ancho',
      cuerpo: `
        <label class="doc-campo">Nombre <input type="text" id="a-nombre" maxlength="150" value="${Panel.esc(a ? a.nombre : '')}"></label>
        <label class="doc-campo">Componente <select id="a-comp">${Object.entries(ETIQUETA).map(([k, v]) =>
          `<option value="${k}" ${a && a.componente === k ? 'selected' : (!a && k === 'tareas' ? 'selected' : '')}>${v}</option>`).join('')}</select></label>
        <label class="doc-campo">Fecha de entrega <input type="date" id="a-fecha" value="${a ? a.fecha_entrega || '' : ''}"></label>
        <label class="doc-campo">Criterios de la rúbrica (uno por línea: «Nombre: puntos»; déjalo vacío si no usas rúbrica)
          <textarea id="a-criterios" rows="6" placeholder="E1 Inventario: 4&#10;E2 Diagnóstico: 5">${Panel.esc(a ? aTextoCriterios(a.criterios) : '')}</textarea></label>
        <label class="doc-campo">Puntos de la actividad (solo si no hay criterios)
          <input type="number" id="a-puntos" min="0.5" step="0.5" value="${a && !a.criterios.length ? a.puntos_max : ''}"></label>`,
      botones: [{ texto: 'Cancelar', valor: null }, { texto: 'Guardar', primario: true, valor: f => {
        const criterios = deTextoCriterios(f.querySelector('#a-criterios').value);
        return {
          materia_id: Number(Panel.contexto.id()), nombre: f.querySelector('#a-nombre').value.trim(),
          componente: f.querySelector('#a-comp').value, fecha_entrega: f.querySelector('#a-fecha').value || null,
          criterios, puntos_max: criterios.length ? null : Number(f.querySelector('#a-puntos').value) || null,
        };
      } }],
    }).catch(e => { Panel.toast(e.message, 'error'); return null; });
    if (!datos) return;
    await Panel.json(a ? `/api/docente/actividades/${a.id}` : '/api/docente/actividades', { method: a ? 'PUT' : 'POST', body: datos });
    Panel.toast('Actividad guardada');
    await cargarLista();
  }

  async function importar() {
    const datos = await Panel.dialogo({
      titulo: 'Importar hoja de calificación',
      cuerpo: `<p class="doc-muted">Excel como tus <code>Calificacion_*.xlsx</code>: una fila por estudiante y columnas de criterios con sus puntos entre
        paréntesis (p. ej. «E1 Inventario (4)»), «Estado», «Observaciones para el estudiante» y «Notas internas». Si la actividad ya existe, se reemplaza.</p>
        <label class="doc-campo">Nombre de la actividad <input type="text" id="i-nombre" maxlength="150"></label>
        <label class="doc-campo">Componente <select id="i-comp">${Object.entries(ETIQUETA).map(([k, v]) =>
          `<option value="${k}" ${k === 'tareas' ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
        <label class="doc-campo">Fecha de entrega <input type="date" id="i-fecha"></label>
        <label class="doc-campo">Archivo <input type="file" id="i-archivo" accept=".xlsx"></label>`,
      botones: [{ texto: 'Cancelar', valor: null }, { texto: 'Importar', primario: true, valor: f => ({
        nombre: f.querySelector('#i-nombre').value.trim(), componente: f.querySelector('#i-comp').value,
        fecha: f.querySelector('#i-fecha').value, archivo: f.querySelector('#i-archivo').files[0],
      }) }],
    });
    if (!datos) return;
    if (!datos.nombre || !datos.archivo) return Panel.toast('Falta el nombre o el archivo', 'error');
    const q = new URLSearchParams({ materia_id: Panel.contexto.id(), componente: datos.componente, nombre: datos.nombre });
    if (datos.fecha) q.set('fecha_entrega', datos.fecha);
    const r = await Panel.subir(`/api/docente/actividades/importar?${q}`, datos.archivo);
    if (r.sin_pareja.length) {
      await Panel.dialogo({ titulo: `Se importaron ${r.importadas} estudiantes`,
        cuerpo: `<p>No encontré a estos estudiantes en la sección:</p><ul>${r.sin_pareja.map(n => `<li>${Panel.esc(n)}</li>`).join('')}</ul>` });
    } else {
      Panel.toast(`Se importaron ${r.importadas} calificaciones`);
    }
    await cargarLista();
  }

  // ---------- calificar ----------
  async function abrirCalificar(id) {
    const data = await Panel.json(`/api/docente/actividades/${id}/calificaciones`);
    calificando = data;
    estados = data.estados;
    const a = data.actividad;
    const rubrica = a.criterios.length > 0;
    $('ac-vista-lista').hidden = true;
    $('ac-vista-calificar').hidden = false;
    $('ac-titulo').textContent = `${a.nombre} · ${ETIQUETA[a.componente]} · ${num(a.puntos_max)} puntos`;
    $('tabla-calificar').querySelector('thead').innerHTML = `<tr><th scope="col">Estudiante</th>
      ${rubrica ? a.criterios.map(c => `<th scope="col">${Panel.esc(c.nombre)} <small>/${num(c.puntos)}</small></th>`).join('') : `<th scope="col">Puntos <small>/${num(a.puntos_max)}</small></th>`}
      <th scope="col">Total</th><th scope="col">Estado</th><th scope="col">Observación para el estudiante</th><th scope="col"><svg class="doc-candado" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></svg> Nota interna (privada)</th></tr>`;
    $('tabla-calificar').querySelector('tbody').innerHTML = data.calificaciones.map(c => `
      <tr data-id="${c.estudiante_id}">
        <th scope="row">${Panel.esc(Panel.nombre(c))}</th>
        ${rubrica ? a.criterios.map((cr, i) => `<td><input type="number" min="0" max="${cr.puntos}" step="0.25" data-criterio="${i}"
            value="${c.criterios[i] ?? ''}" aria-label="${Panel.esc(cr.nombre)} de ${Panel.esc(c.nombre)} ${Panel.esc(c.apellido1)}"></td>`).join('')
          : `<td><input type="number" min="0" max="${a.puntos_max}" step="0.25" data-puntos value="${c.puntos ?? ''}"
            aria-label="Puntos de ${Panel.esc(c.nombre)} ${Panel.esc(c.apellido1)}"></td>`}
        <td class="doc-final"></td>
        <td><select data-estado aria-label="Estado de ${Panel.esc(c.nombre)} ${Panel.esc(c.apellido1)}">${Object.entries(estados).map(([k, v]) =>
          `<option value="${k}" ${k === c.estado ? 'selected' : ''}>${v}</option>`).join('')}</select></td>
        <td><textarea rows="1" class="doc-auto" data-obs maxlength="2000" aria-label="Observación para ${Panel.esc(c.nombre)} ${Panel.esc(c.apellido1)}">${Panel.esc(c.observacion)}</textarea></td>
        <td><textarea rows="1" class="doc-auto" data-interna maxlength="2000" aria-label="Nota interna de ${Panel.esc(c.nombre)} ${Panel.esc(c.apellido1)}">${Panel.esc(c.nota_interna)}</textarea></td>
      </tr>`).join('');
    document.querySelectorAll('#tabla-calificar tbody tr').forEach(actualizarTotal);
    marcar(false);
  }

  function actualizarTotal(tr) {
    const a = calificando.actividad;
    const celdas = [...tr.querySelectorAll('[data-criterio], [data-puntos]')];
    const vacias = celdas.every(i => i.value === '');
    const total = celdas.reduce((s, i) => s + (Number(i.value) || 0), 0);
    celdas.forEach(i => i.classList.toggle('invalid', i.value !== '' && (Number(i.value) < 0 || Number(i.value) > Number(i.max))));
    const t = tr.querySelector('.doc-final');
    t.textContent = vacias ? '—' : `${num(total)} / ${num(a.puntos_max)}`;
    t.classList.toggle('doc-pending', vacias);
  }

  function marcar(v) {
    sinGuardar = v;
    $('ac-estado').textContent = v ? 'Cambios sin guardar' : 'Todo guardado';
  }

  async function guardarCalificaciones() {
    if (document.querySelector('#tabla-calificar input.invalid')) return Panel.toast('Hay puntos fuera de rango', 'error');
    const rubrica = calificando.actividad.criterios.length > 0;
    const calificaciones = [...document.querySelectorAll('#tabla-calificar tbody tr')].map(tr => {
      const fila = {
        estudiante_id: Number(tr.dataset.id), estado: tr.querySelector('[data-estado]').value,
        observacion: tr.querySelector('[data-obs]').value, nota_interna: tr.querySelector('[data-interna]').value,
      };
      if (rubrica) fila.criterios = [...tr.querySelectorAll('[data-criterio]')].map(i => (i.value === '' ? null : Number(i.value)));
      else { const p = tr.querySelector('[data-puntos]').value; fila.puntos = p === '' ? null : Number(p); }
      return fila;
    });
    // los entregados sin ninguna nota todavía quedan "en revisión" para no contarlos como 0 por error
    calificaciones.forEach(c => {
      const sinNota = rubrica ? c.criterios.every(x => x === null) : c.puntos === null;
      if (sinNota && ['entregado', 'tardio'].includes(c.estado)) c.estado = 'revision';
    });
    await Panel.json(`/api/docente/actividades/${calificando.actividad.id}/calificaciones`, {
      method: 'PUT', body: { calificaciones },
    });
    Panel.toast('Calificaciones guardadas. El componente en Notas se actualizó.');
    await abrirCalificar(calificando.actividad.id);
  }

  Panel.registrar('actividades', 'Actividades', {
    init(el) {
      el.innerHTML = `
        <section id="ac-vista-lista">
          <div class="doc-toolbar">
            <button class="btn btn-primary" id="btn-nueva-act">Nueva actividad</button>
            <button class="btn btn-secondary" id="btn-importar-act">Importar hoja (Excel)…</button>
          </div>
          <p class="doc-muted">El componente de cada estudiante en <strong>Notas</strong> se calcula con los puntos obtenidos entre los posibles de las
            actividades ya calificadas. «Sin entrega» cuenta 0; «en revisión» y «exonerado» no cuentan.</p>
          <div class="doc-table-wrap">
            <table class="doc-table" id="tabla-actividades">
              <caption class="doc-solo-lectores">Actividades de la materia</caption>
              <thead><tr><th scope="col">Actividad</th><th scope="col">Entrega</th><th scope="col">Puntos</th><th scope="col">Calificadas</th><th scope="col">Acciones</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </section>
        <section id="ac-vista-calificar" hidden>
          <nav class="doc-ruta" aria-label="Ruta">
            <button type="button" class="doc-enlace" id="btn-volver-act">Actividades</button>
            <span aria-hidden="true">›</span>
            <h2 id="ac-titulo" class="doc-sin-margen" aria-current="page"></h2>
          </nav>
          <div class="doc-table-wrap doc-hoja">
            <table class="doc-table" id="tabla-calificar"><caption class="doc-solo-lectores">Calificación por estudiante</caption><thead></thead><tbody></tbody></table>
          </div>
          <div class="doc-barra-fija">
            <strong id="ac-estado" class="doc-barra-estado" aria-live="polite"></strong>
            <button class="btn btn-primary" id="btn-guardar-cal">Guardar calificaciones</button>
          </div>
        </section>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('btn-nueva-act').addEventListener('click', run(() => editar(null)));
      $('btn-importar-act').addEventListener('click', run(importar));
      $('tabla-actividades').addEventListener('click', run(async (ev) => {
        const t = ev.target.dataset;
        if (t.calificar) await abrirCalificar(t.calificar);
      }));
      $('tabla-calificar').addEventListener('input', ev => {
        const tr = ev.target.closest('tr');
        if (tr && tr.dataset.id) actualizarTotal(tr);
        marcar(true);
      });
      Panel.navegarCeldas($('tabla-calificar'));
      $('btn-guardar-cal').addEventListener('click', run(guardarCalificaciones));
      $('btn-volver-act').addEventListener('click', run(async () => {
        if (sinGuardar && !(await Panel.confirmar('Tienes cambios sin guardar; se descartarán.', { texto: 'Volver' }))) return;
        await cargarLista();
      }));
    },
    usaContexto: true,
    hayCambios: () => !!calificando && sinGuardar,
    mostrar: cargarLista,
  });
})();
