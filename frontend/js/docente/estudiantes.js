// Pestaña Estudiantes: cuentas, contraseñas temporales, altas, bajas e importación
(function () {
  let estudiantes = [];
  let ordenar = (l) => l;
  const orden = { clave: 'nombre', dir: 1 };

  async function cargar() {
    const seccion = $('e-seccion').value;
    const q = $('e-buscar').value.trim();
    const params = new URLSearchParams();
    if (seccion) params.set('seccion', seccion);
    if (q) params.set('q', q);
    const todos = (await Panel.json('/api/docente/estudiantes')).estudiantes;
    llenarSecciones(todos);
    estudiantes = (await Panel.json(`/api/docente/estudiantes?${params}`)).estudiantes;
    render();
  }

  function llenarSecciones(todos) {
    const select = $('e-seccion');
    const actual = select.value;
    const secciones = [...new Set(todos.map(e => e.seccion))].sort();
    select.innerHTML = '<option value="">Todas</option>' + secciones.map(s => `<option>${Panel.esc(s)}</option>`).join('');
    select.value = secciones.includes(actual) ? actual : '';
  }

  function render() {
    $('e-resumen').textContent = `${estudiantes.length} estudiantes · ${estudiantes.filter(e => !e.activo).length} desactivados · ` +
      `${estudiantes.filter(e => e.debe_cambiar_password).length} con clave temporal pendiente`;
    $('tabla-estudiantes').querySelector('tbody').innerHTML = ordenar(estudiantes).map(e => {
      const pills = [
        e.activo ? '<span class="doc-pill ok">Activo</span>' : '<span class="doc-pill warn">Desactivado</span>',
        e.debe_cambiar_password ? '<span class="doc-pill wait">Clave temporal</span>' : '',
        e.bloqueado ? '<span class="doc-pill warn">Bloqueado</span>' : '',
      ].join(' ');
      return `<tr>
        <th scope="row">${Panel.esc(Panel.nombre(e))}</th>
        <td>${Panel.esc(e.username)}</td>
        <td>${Panel.esc(e.seccion)}</td>
        <td>${pills}</td>
        <td>${Panel.formatoFecha(e.ultimo_acceso)}</td>
        <td>${e.enviados}</td>
        <td class="doc-actions">
          <button class="btn btn-secondary" data-reiniciar="${e.id}">Reiniciar clave</button>
          <button class="btn btn-secondary" data-mas="${e.id}" aria-haspopup="dialog">Más…</button>
        </td>
      </tr>`;
    }).join('') || '<tr><td colspan="7" class="doc-pending">Sin estudiantes</td></tr>';
  }

  function mostrarClave(titulo, nombre, username, clave) {
    return Panel.dialogo({
      titulo,
      cuerpo: `<p>${Panel.esc(nombre)} · usuario <strong>${Panel.esc(username)}</strong></p>
        <p class="doc-clave" id="dlg-clave">${Panel.esc(clave)}</p>
        <button type="button" class="btn btn-secondary" data-copiar="${Panel.esc(clave)}">Copiar</button>
        <p class="doc-muted">Se muestra <strong>una sola vez</strong>. El estudiante deberá crear su propia contraseña al entrar.</p>`,
      botones: [{ texto: 'Listo', primario: true, valor: true }],
    });
  }

  function hojaCredenciales(titulo, filas) {
    return Panel.dialogo({
      titulo,
      ancho: 'ancho imprimible',
      cuerpo: `<p class="doc-muted">Cada estudiante debe cambiar esta contraseña al iniciar sesión por primera vez.
        Entrega cada fila por separado y no conserves esta hoja.</p>
        <table class="doc-table"><thead><tr><th scope="col">Estudiante</th><th scope="col">Sección</th><th scope="col">Usuario</th><th scope="col">Contraseña temporal</th></tr></thead>
        <tbody>${filas.map(f => `<tr><td>${Panel.esc(f.nombre)}</td><td>${Panel.esc(f.seccion || '')}</td>
          <td>${Panel.esc(f.username)}</td><td class="doc-clave-mini">${Panel.esc(f.password_temporal)}</td></tr>`).join('')}</tbody></table>`,
      botones: [{ texto: 'Imprimir', valor: 'imprimir', primario: true }, { texto: 'Cerrar', valor: null }],
    }).then(v => { if (v === 'imprimir') { const nueva = hojaCredenciales(titulo, filas); window.print(); return nueva; } });
  }

  async function reiniciarClave(id) {
    const e = estudiantes.find(x => x.id === id);
    const ok = await Panel.confirmar(
      `Se generará una contraseña temporal para ${Panel.nombre(e)}. La anterior dejará de funcionar.`,
      { titulo: 'Reiniciar contraseña', texto: 'Reiniciar', peligro: true });
    if (!ok) return;
    const r = await Panel.json(`/api/docente/estudiantes/${id}/reiniciar-password`, { method: 'POST' });
    await cargar();
    await mostrarClave('Contraseña temporal', Panel.nombre(e), r.username, r.password_temporal);
  }

  async function mas(id) {
    const e = estudiantes.find(x => x.id === id);
    const accion = await Panel.dialogo({
      titulo: Panel.nombre(e),
      cuerpo: '<p class="doc-muted">Elige una acción:</p>',
      botones: [
        ...(e.bloqueado ? [{ texto: 'Desbloquear login', valor: 'desbloquear' }] : []),
        { texto: e.activo ? 'Desactivar cuenta' : 'Activar cuenta', valor: 'activo' },
        { texto: 'Cambiar sección', valor: 'seccion' },
        { texto: 'Eliminar', valor: 'eliminar' },
        { texto: 'Cancelar', valor: null },
      ],
    });
    if (accion === 'desbloquear') {
      await Panel.json(`/api/docente/estudiantes/${id}/desbloquear`, { method: 'POST' });
      Panel.toast('Login desbloqueado');
    } else if (accion === 'activo') {
      await Panel.json(`/api/docente/estudiantes/${id}`, { method: 'PATCH', body: { activo: !e.activo } });
      Panel.toast(e.activo ? 'Cuenta desactivada' : 'Cuenta activada');
    } else if (accion === 'seccion') {
      const nueva = await Panel.pedir('Nueva sección (ej. 11-1)', e.seccion, { titulo: 'Cambiar sección' });
      if (!nueva) return;
      await Panel.json(`/api/docente/estudiantes/${id}`, { method: 'PATCH', body: { seccion: nueva } });
      Panel.toast('Sección actualizada');
    } else if (accion === 'eliminar') {
      if (!(await Panel.confirmar(`¿Eliminar a ${Panel.nombre(e)}? Solo es posible si no tiene intentos de examen.`,
        { titulo: 'Eliminar estudiante', texto: 'Eliminar', peligro: true }))) return;
      await Panel.json(`/api/docente/estudiantes/${id}`, { method: 'DELETE' });
      Panel.toast('Estudiante eliminado');
    } else {
      return;
    }
    await cargar();
  }

  async function nuevo() {
    const datos = await Panel.dialogo({
      titulo: 'Nuevo estudiante',
      cuerpo: `
        <label class="doc-campo">Cédula <input id="n-cedula" autocomplete="off"></label>
        <label class="doc-campo">Nombre(s) <input id="n-nombre" autocomplete="off"></label>
        <label class="doc-campo">Primer apellido <input id="n-ap1" autocomplete="off"></label>
        <label class="doc-campo">Segundo apellido <input id="n-ap2" autocomplete="off"></label>
        <label class="doc-campo">Sección <input id="n-seccion" placeholder="11-1" autocomplete="off"></label>`,
      botones: [
        { texto: 'Cancelar', valor: null },
        { texto: 'Crear', primario: true, valor: f => ({
          cedula: f.querySelector('#n-cedula').value, nombre: f.querySelector('#n-nombre').value,
          apellido1: f.querySelector('#n-ap1').value, apellido2: f.querySelector('#n-ap2').value,
          seccion: f.querySelector('#n-seccion').value,
        }) },
      ],
    });
    if (!datos) return;
    const r = await Panel.json('/api/docente/estudiantes', { method: 'POST', body: datos });
    await cargar();
    await mostrarClave('Estudiante creado', `${datos.nombre} ${datos.apellido1}`, r.username, r.password_temporal);
  }

  async function importar() {
    const texto = await Panel.dialogo({
      titulo: 'Importar estudiantes (CSV)',
      cuerpo: `<p class="doc-muted">Columnas: <code>cedula,nombre,apellido1,apellido2,seccion</code>. Los repetidos se omiten.</p>
        <label class="doc-campo">Archivo CSV <input type="file" id="imp-archivo" accept=".csv,text/csv"></label>
        <label class="doc-campo">…o pega el contenido <textarea id="imp-texto" rows="6"></textarea></label>`,
      botones: [
        { texto: 'Cancelar', valor: null },
        { texto: 'Importar', primario: true, valor: f => f.querySelector('#imp-texto').value.trim() || null },
      ],
    });
    if (!texto) return;
    const r = await Panel.json('/api/docente/estudiantes/importar', { method: 'POST', body: { csv: texto } });
    await cargar();
    Panel.toast(`${r.creados.length} creados, ${r.omitidos.length} omitidos`);
    if (r.creados.length) await hojaCredenciales('Credenciales de estudiantes importados', r.creados);
  }

  async function credencialesSeccion() {
    const seccion = $('e-seccion').value;
    if (!seccion) return Panel.toast('Elige primero una sección en el filtro', 'error');
    const ok = await Panel.confirmar(
      `Se reiniciará la contraseña de todos los estudiantes activos de ${seccion} y se generará una hoja imprimible.`,
      { titulo: 'Credenciales de sección', texto: 'Generar', peligro: true });
    if (!ok) return;
    const r = await Panel.json('/api/docente/estudiantes/reiniciar-seccion', { method: 'POST', body: { seccion } });
    await cargar();
    await hojaCredenciales(`Credenciales · sección ${seccion}`, r.credenciales.map(c => ({ ...c, seccion })));
  }

  Panel.registrar('estudiantes', 'Estudiantes', {
    init(el) {
      el.innerHTML = `
        <div class="doc-toolbar">
          <label>Buscar <input type="search" id="e-buscar" placeholder="Nombre, usuario o cédula"></label>
          <label>Sección <select id="e-seccion"></select></label>
          <button class="btn btn-primary" id="e-nuevo">Nuevo estudiante</button>
          <button class="btn btn-secondary" id="e-importar">Importar CSV</button>
          <button class="btn btn-secondary" id="e-credenciales">Credenciales de sección</button>
        </div>
        <p id="e-resumen" class="doc-muted" aria-live="polite"></p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-estudiantes">
            <caption class="doc-solo-lectores">Estudiantes</caption>
            <thead><tr>
              ${Panel.th('nombre', 'Estudiante')}${Panel.th('usuario', 'Usuario')}${Panel.th('seccion', 'Sección')}
              <th scope="col">Estado</th>${Panel.th('acceso', 'Último acceso')}${Panel.th('enviados', 'Enviados')}<th scope="col">Acciones</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
      ordenar = Panel.ordenable($('tabla-estudiantes'), {
        nombre: e => Panel.nombre(e), usuario: e => e.username, seccion: e => e.seccion,
        acceso: e => e.ultimo_acceso, enviados: e => e.enviados,
      }, orden, render);
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      let espera;
      $('e-buscar').addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(run(cargar), 250); });
      $('e-seccion').addEventListener('change', run(cargar));
      $('e-nuevo').addEventListener('click', run(nuevo));
      $('e-importar').addEventListener('click', run(importar));
      $('e-credenciales').addEventListener('click', run(credencialesSeccion));
      $('tabla-estudiantes').addEventListener('click', e => {
        if (e.target.dataset.reiniciar) run(reiniciarClave)(Number(e.target.dataset.reiniciar));
        if (e.target.dataset.mas) run(mas)(Number(e.target.dataset.mas));
      });
      // Copiar al portapapeles y cargar CSV desde archivo (elementos dentro de diálogos)
      document.addEventListener('click', e => {
        if (e.target.dataset && e.target.dataset.copiar) {
          navigator.clipboard.writeText(e.target.dataset.copiar).then(() => Panel.toast('Copiada'));
        }
      });
      document.addEventListener('change', e => {
        if (e.target.id === 'imp-archivo' && e.target.files[0]) {
          e.target.files[0].text().then(t => { $('imp-texto').value = t; });
        }
      });
    },
    mostrar: cargar,
  });
})();
