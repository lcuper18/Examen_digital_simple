// Pestaña Exámenes: habilitar, programar y restringir por sección
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
        <td>${e.enviados} enviados · ${e.en_curso} en curso${e.anulados ? ` · ${e.anulados} anulados` : ''}</td>
        <td class="doc-actions">
          <button class="btn btn-secondary" data-alternar="${e.codigo}">${e.habilitado ? 'Deshabilitar' : 'Habilitar'}</button>
          <button class="btn btn-secondary" data-config="${e.codigo}" aria-haspopup="dialog">Configurar…</button>
        </td>
      </tr>`;
    }).join('');
  }

  async function guardar(e, cambios) {
    await Panel.json(`/api/docente/examenes/${e.codigo}`, {
      method: 'PUT',
      body: { habilitado: e.habilitado, desde: e.desde, hasta: e.hasta, secciones: e.secciones, ...cambios },
    });
    await cargar();
  }

  async function alternar(codigo) {
    const e = examenes.find(x => x.codigo === codigo);
    await guardar(e, { habilitado: !e.habilitado });
    Panel.toast(e.habilitado ? 'Examen deshabilitado: nadie nuevo puede iniciarlo' : 'Examen habilitado');
  }

  async function configurar(codigo) {
    const e = examenes.find(x => x.codigo === codigo);
    const datos = await Panel.dialogo({
      titulo: `Configurar ${e.codigo}`,
      cuerpo: `
        <p class="doc-muted">${Panel.esc(e.nombre)}. Los estudiantes que ya iniciaron pueden terminar aunque cambies esto.</p>
        <label class="doc-campo">Disponible desde <input type="datetime-local" id="c-desde" value="${aInputLocal(e.desde)}"></label>
        <label class="doc-campo">Disponible hasta (para iniciar) <input type="datetime-local" id="c-hasta" value="${aInputLocal(e.hasta)}"></label>
        <label class="doc-campo">Secciones permitidas (separadas por coma; vacío = todas)
          <input type="text" id="c-secciones" value="${Panel.esc(e.secciones.join(', '))}" placeholder="11-1, 11-2"></label>`,
      botones: [
        { texto: 'Cancelar', valor: null },
        { texto: 'Guardar', primario: true, valor: f => ({
          desde: deInputLocal(f.querySelector('#c-desde').value),
          hasta: deInputLocal(f.querySelector('#c-hasta').value),
          secciones: f.querySelector('#c-secciones').value.split(',').map(x => x.trim()).filter(Boolean),
        }) },
      ],
    });
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
              <th scope="col">Ventana para iniciar</th><th scope="col">Intentos</th><th scope="col">Acciones</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
      const run = (fn) => fn().catch(err => Panel.toast(err.message, 'error'));
      $('tabla-examenes').addEventListener('click', ev => {
        if (ev.target.dataset.alternar) run(() => alternar(ev.target.dataset.alternar));
        if (ev.target.dataset.config) run(() => configurar(ev.target.dataset.config));
      });
    },
    mostrar: cargar,
  });
})();
