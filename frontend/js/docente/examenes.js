// Pestaña Exámenes: habilitar, programar, restringir por sección y vincular a las notas de una o varias materias
(function () {
  let examenes = [];

  // ISO UTC <-> valor de <input type="datetime-local"> en hora local
  function aInputLocal(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  const deInputLocal = (valor) => (valor ? new Date(valor).toISOString() : null);
  const COMPONENTES = { prueba01: 'Prueba 1', prueba02: 'Prueba 2' };

  async function cargar() {
    examenes = (await Panel.json('/api/docente/examenes')).examenes;
    $('tabla-examenes').querySelector('tbody').innerHTML = examenes.map(e => {
      const ventana = e.desde || e.hasta
        ? `${e.desde ? 'Desde ' + Panel.formatoFecha(e.desde) : ''}${e.desde && e.hasta ? '<br>' : ''}${e.hasta ? 'Hasta ' + Panel.formatoFecha(e.hasta) : ''}`
        : '<span class="doc-pending">Sin límite</span>';
      return `<tr>
        <th scope="row">${Panel.esc(e.nombre)}<br><small class="doc-muted">${Panel.esc(e.codigo)} · ${e.duracion_minutos} min</small></th>
        <td>${e.habilitado ? '<span class="doc-pill ok">Habilitado</span>' : '<span class="doc-pill warn">Deshabilitado</span>'}</td>
        <td>${e.secciones.length ? Panel.esc(e.secciones.join(', ')) : '<span class="doc-pending">Todas</span>'}</td>
        <td>${ventana}</td>
        <td>${e.vinculos.length
          ? e.vinculos.map(v => `${Panel.esc(v.seccion)} · ${Panel.esc(v.nombre)} <small class="doc-muted">(${v.periodo}.º) → ${COMPONENTES[v.componente]}</small>`).join('<br>')
          : '<span class="doc-pill wait">Sin vincular</span>'}</td>
        <td>${e.enviados} enviados · ${e.en_curso} en curso${e.anulados ? ` · ${e.anulados} anulados` : ''}</td>
        <td class="doc-actions">
          <button class="btn btn-secondary" data-alternar="${e.codigo}">${e.habilitado ? 'Deshabilitar' : 'Habilitar'}</button>
          <button class="btn btn-secondary" data-config="${e.codigo}" aria-haspopup="dialog">Configurar…</button>
          ${e.en_curso ? `<button class="btn btn-secondary" data-cerrar="${e.codigo}" aria-haspopup="dialog">Cerrar y calificar los ${e.en_curso} en curso…</button>` : ''}
        </td>
      </tr>`;
    }).join('');
  }

  async function guardar(e, cambios) {
    await Panel.json(`/api/docente/examenes/${e.codigo}`, {
      method: 'PUT',
      // Sin «vinculos» en los cambios, el servidor deja los vínculos como están
      body: { habilitado: e.habilitado, desde: e.desde, hasta: e.hasta, secciones: e.secciones, ...cambios },
    });
    await cargar();
  }

  async function alternar(codigo) {
    const e = examenes.find(x => x.codigo === codigo);
    await guardar(e, { habilitado: !e.habilitado });
    Panel.toast(e.habilitado ? 'Examen deshabilitado: nadie nuevo puede iniciarlo' : 'Examen habilitado');
  }

  // Deshabilitar un examen no detiene a quienes ya lo iniciaron; esto los cierra a todos y los califica con lo guardado
  async function cerrarEnCurso(codigo) {
    const e = examenes.find(x => x.codigo === codigo);
    const ok = await Panel.confirmar(
      `Se cerrarán y calificarán con las respuestas que tengan guardadas los ${e.en_curso} intentos que siguen abiertos de ${e.codigo}. ` +
      'Los estudiantes que lo estén presentando ahora ya no podrán seguir ni enviarlo. Úsalo cuando termine el tiempo de la clase.',
      { titulo: `Cerrar ${e.codigo}`, texto: 'Cerrar y calificar', peligro: true });
    if (!ok) return;
    const r = await Panel.json(`/api/docente/examenes/${e.codigo}/cerrar-en-curso`, { method: 'POST' });
    await cargar();
    Panel.toast(`Se cerraron y calificaron ${r.cerrados} intentos de ${e.codigo}`);
  }

  // Período que sugiere el examen: el de sus vínculos o el que indica el sufijo del código (EMP02 → 2.º)
  function periodoSugerido(e, periodos, periodoActual) {
    if (e.vinculos.length) return e.vinculos[0].periodo;
    const sufijo = Number((e.codigo.match(/(\d\d)$/) || [])[1]);
    return periodos.includes(sufijo) ? sufijo : periodoActual;
  }

  async function configurar(codigo) {
    const e = examenes.find(x => x.codigo === codigo);
    const [{ materias }, { ajustes }] = await Promise.all([Panel.json('/api/docente/materias'), Panel.json('/api/docente/ajustes')]);
    const periodos = [...new Set(materias.map(m => m.periodo))].sort();
    let periodo = periodoSugerido(e, periodos, Number(ajustes.periodo_actual));
    const elegidas = new Map(e.vinculos.map(v => [v.materia_id, v.componente])); // materia_id -> componente
    const porDefecto = e.vinculos.length ? e.vinculos[0].componente : 'prueba02';

    const filasVinculos = () => {
      const grupos = {};
      materias.filter(m => m.periodo === periodo).forEach(m => { (grupos[m.seccion] = grupos[m.seccion] || []).push(m); });
      return Object.entries(grupos).map(([seccion, lista]) => `
        <fieldset class="doc-vinculos-grupo"><legend>${Panel.esc(seccion)}</legend>
          ${lista.map(m => `<div class="doc-vinculo-fila">
            <label><input type="checkbox" data-m="${m.id}" ${elegidas.has(m.id) ? 'checked' : ''}> ${Panel.esc(m.nombre)}</label>
            <select data-c="${m.id}" aria-label="Componente de ${Panel.esc(m.nombre)}" ${elegidas.has(m.id) ? '' : 'disabled'}>
              ${Object.entries(COMPONENTES).map(([k, t]) => `<option value="${k}" ${(elegidas.get(m.id) || porDefecto) === k ? 'selected' : ''}>${t}</option>`).join('')}
            </select></div>`).join('')}
        </fieldset>`).join('') || '<p class="doc-muted">No hay materias en este período.</p>';
    };
    const resumen = () => (elegidas.size
      ? `Vinculado a ${elegidas.size} materia${elegidas.size === 1 ? '' : 's'}.`
      : 'Sin vincular: sus notas no se pueden importar con un clic.');

    const promesa = Panel.dialogo({
      titulo: `Configurar ${e.codigo}`,
      cuerpo: `
        <p class="doc-muted">${Panel.esc(e.nombre)}. Los estudiantes que ya iniciaron pueden terminar aunque cambies esto.</p>
        <label class="doc-campo">Disponible desde <input type="datetime-local" id="c-desde" value="${aInputLocal(e.desde)}"></label>
        <label class="doc-campo">Disponible hasta (para iniciar) <input type="datetime-local" id="c-hasta" value="${aInputLocal(e.hasta)}"></label>
        <label class="doc-campo">Secciones permitidas (separadas por coma; vacío = todas)
          <input type="text" id="c-secciones" value="${Panel.esc(e.secciones.join(', '))}" placeholder="11-1, 11-2"></label>
        <h3>Importar su nota a Notas</h3>
        <p class="doc-muted">Marca las materias que usan este examen y en qué componente va. Cada materia importa solo a los estudiantes de su grupo.</p>
        <label class="doc-campo">Período
          <select id="c-periodo">${periodos.map(p => `<option value="${p}" ${p === periodo ? 'selected' : ''}>${p}.º período</option>`).join('')}</select></label>
        <div id="c-vinculos">${filasVinculos()}</div>
        <p class="doc-muted" id="c-resumen" aria-live="polite">${resumen()}</p>`,
      botones: [
        { texto: 'Cancelar', valor: null },
        { texto: 'Guardar', primario: true, valor: f => ({
          desde: deInputLocal(f.querySelector('#c-desde').value),
          hasta: deInputLocal(f.querySelector('#c-hasta').value),
          secciones: f.querySelector('#c-secciones').value.split(',').map(x => x.trim()).filter(Boolean),
          vinculos: [...elegidas].map(([materia_id, componente]) => ({ materia_id, componente })),
        }) },
      ],
    });
    // El diálogo ya está en pantalla: se conectan sus controles antes de esperar la respuesta
    const raiz = [...document.querySelectorAll('.doc-dialogo')].pop();
    raiz.querySelector('#c-periodo').addEventListener('change', ev => {
      periodo = Number(ev.target.value);
      raiz.querySelector('#c-vinculos').innerHTML = filasVinculos();
    });
    raiz.querySelector('#c-vinculos').addEventListener('change', ev => {
      const id = Number(ev.target.dataset.m || ev.target.dataset.c);
      const sel = raiz.querySelector(`select[data-c="${id}"]`);
      if (ev.target.dataset.m) {
        sel.disabled = !ev.target.checked;
        if (ev.target.checked) elegidas.set(id, sel.value); else elegidas.delete(id);
      } else if (elegidas.has(id)) {
        elegidas.set(id, ev.target.value);
      }
      raiz.querySelector('#c-resumen').textContent = resumen();
    });
    const datos = await promesa;
    if (!datos) return;
    await guardar(e, datos);
    Panel.toast('Configuración guardada');
  }

  Panel.registrar('examenes', 'Exámenes', {
    init(el) {
      el.innerHTML = `
        <p class="doc-muted">Controla qué exámenes pueden iniciar los estudiantes. Para agregar un examen nuevo, súbelo como JSON a <code>data/examenes/</code> y regístralo en <code>data/codigos.json</code>.</p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-examenes">
            <caption class="doc-solo-lectores">Exámenes disponibles</caption>
            <thead><tr>
              <th scope="col">Examen</th><th scope="col">Estado</th><th scope="col">Secciones</th>
              <th scope="col">Ventana para iniciar</th><th scope="col">Va a las notas de</th><th scope="col">Intentos</th><th scope="col">Acciones</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
      const run = (fn) => fn().catch(err => Panel.toast(err.message, 'error'));
      $('tabla-examenes').addEventListener('click', ev => {
        if (ev.target.dataset.alternar) run(() => alternar(ev.target.dataset.alternar));
        if (ev.target.dataset.config) run(() => configurar(ev.target.dataset.config));
        if (ev.target.dataset.cerrar) run(() => cerrarEnCurso(ev.target.dataset.cerrar));
      });
    },
    mostrar: cargar,
  });
})();
