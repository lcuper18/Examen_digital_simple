// Pestaña Bitácora: registro de acciones del docente, con búsqueda, filtro por acción y paginación
(function () {
  let entradas = [];
  let paginas;
  const POR_PAGINA = 25;

  function render() {
    const accion = $('b-accion').value;
    const buscar = $('b-buscar').value;
    const lista = entradas.filter(e =>
      (!accion || e.accion === accion) &&
      (!buscar.trim() || Panel.coincide(`${Panel.frase(e.accion)} ${e.detalle || ''}`, buscar)));
    $('b-resumen').textContent = entradas.length
      ? `${lista.length} de ${entradas.length} registros${entradas.length >= 1000 ? ' (los 1000 más recientes)' : ''}`
      : '';
    $('tabla-bitacora').querySelector('tbody').innerHTML = paginas.cortar(lista).map(e => `<tr>
      <td>${Panel.formatoFecha(e.fecha)}</td>
      <td>${Panel.esc(Panel.frase(e.accion))}</td>
      <td>${Panel.esc(e.detalle)}</td></tr>`).join('') ||
      `<tr><td colspan="3" class="doc-pending">${entradas.length ? 'Sin registros con ese filtro.' : 'Todavía no hay registros.'}</td></tr>`;
  }

  async function cargar() {
    entradas = (await Panel.json(`/api/docente/bitacora?limite=${$('b-limite').value}`)).entradas;
    const actual = $('b-accion').value;
    const acciones = [...new Set(entradas.map(e => e.accion))].sort((a, b) => Panel.frase(a).localeCompare(Panel.frase(b), 'es'));
    $('b-accion').innerHTML = '<option value="">Todas</option>' +
      acciones.map(a => `<option value="${Panel.esc(a)}">${Panel.esc(Panel.frase(a))}</option>`).join('');
    $('b-accion').value = acciones.includes(actual) ? actual : '';
    paginas.reiniciar();
    render();
  }

  Panel.registrar('bitacora', 'Bitácora', {
    init(el) {
      el.innerHTML = `
        <p class="doc-muted">Acciones realizadas desde este panel (nunca se guardan contraseñas).</p>
        <div class="doc-toolbar">
          <label>Buscar <input type="search" id="b-buscar" placeholder="Estudiante, materia, examen…" autocomplete="off"></label>
          <label>Acción <select id="b-accion"><option value="">Todas</option></select></label>
          <label>Mostrar <select id="b-limite">
            <option value="100">Últimos 100</option><option value="300" selected>Últimos 300</option><option value="1000">Últimos 1000</option></select></label>
          <button class="btn btn-secondary" id="b-actualizar">Actualizar</button>
        </div>
        <p id="b-resumen" class="doc-muted" aria-live="polite"></p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-bitacora">
            <caption class="doc-solo-lectores">Bitácora de acciones</caption>
            <thead><tr><th scope="col">Fecha</th><th scope="col">Acción</th><th scope="col">Detalle</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <nav id="pag-bitacora" class="doc-paginacion" hidden></nav>`;
      paginas = Panel.paginador($('pag-bitacora'), POR_PAGINA, render);
      const filtrar = () => { paginas.reiniciar(); render(); };
      $('b-buscar').addEventListener('input', filtrar);
      $('b-accion').addEventListener('change', filtrar);
      const recargar = () => cargar().catch(e => Panel.toast(e.message, 'error'));
      $('b-limite').addEventListener('change', recargar);
      $('b-actualizar').addEventListener('click', recargar);
    },
    mostrar: cargar,
  });
})();
