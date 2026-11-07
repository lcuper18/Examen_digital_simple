// Pestaña Ajustes: datos institucionales, ponderaciones por materia y dirección de acceso
(function () {
  const CAMPOS = [
    ['institucion', 'Institución'], ['direccion_regional', 'Dirección Regional'], ['circuito', 'Circuito'],
    ['docente', 'Docente'], ['curso_lectivo', 'Curso lectivo'], ['nota_minima', 'Nota mínima de aprobación (0-100)'],
  ];
  let materias = [];
  let componentes = [];
  let etiquetas = {};

  async function cargarAjustes() {
    const { ajustes } = await Panel.json('/api/docente/ajustes');
    $('aj-campos').innerHTML = CAMPOS.map(([k, etiqueta]) => `
      <label class="doc-campo">${etiqueta}
        <input type="${k === 'nota_minima' ? 'number' : 'text'}" data-clave="${k}" value="${Panel.esc(ajustes[k])}"
          ${k === 'nota_minima' ? 'min="0" max="100" step="1"' : ''}></label>`).join('');
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
    const m = materias.find(x => String(x.id) === $('aj-materia').value);
    if (!m) return;
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
    const actual = $('aj-materia').value;
    $('aj-materia').innerHTML = materias.map(m =>
      `<option value="${m.id}">${Panel.esc(m.seccion)} · Periodo ${m.periodo} · ${Panel.esc(m.nombre)}</option>`).join('');
    if (actual) $('aj-materia').value = actual;
    dibujarPesos();
  }

  async function guardarPesos() {
    const id = $('aj-materia').value;
    const ponderaciones = Object.fromEntries([...document.querySelectorAll('#aj-pesos input')].map(i => [i.dataset.c, Number(i.value) || 0]));
    await Panel.json(`/api/docente/materias/${id}/ponderaciones`, { method: 'PUT', body: { ponderaciones } });
    Panel.toast('Ponderaciones guardadas');
    await cargarMaterias();
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
          <div class="doc-toolbar"><label>Materia <select id="aj-materia"></select></label></div>
          <div id="aj-pesos"></div>
          <p><span id="aj-suma" class="doc-pill"></span></p>
          <button class="btn btn-primary" id="btn-guardar-pesos">Guardar ponderación</button>
        </section>
        <section aria-labelledby="aj-t3">
          <h2 id="aj-t3">Dirección para los estudiantes</h2>
          <ul id="aj-red"></ul>
        </section>`;
      const run = (fn) => (...a) => fn(...a).catch(e => Panel.toast(e.message, 'error'));
      $('btn-guardar-ajustes').addEventListener('click', run(guardarAjustes));
      $('aj-materia').addEventListener('change', dibujarPesos);
      $('aj-pesos').addEventListener('input', sumarPesos);
      $('btn-guardar-pesos').addEventListener('click', run(guardarPesos));
    },
    async mostrar() {
      await Promise.all([cargarAjustes(), cargarMaterias(), cargarRed()]);
    },
  });
})();
