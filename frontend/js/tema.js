// Tema claro u oscuro: sigue al dispositivo hasta que la persona elige uno con el botón (.tema-btn)
(function () {
  const CLAVE = 'tema';
  const leer = () => { try { return localStorage.getItem(CLAVE); } catch (e) { return null; } };
  const guardar = (v) => { try { localStorage.setItem(CLAVE, v); } catch (e) { /* sin almacenamiento: vale solo esta visita */ } };
  const claroDelSistema = () => window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches;
  const efectivo = () => { const g = leer(); return g === 'light' || g === 'dark' ? g : (claroDelSistema() ? 'light' : 'dark'); };

  const SOL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const LUNA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>';

  function pintarBotones() {
    const oscuro = efectivo() === 'dark';
    document.querySelectorAll('.tema-btn').forEach(b => {
      b.innerHTML = oscuro ? SOL : LUNA;
      b.setAttribute('aria-label', oscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro');
      b.title = oscuro ? 'Tema claro' : 'Tema oscuro';
    });
  }

  function alternar() {
    const nuevo = efectivo() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = nuevo;
    guardar(nuevo);
    pintarBotones();
  }

  // Se aplica de inmediato (el script va en <head>) para evitar el destello del tema equivocado
  const g = leer();
  if (g === 'light' || g === 'dark') document.documentElement.dataset.theme = g;

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tema-btn').forEach(b => b.addEventListener('click', alternar));
    pintarBotones();
  });
  if (window.matchMedia) matchMedia('(prefers-color-scheme: light)').addEventListener('change', pintarBotones);
  window.Tema = { alternar, efectivo };
})();
