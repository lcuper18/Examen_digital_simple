// Pestaña Bitácora: registro de acciones del docente
(function () {
  const ETIQUETAS = {
    reiniciar_password: 'Reinició contraseña', reiniciar_seccion: 'Reinició contraseñas de sección',
    desbloquear_login: 'Desbloqueó login', activar_cuenta: 'Activó cuenta', desactivar_cuenta: 'Desactivó cuenta',
    cambiar_seccion: 'Cambió de sección', crear_estudiante: 'Creó estudiante', eliminar_estudiante: 'Eliminó estudiante',
    importar_estudiantes: 'Importó estudiantes',
  };

  async function cargar() {
    const { entradas } = await Panel.json('/api/docente/bitacora?limite=300');
    $('tabla-bitacora').querySelector('tbody').innerHTML = entradas.map(e => `<tr>
      <td>${Panel.formatoFecha(e.fecha)}</td>
      <td>${Panel.esc(ETIQUETAS[e.accion] || e.accion.replace(/_/g, ' '))}</td>
      <td>${Panel.esc(e.detalle)}</td></tr>`).join('') || '<tr><td colspan="3" class="doc-pending">Sin registros</td></tr>';
  }

  Panel.registrar('bitacora', 'Bitácora', {
    init(el) {
      el.innerHTML = `
        <p class="doc-muted">Últimas acciones realizadas desde este panel.</p>
        <div class="doc-table-wrap">
          <table class="doc-table" id="tabla-bitacora">
            <caption class="doc-solo-lectores">Bitácora de acciones</caption>
            <thead><tr><th scope="col">Fecha</th><th scope="col">Acción</th><th scope="col">Detalle</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
    },
    mostrar: cargar,
  });
})();
