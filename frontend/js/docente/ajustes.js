// Pestaña Ajustes: datos institucionales, ponderaciones por materia y dirección de acceso
(function () {
  const CAMPOS = [
    ['institucion', 'Institución'], ['direccion_regional', 'Dirección Regional'], ['circuito', 'Circuito'],
    ['docente', 'Docente (como aparece en las actas)'], ['curso_lectivo', 'Curso lectivo'], ['nota_minima', 'Nota mínima de aprobación (0-100)'],
    ['periodo_actual', 'Período actual (para las alertas del Resumen)'], ['umbral_ausencias', 'Alerta de asistencia desde (% de ausencias injustificadas)'],
  ];
  const NUMERICOS = ['nota_minima', 'periodo_actual', 'umbral_ausencias'];
  let materias = [];
  let componentes = [];
  let etiquetas = {};

  async function cargarAjustes() {
    const { ajustes } = await Panel.json('/api/docente/ajustes');
    $('aj-campos').innerHTML = CAMPOS.map(([k, etiqueta]) => `
      <label class="doc-campo">${etiqueta}
        <input type="${NUMERICOS.includes(k) ? 'number' : 'text'}" data-clave="${k}" value="${Panel.esc(ajustes[k])}"
          ${NUMERICOS.includes(k) ? 'min="1" max="100" step="1"' : ''}></label>`).join('');
  }

  async function guardarAjustes() {
    const ajustes = Object.fromEntries([...document.querySelectorAll('#aj-campos input')].map(i => [i.dataset.clave, i.value]));
    await Panel.json('/api/docente/ajustes', { method: 'PUT', body: { ajustes } });
    Panel.toast('Ajustes guardados');
  }

  async function cargarRed() {
    const red = await Panel.json('/api/docente/red');
    $('aj-red').innerHTML = `
      <li>Por IP: <strong>${red.url_ip ? Panel.esc(red.url_ip) : 'sin red'}</strong> <small class="doc-muted">(puede cambiar si la Mac se reconecta)</small></li>
      ${red.url_nombre ? `<li>Por nombre: <strong>${Panel.esc(red.url_nombre)}</strong> <small class="doc-muted">(no cambia aunque cambie la IP; funciona en la mayoría de los celulares y computadoras)</small></li>` : ''}`;
  }

  function dibujarPesos() {
    const m = materias.find(x => x.id === Panel.contexto.id());
    if (!m) return;
    $('aj-materia-txt').textContent = `${m.seccion} · ${m.periodo}.º período · ${m.nombre}`;
    $('aj-pesos').innerHTML = componentes.map(c => `
      <label class="doc-campo">${etiquetas[c]} (puntos)
        <input type="number" min="0" max="100" step="0.5" data-c="${c}" value="${m.ponderaciones[c]}"></label>`).join('');
    sumarPesos();
  }

  function sumarPesos() {
    const total = [...document.querySelectorAll('#aj-pesos input')].reduce((s, i) => s + (Number(i.value) || 0), 0);
    const ok = Math.abs(total - 100) < 0.001;
    $('aj-suma').textContent = `Suma: ${Math.round(total * 100) / 100} de 100`;
    $('aj-suma').className = ok ? 'doc-pill ok' : 'doc-pill warn';
    $('btn-guardar-pesos').disabled = !ok;
  }

  async function cargarMaterias() {
    const data = await Panel.json('/api/docente/materias');
    materias = data.materias;
    componentes = data.componentes;
    etiquetas = data.etiquetas;
    dibujarPesos();
  }

  async function guardarPesos() {
    const id = Panel.contexto.id();
    const ponderaciones = Object.fromEntries([...document.querySelectorAll('#aj-pesos input')].map(i => [i.dataset.c, Number(i.value) || 0]));
    await Panel.json(`/api/docente/materias/${id}/ponderaciones`, { method: 'PUT', body: { ponderaciones } });
    Panel.toast('Ponderaciones guardadas');
    await cargarMaterias();
  }

  async function cargarCierre() {
    const [est, arch, aj] = await Promise.all([
      Panel.json('/api/docente/estudiantes'), Panel.json('/api/docente/cierre/archivos'), Panel.json('/api/docente/ajustes')]);
    const secciones = [...new Set(est.estudiantes.map(e => e.seccion))].sort();
    $('aj-cierre-secciones').innerHTML = secciones.map(s =>
      `<label><input type="checkbox" value="${Panel.esc(s)}"> ${Panel.esc(s)}</label>`).join(' ');
    $('aj-nuevo-curso').value = String(Number(aj.ajustes.curso_lectivo) + 1 || '');
    $('aj-archivos').innerHTML = arch.archivos.length
      ? arch.archivos.map(a => `<li>${Panel.esc(a)}</li>`).join('') + `<li class="doc-muted">Carpeta: ${Panel.esc(arch.carpeta)}</li>`
      : '<li class="doc-pending">Aún no se ha cerrado ningún curso.</li>';
  }

  async function cerrarCurso() {
    const nuevo = $('aj-nuevo-curso').value.trim();
    const secciones = [...document.querySelectorAll('#aj-cierre-secciones input:checked')].map(i => i.value);
    if (!nuevo) return Panel.toast('Indica el nuevo curso lectivo', 'error');
    if ($('aj-cierre-confirmar').value.trim().toUpperCase() !== 'CERRAR') return Panel.toast('Escribe CERRAR para confirmar', 'error');
    const ok = await Panel.confirmar(
      `Se guardará una copia completa del curso actual y se borrarán notas, asistencia, actividades, exámenes presentados y observaciones` +
      `${secciones.length ? `; se desactivarán los estudiantes de ${secciones.join(', ')}` : ''}. Empieza el curso ${nuevo}.`,
      { titulo: 'Cerrar el curso lectivo', texto: 'Cerrar curso', peligro: true });
    if (!ok) return;
    const r = await Panel.json('/api/docente/cierre', { method: 'POST', body: {
      confirmacion: 'CERRAR', nuevo_curso: nuevo, desactivar_secciones: secciones } });
    $('aj-cierre-confirmar').value = '';
    Panel.toast(`Curso cerrado. Copia: ${r.copia}`);
    await Promise.all([cargarAjustes(), cargarCierre()]);
  }

  Panel.registrar('ajustes', 'Ajustes', {
    init(el) {
      el.innerHTML = `
        <section aria-labelledby="aj-t1">
          <h2 id="aj-t1">Datos de la institución</h2>
          <p class="doc-muted">Aparecen en los reportes, las actas y los informes.</p>
          <div id="aj-campos"></div>
          <button class="btn btn-primary" id="btn-guardar-ajustes">Guardar ajustes</button>
        </section>
        <section aria-labelledby="aj-t2">
          <h2 id="aj-t2">Ponderación por materia</h2>
          <p class="doc-muted">Puntos que vale cada componente en la nota final. Deben sumar 100.</p>
          <p class="doc-muted">Materia elegida arriba: <strong id="aj-materia-txt"></strong>. Cámbiala con el selector de la parte superior.</p>
          <div id="aj-pesos"></div>
          <p><span id="aj-suma" class="doc-pill"></span></p>
          <button class="btn btn-primary" id="btn-guardar-pesos">Guardar ponderación</button>
        </section>
        <section aria-labelledby="aj-t4">
          <h2 id="aj-t4">Cierre del curso lectivo</h2>
          <p class="doc-muted">Guarda una copia completa de la base y un Excel con las notas finales, y deja el sistema limpio para el siguiente curso.
            Se conservan los estudiantes, las materias, las ponderaciones y los exámenes. Se borran notas, asistencia, actividades, exámenes presentados y observaciones.</p>
          <label class="doc-campo">Nuevo curso lectivo <input type="text" id="aj-nuevo-curso" maxlength="9"></label>
          <div class="doc-campo">Desactivar estudiantes de estas secciones (por ejemplo, las que egresan)<div id="aj-cierre-secciones"></div></div>
          <label class="doc-campo">Escribe CERRAR para confirmar <input type="text" id="aj-cierre-confirmar" autocomplete="off"></label>
          <button class="btn btn-secondary" id="btn-cerrar-curso">Cerrar curso lectivo…</button>
          <h3>Cierres anteriores</h3><ul id="aj-archivos" class="doc-lista"></ul>
        </section>
        <section aria-labelledby="aj-t3">
          <h2 id="aj-t3">Dirección para los estudiantes</h2>
          <ul id="aj-red"></ul>
        </section>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('btn-guardar-ajustes').addEventListener('click', run(guardarAjustes));
      $('aj-pesos').addEventListener('input', sumarPesos);
      $('btn-guardar-pesos').addEventListener('click', run(guardarPesos));
      $('btn-cerrar-curso').addEventListener('click', run(cerrarCurso));
    },
    usaContexto: true,
    async mostrar() {
      await Promise.all([cargarAjustes(), cargarMaterias(), cargarRed(), cargarCierre()]);
    },
  });
})();
