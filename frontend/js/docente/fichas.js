// Ficha del estudiante: datos del encargado, adecuación, observaciones, historial y alertas
(function () {
  const num = (n, d = 1) => (n === null || n === undefined ? '—' : String(Math.round(n * 10 ** d) / 10 ** d));
  const fecha = (iso) => (iso ? iso.split('T')[0].split('-').reverse().join('/') : '—');
  const hoyIso = () => { const d = new Date(), p = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; };

  const campo = (id, etiqueta, valor, tipo = 'text') =>
    `<label class="doc-campo">${etiqueta}<input type="${tipo}" id="${id}" value="${Panel.esc(valor)}"></label>`;

  function htmlHistorial(d) {
    const filas = d.materias.map(m => {
      const a = m.asistencia;
      const pend = m.actividades.filter(x => x.estado === 'sin_entrega').length;
      return `<tr><td>${Panel.esc(m.materia)}</td><td class="num">${m.periodo}</td>
        <td class="num ${m.aprobado ? '' : 'low'}">${num(m.nota_final)}${m.completa ? '' : '*'}</td>
        <td>${a ? `${num(a.porcentaje)} % ausencias · ${a.puntos}/${a.maximo}` : '—'}</td><td class="num">${pend || ''}</td></tr>`;
    }).join('');
    const examenes = d.examenes.length ? `<p class="doc-muted">Exámenes presentados: ${d.examenes.map(x =>
      `${Panel.esc(x.codigo)} ${num(x.puntuacion / x.total * 100)}`).join(' · ')}</p>` : '';
    return `<table class="doc-table"><caption class="doc-solo-lectores">Historial por materia</caption>
      <thead><tr><th scope="col">Materia</th><th scope="col">Per.</th><th scope="col">Nota</th><th scope="col">Asistencia</th><th scope="col">Sin entrega</th></tr></thead>
      <tbody>${filas}</tbody></table><p class="doc-muted">* nota parcial</p>${examenes}`;
  }

  function htmlObservaciones(d) {
    return d.observaciones.length ? `<ul class="doc-lista">${d.observaciones.map(o => `<li>
      <small class="doc-muted">${fecha(o.fecha)} · ${Panel.esc(d.tipos[o.tipo] || o.tipo)}${o.materia ? ' · ' + Panel.esc(o.materia) : ''}</small><br>
      ${Panel.esc(o.texto)} <button type="button" class="doc-enlace" data-borrar-obs="${o.id}">Eliminar</button></li>`).join('')}</ul>`
      : '<p class="doc-pending">Sin observaciones.</p>';
  }

  Panel.abrirFicha = async function (id) {
    let d = await Panel.json(`/api/docente/estudiantes/${id}/ficha`);
    const e = d.estudiante;
    const alertas = d.alertas.length
      ? `<ul class="doc-lista">${d.alertas.map(a => `<li><span class="doc-pill ${a.severidad === 'alta' ? 'warn' : 'wait'}">${Panel.esc(a.tipo)}</span>
          ${Panel.esc(a.materia)}: ${Panel.esc(a.detalle)}</li>`).join('')}</ul>` : '<p class="doc-pending">Sin alertas en el período actual.</p>';
    const resultado = Panel.dialogo({
      titulo: `${e.nombre} · ${e.seccion}`, ancho: 'doc-dialogo-ancho',
      cuerpo: `
        <p class="doc-muted">Cédula ${Panel.esc(e.cedula)}${e.activo ? '' : ' · desactivado'}</p>
        <h3>Alertas</h3>${alertas}
        <h3>Datos de contacto y adecuación</h3>
        ${campo('f-tel', 'Teléfono del estudiante', e.telefono)}
        ${campo('f-enc', 'Encargado (apellidos y nombre)', e.encargado_nombre)}
        ${campo('f-encced', 'Cédula del encargado', e.encargado_cedula)}
        ${campo('f-t1', 'Teléfono 1 del encargado', e.encargado_telefono)}
        ${campo('f-t2', 'Teléfono 2 del encargado', e.encargado_telefono2)}
        ${campo('f-dir', 'Dirección', e.direccion)}
        <label class="doc-campo"><span><input type="checkbox" id="f-ad" ${e.adecuacion ? 'checked' : ''}> Cuenta con adecuación o apoyo educativo</span></label>
        ${campo('f-addet', 'Detalle de la adecuación', e.adecuacion_detalle)}
        <h3>Historial</h3>${htmlHistorial(d)}
        <h3>Observaciones</h3><div id="f-obs">${htmlObservaciones(d)}</div>
        <div class="doc-toolbar">
          <label>Fecha <input type="date" id="f-ofecha" value="${hoyIso()}"></label>
          <label>Tipo <select id="f-otipo">${Object.entries(d.tipos).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
        </div>
        <label class="doc-campo">Nueva observación <textarea id="f-otexto" rows="3" maxlength="2000"></textarea></label>
        <button type="button" class="btn btn-secondary" id="f-oagregar">Agregar observación</button>`,
      botones: [
        { texto: 'Cerrar', valor: null },
        { texto: 'Guardar datos', primario: true, valor: f => ({
          telefono: f.querySelector('#f-tel').value, encargado_nombre: f.querySelector('#f-enc').value,
          encargado_cedula: f.querySelector('#f-encced').value, encargado_telefono: f.querySelector('#f-t1').value,
          encargado_telefono2: f.querySelector('#f-t2').value, direccion: f.querySelector('#f-dir').value,
          adecuacion: f.querySelector('#f-ad').checked, adecuacion_detalle: f.querySelector('#f-addet').value,
        }) },
      ],
    });
    const dlg = [...document.querySelectorAll('.doc-dialogo-fondo')].pop();
    const recargarObs = async () => {
      d = await Panel.json(`/api/docente/estudiantes/${id}/ficha`);
      dlg.querySelector('#f-obs').innerHTML = htmlObservaciones(d);
    };
    dlg.addEventListener('click', async (ev) => {
      try {
        if (ev.target.id === 'f-oagregar') {
          const texto = dlg.querySelector('#f-otexto').value.trim();
          if (!texto) return Panel.toast('Escribe la observación', 'error');
          await Panel.json(`/api/docente/estudiantes/${id}/observaciones`, { method: 'POST', body: {
            fecha: dlg.querySelector('#f-ofecha').value, tipo: dlg.querySelector('#f-otipo').value, texto } });
          dlg.querySelector('#f-otexto').value = '';
          await recargarObs();
          Panel.toast('Observación agregada');
        }
        if (ev.target.dataset.borrarObs) {
          await Panel.json(`/api/docente/observaciones/${ev.target.dataset.borrarObs}`, { method: 'DELETE' });
          await recargarObs();
        }
      } catch (err) { Panel.toast(err.message, 'error'); }
    });
    const datos = await resultado;
    if (!datos) return;
    await Panel.json(`/api/docente/estudiantes/${id}/ficha`, { method: 'PUT', body: datos });
    Panel.toast('Ficha guardada');
  };
})();
