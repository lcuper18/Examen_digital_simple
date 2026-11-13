// Pestaña Ajustes: datos institucionales, ponderaciones por materia y dirección de acceso
(function () {
  const CAMPOS = [
    ['institucion', 'Institución'], ['direccion_regional', 'Dirección Regional'], ['circuito', 'Circuito'],
    ['docente', 'Docente (como aparece en las actas)'], ['curso_lectivo', 'Curso lectivo'], ['nota_minima', 'Nota mínima de aprobación (0-100)'],
    ['periodo_actual', 'Período actual'], ['umbral_ausencias', 'Avisar desde este % de ausencias injustificadas'],
  ];
  const AYUDAS = {
    nota_minima: 'Nota desde la cual el estudiante aprueba.',
    periodo_actual: 'Es el período que se vigila en «Estudiantes que necesitan atención» en el inicio.',
    umbral_ausencias: 'Con este porcentaje de ausencias sin justificar se muestra un aviso en el inicio.',
  };
  const NUMERICOS = ['nota_minima', 'periodo_actual', 'umbral_ausencias'];
  let materias = [];
  let componentes = [];
  let etiquetas = {};

  async function cargarAjustes() {
    const { ajustes } = await Panel.json('/api/docente/ajustes');
    $('aj-campos').innerHTML = CAMPOS.map(([k, etiqueta]) => `
      <label class="doc-campo">${etiqueta}${AYUDAS[k] ? Panel.ayuda(AYUDAS[k]) : ''}
        <input type="${NUMERICOS.includes(k) ? 'number' : 'text'}" data-clave="${k}" value="${Panel.esc(ajustes[k])}"
          ${NUMERICOS.includes(k) ? 'min="1" max="100" step="1"' : ''}></label>`).join('');
  }

  async function guardarAjustes() {
    const ajustes = Object.fromEntries([...document.querySelectorAll('#aj-campos input')].map(i => [i.dataset.clave, i.value]));
    await Panel.json('/api/docente/ajustes', { method: 'PUT', body: { ajustes } });
    Panel.toast('Ajustes guardados');
  }

  // ---------- Copia de respaldo externa ----------
  function pintarRespaldo(r) {
    const cuando = r.ultimo ? new Date(r.ultimo).toLocaleString('es-CR', { dateStyle: 'medium', timeStyle: 'short' }) : null;
    $('aj-resp-estado').innerHTML = !r.carpeta
      ? '<span class="doc-pill wait">Sin configurar</span> <span class="doc-muted">Hoy tus datos solo están en este computador.</span>'
      : r.error
        ? `<span class="doc-pill warn">Falló</span> ${Panel.esc(r.error)}`
        : `<span class="doc-pill ok">Activa</span> Última copia: <strong>${cuando ? Panel.esc(cuando) : 'todavía ninguna'}</strong>`;
    $('aj-resp-destino').textContent = r.carpeta ? `Se guarda en: ${r.destino}` : '';
    $('aj-resp-carpeta').value = r.carpeta || '';
    $('aj-resp-sug').innerHTML = r.sugerencias.length
      ? 'Sugerencias: ' + r.sugerencias.map(s => `<button type="button" class="btn btn-secondary" data-ruta="${Panel.esc(s.ruta)}">${Panel.esc(s.nombre)}</button>`).join(' ')
      : '<span class="doc-muted">No encontré iCloud Drive ni discos conectados; escribe la ruta de una carpeta.</span>';
    $('btn-resp-ahora').disabled = !r.carpeta;
    $('btn-resp-quitar').disabled = !r.carpeta;
  }

  async function cargarRespaldo() {
    pintarRespaldo(await Panel.json('/api/docente/respaldo'));
  }

  async function guardarRespaldo() {
    const r = await Panel.json('/api/docente/respaldo', { method: 'PUT', body: { carpeta: $('aj-resp-carpeta').value } });
    pintarRespaldo(r);
    if (r.copia.ok) Panel.toast('Carpeta guardada y primera copia hecha');
    else Panel.toast(r.copia.error || 'No se pudo hacer la copia', 'error');
  }

  async function respaldarAhora() {
    const r = await Panel.json('/api/docente/respaldo/ahora', { method: 'POST' });
    pintarRespaldo(r);
    if (r.copia.ok) Panel.toast('Copia externa hecha');
    else Panel.toast(r.copia.error || 'No se pudo hacer la copia', 'error');
  }

  async function quitarRespaldo() {
    const ok = await Panel.confirmar('Lectiva dejará de hacer la copia externa. Las copias que ya están en esa carpeta no se borran.',
      { titulo: 'Dejar de usar la copia externa', texto: 'Dejar de usar', peligro: true });
    if (!ok) return;
    pintarRespaldo((await Panel.json('/api/docente/respaldo', { method: 'PUT', body: { carpeta: '' } })));
    Panel.toast('Copia externa desactivada');
  }

  async function cargarRed() {
    const red = await Panel.json('/api/docente/red');
    $('aj-red').innerHTML = `
      <li>Con la dirección numérica: <strong>${red.url_ip ? Panel.esc(red.url_ip) : 'sin red'}</strong> <small class="doc-muted">(puede cambiar si el computador se reconecta al wifi)</small></li>
      ${red.url_nombre ? `<li>Con el nombre del computador: <strong>${Panel.esc(red.url_nombre)}</strong> <small class="doc-muted">(no cambia aunque cambie la IP; funciona en la mayoría de los celulares y computadoras)</small></li>` : ''}`;
  }

  function dibujarPesos() {
    const m = materias.find(x => x.id === Panel.contexto.id());
    if (!m) {
      $('aj-materia-txt').textContent = 'todavía no hay materias registradas';
      $('aj-pesos').innerHTML = '';
      $('aj-suma').textContent = '';
      $('btn-guardar-pesos').disabled = true;
      return;
    }
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
        <section aria-labelledby="aj-t6">
          <h2 id="aj-t6">Copia de respaldo externa</h2>
          <p class="doc-muted">Lectiva guarda tus datos en este computador. Una copia en otro lugar (iCloud Drive, un disco externo o una memoria USB)
            te protege si el computador se daña o se pierde. Se actualiza cada hora mientras Lectiva esté abierta y se conservan los últimos 30 días.</p>
          <p class="doc-muted"><strong>Contiene datos personales de tus estudiantes:</strong> elige un lugar privado.</p>
          <p id="aj-resp-estado" aria-live="polite"></p>
          <label class="doc-campo">Carpeta (ruta completa)
            <input type="text" id="aj-resp-carpeta" placeholder="/Volumes/MI-USB o la carpeta de iCloud Drive" autocomplete="off"></label>
          <p id="aj-resp-sug" class="doc-pills"></p>
          <p class="doc-muted" id="aj-resp-destino"></p>
          <div class="doc-actions-fila">
            <button class="btn btn-primary" id="btn-resp-guardar">Guardar y respaldar ahora</button>
            <button class="btn btn-secondary" id="btn-resp-ahora">Respaldar ahora</button>
            <button class="btn btn-secondary" id="btn-resp-quitar">Dejar de usar</button>
          </div>
        </section>
        <section aria-labelledby="aj-t5">
          <h2 id="aj-t5">Contraseña del docente</h2>
          <p class="doc-muted">Protege el panel docente. Cámbiala si alguien más la conoce; se guarda cifrada en este computador.</p>
          <button class="btn btn-secondary" id="btn-cambiar-clave">Cambiar contraseña…</button>
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
      $('btn-cambiar-clave').addEventListener('click', run(Panel.cambiarClaveDocente));
      $('btn-resp-guardar').addEventListener('click', run(() => Panel.conCarga($('btn-resp-guardar'), guardarRespaldo, 'Copiando…')));
      $('btn-resp-ahora').addEventListener('click', run(() => Panel.conCarga($('btn-resp-ahora'), respaldarAhora, 'Copiando…')));
      $('btn-resp-quitar').addEventListener('click', run(quitarRespaldo));
      $('aj-resp-sug').addEventListener('click', e => { if (e.target.dataset.ruta) $('aj-resp-carpeta').value = e.target.dataset.ruta; });
      $('btn-cerrar-curso').addEventListener('click', run(cerrarCurso));
    },
    usaContexto: true,
    contextoOpcional: true, // los datos de la institución, la contraseña y la copia de respaldo no dependen de una materia
    async mostrar() {
      await Promise.all([cargarAjustes(), cargarMaterias(), cargarRed(), cargarCierre(), cargarRespaldo()]);
    },
  });
})();
