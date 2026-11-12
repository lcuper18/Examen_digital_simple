// Variables globales
let questions = [];
let examData = {};
let temaGroups = {};
let answers = [];
let estudianteActual = null;
let codigoExamenActual = null;
let duracionMinutos = null;
let tiempoRestanteSegundos = 0;
let timerInterval = null;
let estudianteNombre = '';
let estudianteSeccion = '';
let authToken = null;
let intentoId = null;
let incidenciasDocente = null; // solo si algún día se muestra el detalle completo
let incidencias = 0; // veces que el estudiante salió de la pestaña durante el examen

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Aviso en pantalla (reemplaza a alert): se lee con lectores de pantalla y se cierra solo o con la X
function mostrarAviso(mensaje) {
  const el = document.getElementById('student-aviso');
  el.innerHTML = `<span></span><button type="button" aria-label="Cerrar aviso">×</button>`;
  el.firstElementChild.textContent = mensaje;
  el.lastElementChild.addEventListener('click', () => { el.hidden = true; });
  el.hidden = false;
  clearTimeout(mostrarAviso.espera);
  mostrarAviso.espera = setTimeout(() => { el.hidden = true; }, 9000);
}

function authFetch(url, options = {}, token = authToken) {
  const headers = Object.assign({}, options.headers, { Authorization: `Bearer ${token}` });
  return fetch(url, Object.assign({}, options, { headers }));
}

// ========== SCREEN MANAGEMENT ==========
function showLoginScreen() {
  document.getElementById('change-overlay').classList.remove('active');
  document.getElementById('login-overlay').classList.add('active');
  document.getElementById('code-overlay').classList.remove('active');
  document.getElementById('results-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'none';
}

function showChangePasswordScreen() {
  document.getElementById('login-overlay').classList.remove('active');
  document.getElementById('code-overlay').classList.remove('active');
  document.getElementById('results-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'none';
  document.getElementById('change-overlay').classList.add('active');
  document.getElementById('change-actual').focus();
}

async function performChangePassword() {
  const actual = document.getElementById('change-actual').value;
  const nueva = document.getElementById('change-nueva').value;
  const confirmar = document.getElementById('change-confirmar').value;
  const errorEl = document.getElementById('change-error');
  const mostrar = (msg) => { errorEl.textContent = msg; errorEl.style.display = 'block'; };

  if (nueva.length < 8) return mostrar('La nueva contraseña debe tener al menos 8 caracteres');
  if (nueva !== confirmar) return mostrar('Las contraseñas nuevas no coinciden');

  const response = await authFetch('/api/cambiar-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password_actual: actual, password_nueva: nueva })
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) return mostrar(data.detail || 'No se pudo cambiar la contraseña');

  errorEl.style.display = 'none';
  ['change-actual', 'change-nueva', 'change-confirmar'].forEach(id => { document.getElementById(id).value = ''; });
  estudianteActual.debe_cambiar_password = false;
  saveSession();
  showCodeScreen();
}

function showCodeScreen() {
  if (estudianteActual && estudianteActual.debe_cambiar_password) return showChangePasswordScreen();
  document.getElementById('change-overlay').classList.remove('active');
  document.getElementById('login-overlay').classList.remove('active');
  document.getElementById('code-overlay').classList.add('active');
  document.getElementById('results-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'none';

  if (estudianteActual) {
    document.getElementById('code-student-name').textContent = estudianteActual.nombre;
  }
}

function showExamScreen() {
  document.getElementById('change-overlay').classList.remove('active');
  document.getElementById('login-overlay').classList.remove('active');
  document.getElementById('code-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'block';
  document.getElementById('exam-header').style.display = 'block';
}

// ========== SESSION MANAGEMENT ==========
function saveSession() {
  if (estudianteActual) {
    sessionStorage.setItem('estudianteActual', JSON.stringify(estudianteActual));
    sessionStorage.setItem('authToken', authToken || '');
  }
}

function loadSession() {
  const saved = sessionStorage.getItem('estudianteActual');
  if (saved) {
    try {
      estudianteActual = JSON.parse(saved);
      authToken = sessionStorage.getItem('authToken') || null;
      return !!authToken;
    } catch (e) {
      sessionStorage.removeItem('estudianteActual');
    }
  }
  return false;
}

function clearSession() {
  estudianteActual = null;
  codigoExamenActual = null;
  duracionMinutos = null;
  tiempoRestanteSegundos = 0;
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  clearTimeout(progresoTimeout);
  clearInterval(progresoInterval);
  authToken = null;
  intentoId = null;
  incidencias = 0;
  sessionStorage.removeItem('estudianteActual');
  sessionStorage.removeItem('authToken');
}

function logout() {
  clearSession();
  questions = [];
  examData = {};
  answers = [];
  showLoginScreen();
}

// ========== LOGIN ==========
async function performLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errorEl = document.getElementById('login-error');
  const loginBtn = document.getElementById('login-btn');

  if (!username || !password) {
    errorEl.textContent = 'Escribe tu usuario y tu contraseña.';
    errorEl.classList.add('active');
    return;
  }

  loginBtn.disabled = true;
  loginBtn.innerHTML = '<span class="spinner spinner-mini"></span> Ingresando...';

  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();

    if (data.ok && data.estudiante) {
      estudianteActual = data.estudiante;
      authToken = data.token;
      saveSession();
      errorEl.classList.remove('active');
      document.getElementById('login-username').value = '';
      document.getElementById('login-password').value = '';
      showCodeScreen();
    } else {
      errorEl.textContent = 'Revisa tu usuario y tu contraseña e inténtalo de nuevo.';
      errorEl.classList.add('active');
    }
  } catch (error) {
    console.error('Error en login:', error);
    errorEl.textContent = 'No hay conexión con el servidor. Revisa el wifi e inténtalo de nuevo.';
    errorEl.classList.add('active');
  } finally {
    loginBtn.disabled = false;
    loginBtn.innerHTML = `<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path d="M11 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
    </svg> Iniciar Sesión`;
  }
}

// ========== EXAM CODE ==========
async function startExam() {
  const codigo = document.getElementById('exam-code').value.trim().toUpperCase();
  const errorEl = document.getElementById('code-error');
  const startBtn = document.getElementById('start-exam-btn');

  if (codigo.length < 4) {
    errorEl.textContent = 'El código debe tener al menos 4 caracteres';
    errorEl.classList.add('active');
    return;
  }

  startBtn.disabled = true;
  startBtn.innerHTML = '<span class="spinner spinner-mini"></span> Cargando...';
  errorEl.classList.remove('active');

  try {
    const response = await authFetch(`/api/examen/${encodeURIComponent(codigo)}/iniciar`, { method: 'POST' });

    if (!response.ok) {
      if (response.status === 401) {
        logout();
        return;
      } else if (response.status === 404) {
        errorEl.textContent = 'El código ingresado no existe';
      } else if (response.status === 409) {
        errorEl.textContent = 'Ya enviaste este examen';
      } else if (response.status === 403) {
        const info = await response.json().catch(() => ({}));
        errorEl.textContent = info.detail || 'No puedes iniciar este examen ahora';
      } else {
        errorEl.textContent = 'Error al cargar el examen';
      }
      errorEl.classList.add('active');
      return;
    }

    const data = await response.json();

    // El API devuelve { ok: true, examen: { ... } }
    if (data.ok && data.examen) {
      codigoExamenActual = codigo;
      duracionMinutos = data.examen.duracion_minutos || null;
      loadExamFromData(data.examen);
      showExamScreen();
    } else {
      errorEl.textContent = 'El código ingresado no es válido';
      errorEl.classList.add('active');
    }
  } catch (error) {
    console.error('Error cargando examen:', error);
    errorEl.textContent = 'No hay conexión con el servidor. Revisa el wifi e inténtalo de nuevo.';
    errorEl.classList.add('active');
  } finally {
    startBtn.disabled = false;
    startBtn.innerHTML = `<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
      <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg> Comenzar Examen`;
  }
}

function loadExamFromData(examenData) {
  examData = examenData;
  questions = validateAndTransformQuestions(examenData.preguntas);
  temaGroups = generateDynamicTemaGroups(questions);
  answers = new Array(questions.length).fill(null);

  updateExamMetadata();
  renderExam();
  updateSimpleStats();

  // Restaurar respuestas: primero las guardadas en el servidor, si no las de localStorage
  const delServidor = examenData.respuestas_guardadas || {};
  let savedAnswers = null;
  if (Object.keys(delServidor).length > 0) {
    savedAnswers = questions.map(q => {
      const letra = delServidor[String(q.numeroOriginal)];
      return letra ? letra.charCodeAt(0) - 97 : null;
    });
  } else {
    savedAnswers = loadFromLocalStorage();
  }
  if (savedAnswers && savedAnswers.length === questions.length) {
    answers = savedAnswers;
    // Re-renderizar las opciones seleccionadas
    answers.forEach((ans, idx) => {
      if (ans !== null) {
        const card = document.getElementById('q' + idx);
        if (card) {
          const opts = card.querySelectorAll('.option-item');
          opts.forEach((el, j) => {
            el.classList.remove('selected');
            if (j === ans) el.classList.add('selected');
          });
          document.getElementById('nav-' + idx).classList.add('answered');
        }
      }
    });
    updateSimpleStats();
  }

  // Iniciar timer (FASE 5.3)
  startTimer();
}

function validateAndTransformQuestions(preguntasJSON) {
  const transformedQuestions = [];

  preguntasJSON.forEach((pregunta, index) => {
    const requiredFields = ['numero', 'tema', 'pregunta', 'opciones'];
    for (const field of requiredFields) {
      if (!pregunta[field]) throw new Error(`Pregunta ${index + 1}: falta el campo "${field}"`);
    }

    if (typeof pregunta.opciones !== 'object') throw new Error(`Pregunta ${index + 1}: "opciones" debe ser un objeto`);

    // Las opciones son a, b, c y, en algunos exámenes, d (siempre consecutivas desde la a)
    const keys = ['a', 'b', 'c', 'd'].filter(k => pregunta.opciones[k]);
    if (keys.length < 3) throw new Error(`Pregunta ${index + 1}: debe tener al menos 3 opciones`);

    transformedQuestions.push({
      tema: pregunta.tema,
      q: pregunta.pregunta,
      opts: keys.map(k => pregunta.opciones[k]),
      ans: null, // la respuesta correcta solo la conoce el servidor
      numeroOriginal: pregunta.numero
    });
  });

  return transformedQuestions;
}

function generateDynamicTemaGroups(questions) {
  const groups = {};
  questions.forEach((q, index) => {
    if (!groups[q.tema]) groups[q.tema] = [];
    groups[q.tema].push({ ...q, idx: index });
  });
  return groups;
}

function updateExamMetadata() {
  // Si no hay examData, limpiar los campos
  if (!examData || !examData.titulo) {
    document.getElementById('exam-title-header').textContent = 'Examen';
    document.getElementById('exam-subtitle-header').textContent = 'Cargando...';
    document.getElementById('exam-specialty').textContent = '';
    document.getElementById('exam-professor').textContent = '';
    document.getElementById('exam-instructions').innerHTML = '<strong>Instrucciones:</strong> Cargando examen...';
    return;
  }

  document.getElementById('exam-title-header').textContent = examData.titulo || 'Examen';
  document.getElementById('exam-subtitle-header').textContent =
    `${examData.institucion || ''} · ${examData.nivel || ''} · ${questions.length} preguntas`;

  if (examData.especialidad) {
    document.getElementById('exam-specialty').textContent = examData.especialidad;
  } else {
    document.getElementById('exam-specialty').textContent = '';
  }

  if (examData.profesor) {
    document.getElementById('exam-professor').textContent = `Profesor: ${examData.profesor}`;
  } else {
    document.getElementById('exam-professor').textContent = '';
  }

  if (examData.instrucciones) {
    document.getElementById('exam-instructions').innerHTML =
      `<strong>Instrucciones:</strong> ${escapeHtml(examData.instrucciones)}`;
  } else {
    document.getElementById('exam-instructions').innerHTML = '<strong>Instrucciones:</strong> Sin instrucciones';
  }

  document.getElementById('pending-count').textContent = questions.length;
  document.getElementById('progress-text').textContent = `0 / ${questions.length}`;
  document.getElementById('results-total').textContent = questions.length;
}

function submitExam() {
  // El reloj NO se detiene aquí: si el estudiante cancela el aviso de preguntas sin responder,
  // debe seguir corriendo y el examen se envía solo al acabarse el tiempo. sendExam() lo detiene al enviar.
  const unanswered = answers.filter(a => a === null).length;
  if (unanswered > 0) {
    document.getElementById('warning-message').textContent =
      `Tienes ${unanswered} preguntas sin contestar. ¿Deseas enviar el examen de todas formas?`;
    document.getElementById('warning-overlay').classList.add('active');
  } else {
    sendExam();
  }
}

function closeWarningModal() {
  document.getElementById('warning-overlay').classList.remove('active');
}

function confirmSubmit() {
  closeWarningModal();
  sendExam();
}

async function sendExam() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  clearTimeout(progresoTimeout);
  clearInterval(progresoInterval);
  const respuestas = respuestasPorNumero();

  try {
    const response = await authFetch(`/api/examen/${encodeURIComponent(codigoExamenActual)}/enviar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ respuestas, incidencias })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      mostrarAviso(data.detail || 'No se pudo enviar el examen. Avisa a tu docente.');
      return;
    }
    intentoId = data.intento_id;
    clearLocalStorage();
    showDetailedResults();
  } catch (error) {
    mostrarAviso('No hay conexión con el servidor. Tus respuestas siguen aquí; revisa el wifi e inténtalo de nuevo.');
  }
}

const ICONO_RESULTADO = {
  enviado: '<svg width="56" height="56" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
  bien: '<svg width="56" height="56" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.5 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z"/></svg>',
  repasar: '<svg width="56" height="56" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M4 5a2 2 0 012-2h12v18H6a2 2 0 01-2-2zM4 19a2 2 0 012-2h12"/></svg>',
};

function showDetailedResults() {
  // === TAREA 4.1: Obtener datos del estudiante ===
  const estudianteData = sessionStorage.getItem('estudianteActual');
  if (estudianteData) {
    try {
      const parsed = JSON.parse(estudianteData);
      estudianteNombre = parsed.nombre || 'Estudiante';
      estudianteSeccion = parsed.seccion || 'N/A';
    } catch (e) {
      estudianteNombre = 'Estudiante';
      estudianteSeccion = 'N/A';
    }
  } else {
    estudianteNombre = 'Estudiante';
    estudianteSeccion = 'N/A';
  }

  // Verificar si tenemos respuestas correctas (vendrán en FASE 3)
  const hasCorrectAnswers = questions.some(q => q.ans !== null);
  const answered = answers.filter(a => a !== null).length;

  let correct = 0;
  if (hasCorrectAnswers) {
    correct = answers.reduce((count, ans, idx) =>
      ans === questions[idx].ans ? count + 1 : count, 0);
  }
  const total = questions.length;
  const percentage = hasCorrectAnswers ? Math.round((correct / total) * 100) : 0;
  const nota = percentage; // 0-100

  document.getElementById('results-correct').textContent = hasCorrectAnswers ? correct : '-';
  document.getElementById('results-wrong').textContent = hasCorrectAnswers ? (total - correct) : '-';
  document.getElementById('results-total').textContent = total;

  const title = document.getElementById('results-title');
  const subtitle = document.getElementById('results-subtitle');
  const icon = document.getElementById('results-icon');

  if (!hasCorrectAnswers) {
    // FASE 2: Sin respuestas correctas aún
    icon.innerHTML = ICONO_RESULTADO.enviado;
    title.textContent = '¡Examen enviado!';
    subtitle.textContent = `Contestaste ${answered} de ${total} preguntas. Tu docente te compartirá el resultado.`;
  } else if (percentage >= 80) {
    icon.innerHTML = ICONO_RESULTADO.bien;
    title.textContent = '¡Excelente!';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  } else if (percentage >= 60) {
    icon.innerHTML = ICONO_RESULTADO.bien;
    title.textContent = '¡Buen trabajo!';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  } else if (percentage >= 40) {
    icon.innerHTML = ICONO_RESULTADO.repasar;
    title.textContent = 'Casi lo logras';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  } else {
    icon.innerHTML = ICONO_RESULTADO.repasar;
    title.textContent = '¡Sigue intentando!';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  }

  if (!hasCorrectAnswers) {
    document.getElementById('detailed-results').style.display = 'none';
    document.getElementById('download-pdf-btn').style.display = 'none';
    document.getElementById('results-overlay').classList.add('active');
    return;
  }
  document.getElementById('detailed-results').style.display = 'block';
  document.getElementById('download-pdf-btn').style.display = 'flex';

  // === Construir contenido de resultados detallados ===
  const resultsList = document.getElementById('results-list');
  resultsList.innerHTML = '';

  // === TAREA 4.1: Encabezado del estudiante ===
  const studentHeader = document.createElement('div');
  studentHeader.className = 'result-student-header';
  studentHeader.innerHTML = `
    <div class="result-student-card">
      <div class="result-student-info">
        <span class="result-student-label">Estudiante:</span>
        <span class="result-student-name">${escapeHtml(estudianteNombre)}</span>
      </div>
      <div class="result-student-info">
        <span class="result-student-label">Sección:</span>
        <span class="result-student-value">${escapeHtml(estudianteSeccion)}</span>
      </div>
      <div class="result-student-info">
        <span class="result-student-label">Código Examen:</span>
        <span class="result-student-value">${escapeHtml(codigoExamenActual || 'N/A')}</span>
      </div>
      <div class="result-student-info">
        <span class="result-student-label">Salidas de la pestaña:</span>
        <span class="result-student-value">${escapeHtml(incidenciasDocente ?? 'N/A')}</span>
      </div>
    </div>
  `;
  resultsList.appendChild(studentHeader);

  // === TAREA 4.2: Desglose por tema ===
  const topicBreakdown = generateTopicBreakdown();
  const topicSection = document.createElement('div');
  topicSection.className = 'topic-breakdown-section';

  let topicTableHtml = `
    <h4 class="topic-breakdown-title">Desglose por Tema</h4>
    <table class="topic-breakdown-table">
      <thead>
        <tr>
          <th>Tema</th>
          <th>Correctas</th>
          <th>Incorrectas</th>
          <th>Total</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>
  `;

  topicBreakdown.forEach(row => {
    const pct = row.total > 0 ? Math.round((row.correctas / row.total) * 100) : 0;
    topicTableHtml += `
      <tr>
        <td class="topic-name">${escapeHtml(row.tema)}</td>
        <td class="topic-correctas">${row.correctas}</td>
        <td class="topic-incorrectas">${row.incorrectas}</td>
        <td class="topic-total">${row.total}</td>
        <td class="topic-pct ${pct >= 60 ? 'good' : 'low'}">${pct}%</td>
      </tr>
    `;
  });

  topicTableHtml += '</tbody></table>';
  topicSection.innerHTML = topicTableHtml;
  resultsList.appendChild(topicSection);

  // === TAREA 4.3: Detalle de preguntas (sin truncar) ===
  const detailTitle = document.createElement('h4');
  detailTitle.className = 'detail-title';
  detailTitle.textContent = 'Detalle de Respuestas';
  resultsList.appendChild(detailTitle);

  questions.forEach((q, idx) => {
    const userAnswer = answers[idx];
    const userAnswerText = userAnswer !== null ? q.opts[userAnswer] : 'Sin contestar';

    let resultClass = 'neutral';
    let statusHtml = '';
    let correctAnswerHtml = '';

    if (hasCorrectAnswers) {
      const isCorrect = userAnswer === q.ans;
      resultClass = isCorrect ? 'correct' : 'wrong';
      const correctAnswerText = q.opts[q.ans];
      correctAnswerHtml = `<span class="correct-answer">Correcta: ${String.fromCharCode(97 + q.ans)}) ${escapeHtml(correctAnswerText)}</span>`;
      statusHtml = `<span class="result-status">${isCorrect ? '✓' : '✗'}</span>`;
    }

    const userAnswerLabel = userAnswer !== null ? `${String.fromCharCode(97 + userAnswer)}) ${q.opts[userAnswer]}` : 'Sin contestar';

    const resultItem = document.createElement('div');
    resultItem.className = `result-item ${resultClass}`;
    resultItem.innerHTML = `
      <div class="result-question-header">
        <span class="result-question-num">${q.numeroOriginal}.</span>
        <span class="result-question-topic">[${escapeHtml(q.tema)}]</span>
      </div>
      <div class="result-question-text">${escapeHtml(q.q)}</div>
      <div class="result-details">
        <span class="user-answer">Tu respuesta: ${escapeHtml(userAnswerLabel)}</span>
        ${correctAnswerHtml}
        ${statusHtml}
      </div>
    `;
    resultsList.appendChild(resultItem);
  });

  document.getElementById('results-overlay').classList.add('active');
}

// === TAREA 4.2: Generar desglose por tema ===
function generateTopicBreakdown() {
  const topicMap = {};

  questions.forEach((q, idx) => {
    const tema = q.tema || 'Sin tema';
    if (!topicMap[tema]) {
      topicMap[tema] = { correctas: 0, incorrectas: 0, total: 0 };
    }
    topicMap[tema].total++;

    const userAnswer = answers[idx];
    if (userAnswer !== null && q.ans !== null) {
      if (userAnswer === q.ans) {
        topicMap[tema].correctas++;
      } else {
        topicMap[tema].incorrectas++;
      }
    }
  });

  return Object.entries(topicMap).map(([tema, data]) => ({
    tema,
    correctas: data.correctas,
    incorrectas: data.incorrectas,
    total: data.total
  }));
}

function generatePDF() {
  if (typeof jsPDF === 'undefined' && typeof window.jspdf === 'undefined') {
    const script = document.createElement('script');
    script.src = '/static/js/jspdf.min.js';
    script.onload = () => createPDF();
    script.onerror = () => mostrarAviso('No se pudo preparar el PDF.');
    document.head.appendChild(script);
  } else {
    createPDF();
  }
}

function createPDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  // Verificar si tenemos respuestas correctas
  const hasCorrectAnswers = questions.some(q => q.ans !== null);
  let correct = 0;
  if (hasCorrectAnswers) {
    correct = answers.reduce((count, ans, idx) =>
      ans === questions[idx].ans ? count + 1 : count, 0);
  }
  const total = questions.length;
  const percentage = hasCorrectAnswers ? Math.round((correct / total) * 100) : 0;
  const nota = percentage;

  // ---- ENCABEZADO INSTITUCIONAL ----
  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.text("Colegio Técnico Profesional Las Palmitas", 105, 20, { align: "center" });

  doc.setFontSize(12);
  doc.setFont("helvetica", "normal");
  doc.text("Lectiva - Resultados del examen", 105, 28, { align: "center" });

  // Línea separadora
  doc.setLineWidth(0.5);
  doc.line(20, 32, 190, 32);

  // ---- DATOS DEL ESTUDIANTE ----
  let y = 42;
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.text(`Estudiante: ${estudianteNombre}`, 20, y);
  doc.setFont("helvetica", "normal");
  doc.text(`Sección: ${estudianteSeccion}`, 120, y);
  y += 8;
  doc.text(`Código de Examen: ${codigoExamenActual || 'N/A'}`, 20, y);
  doc.text(`Fecha: ${new Date().toLocaleDateString()}`, 120, y);

  // ---- RESUMEN ----
  y += 14;
  doc.setFontSize(13);
  doc.setFont("helvetica", "bold");
  doc.text("Resumen de Resultados", 20, y);

  y += 8;
  doc.setFontSize(11);
  doc.setFont("helvetica", "normal");
  doc.text(`Puntuación: ${correct}/${total}`, 20, y);
  doc.text(`Nota: ${nota}`, 100, y);
  y += 7;
  doc.text(`Correctas: ${correct}`, 20, y);
  doc.text(`Incorrectas: ${total - correct}`, 100, y);

  // ---- DESGLOSE POR TEMA ----
  y += 14;
  doc.setFontSize(13);
  doc.setFont("helvetica", "bold");
  doc.text("Desglose por Tema", 20, y);

  y += 8;
  // Tabla de temas
  const topicData = generateTopicBreakdown();
  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");

  // Header de tabla
  doc.setLineWidth(0.3);
  doc.line(20, y, 190, y); // línea superior
  doc.text("Tema", 22, y + 5);
  doc.text("Correctas", 100, y + 5);
  doc.text("Incorrectas", 130, y + 5);
  doc.text("Total", 160, y + 5);
  doc.line(20, y + 7, 190, y + 7); // línea header
  y += 10;

  topicData.forEach(row => {
    doc.text(row.tema.substring(0, 30), 22, y);
    doc.text(String(row.correctas), 100, y);
    doc.text(String(row.incorrectas), 130, y);
    doc.text(String(row.total), 160, y);
    y += 6;
  });
  doc.line(20, y, 190, y); // línea inferior

  // ---- DETALLE DE PREGUNTAS ----
  y += 10;
  doc.setFontSize(13);
  doc.setFont("helvetica", "bold");
  doc.text("Detalle de Respuestas", 20, y);
  y += 8;

  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");

  questions.forEach((q, idx) => {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }

    const userAnswer = answers[idx];
    const isCorrect = hasCorrectAnswers && userAnswer === q.ans;

    // Número de pregunta y tema
    doc.setFont("helvetica", "bold");
    doc.text(`${q.numeroOriginal}. [${q.tema}]`, 20, y);
    doc.setFont("helvetica", "normal");

    y += 5;
    // Pregunta completa (sin truncar)
    const lines = doc.splitTextToSize(q.q, 170);
    doc.text(lines, 22, y);
    y += lines.length * 4 + 2;

    // Tu respuesta
    const userAnswerText = userAnswer !== null ? `${String.fromCharCode(97 + userAnswer)}) ${q.opts[userAnswer]}` : 'Sin contestar';
    const correctAnswerText = `${String.fromCharCode(97 + q.ans)}) ${q.opts[q.ans]}`;

    if (hasCorrectAnswers) {
      if (isCorrect) {
        doc.setTextColor(0, 128, 0); // verde
        doc.text(`Tu respuesta: ${userAnswerText} ✓`, 25, y);
      } else {
        doc.setTextColor(200, 0, 0); // rojo
        doc.text(`Tu respuesta: ${userAnswerText}`, 25, y);
        y += 5;
        doc.setTextColor(0, 128, 0);
        doc.text(`Respuesta correcta: ${correctAnswerText}`, 25, y);
      }
    } else {
      doc.setTextColor(100, 100, 100);
      doc.text(`Tu respuesta: ${userAnswerText}`, 25, y);
    }

    doc.setTextColor(0, 0, 0);
    y += 8;
  });

  // ---- FOOTER ----
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(9);
    doc.setTextColor(128);
    doc.text(`Página ${i} de ${pageCount}`, 105, 290, { align: "center" });
    doc.text(`${institucionNombre} - Lectiva`, 20, 290);
    doc.text(new Date().toLocaleDateString(), 170, 290);
  }

  const filename = `resultados-${codigoExamenActual || 'examen'}-${estudianteNombre.replace(/\s+/g, '-')}-${new Date().toISOString().slice(0,10)}.pdf`;
  doc.save(filename);
}

let institucionNombre = 'CTP Las Palmitas';
fetch('/api/config').then(r => r.json()).then(c => {
  if (c.institucion) institucionNombre = c.institucion;
  const v = document.getElementById('login-version');
  if (v && c.version) v.textContent = `Versión ${c.version}`;
}).catch(() => {});

function closeResults() {
  document.getElementById('results-overlay').classList.remove('active');
  if (intentoId !== null) logout(); // el examen ya fue enviado
}

function scrollToQuestion(idx) {
  const card = document.getElementById('q' + idx);
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    document.querySelectorAll('.q-nav-item').forEach(n => n.classList.remove('current'));
    document.getElementById('nav-' + idx).classList.add('current');
  }
}

function renderExam() {
  const content = document.getElementById('exam-content');
  const nav = document.getElementById('question-nav');
  content.innerHTML = '';
  nav.innerHTML = '';

  questions.forEach((q, i) => {
    const navItem = document.createElement('button');
    navItem.type = 'button';
    navItem.className = 'q-nav-item';
    navItem.setAttribute('aria-label', `Ir a la pregunta ${q.numeroOriginal}`);
    navItem.id = 'nav-' + i;
    navItem.textContent = q.numeroOriginal;
    navItem.onclick = () => scrollToQuestion(i);
    nav.appendChild(navItem);
  });

  Object.entries(temaGroups).forEach(([tema, preguntasEnTema]) => {
    if (preguntasEnTema.length === 0) return;

    const sec = document.createElement('div');
    sec.className = 'theme-section';
    sec.innerHTML = `
      <div class="theme-header">
        <div class="theme-icon">
          <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
          </svg>
        </div>
        <div>
          <div class="theme-title">${escapeHtml(tema)}</div>
          <div class="theme-subtitle">${preguntasEnTema.length} preguntas</div>
        </div>
      </div>
    `;
    preguntasEnTema.forEach((q, qIndex) => {
      const card = document.createElement('div');
      card.className = 'question-card';
      card.id = 'q' + q.idx;
      // Staggered animation
      card.style.animationDelay = `${0.1 + qIndex * 0.05}s`;

      const keys = ['a', 'b', 'c', 'd'];
      let optsHtml = q.opts.map((o, j) => `
        <button type="button" class="option-item" id="opt-${q.idx}-${j}" data-q="${q.idx}" data-opt="${j}" aria-pressed="false">
          <span class="option-key" aria-hidden="true">${keys[j]}</span>
          <span class="option-text">${escapeHtml(o)}</span>
        </button>
      `).join('');
      card.innerHTML = `
        <div class="question-header">
          <div class="question-number">${q.numeroOriginal}</div>
          <div class="question-text">${escapeHtml(q.q)}</div>
        </div>
        <div class="options-list" role="group" aria-label="Opciones de la pregunta ${q.numeroOriginal}">${optsHtml}</div>
      `;
      card.querySelectorAll('.option-item').forEach(b => b.addEventListener('click', () => answer(Number(b.dataset.q), Number(b.dataset.opt))));
      sec.appendChild(card);
    });
    content.appendChild(sec);
  });
  updateSimpleStats();
}

function cantidadOpciones(qIdx) {
  return questions[qIdx].opts.length;
}

function answer(qIdx, optIdx) {
  answers[qIdx] = optIdx;

  const card = document.getElementById('q' + qIdx);
  const navItem = document.getElementById('nav-' + qIdx);
  const opts = card.querySelectorAll('.option-item');

  opts.forEach((el, j) => {
    el.classList.remove('selected', 'disabled');
    el.setAttribute('aria-pressed', j === optIdx ? 'true' : 'false');
    if (j === optIdx) {
      el.classList.add('selected');
      // Ripple effect
      const rect = el.getBoundingClientRect();
      const x = ((optIdx / cantidadOpciones(qIdx)) * 100);
      el.style.setProperty('--ripple-x', x + '%');
      el.style.setProperty('--ripple-y', '50%');
    }
  });

  navItem.classList.add('answered');

  updateSimpleStats();
  saveToLocalStorage();
  programarProgreso();
}

function updateSimpleStats() {
  const answered = answers.filter(a => a !== null).length;
  const pending = questions.length - answered;

  document.getElementById('answered-count').textContent = answered;
  document.getElementById('pending-count').textContent = pending;
  document.getElementById('progress-text').textContent = `${answered} / ${questions.length}`;

  const fill = document.getElementById('progress-fill');
  fill.style.width = (answered / questions.length * 100) + '%';

  // Guardar en localStorage por seguridad
  saveToLocalStorage();
}

// ========== LOCALSTORAGE (FASE 5.1 y 5.2) ==========
function saveToLocalStorage() {
  if (!codigoExamenActual || !estudianteActual) return;
  const key = `examen_${codigoExamenActual}_${estudianteActual.id}`;
  const data = {
    answers: answers,
    timestamp: Date.now()
  };
  localStorage.setItem(key, JSON.stringify(data));
}

function loadFromLocalStorage() {
  if (!codigoExamenActual || !estudianteActual) return null;
  const key = `examen_${codigoExamenActual}_${estudianteActual.id}`;
  const saved = localStorage.getItem(key);
  if (saved) {
    try {
      const data = JSON.parse(saved);
      // Verificar que no esté expirado (24 horas)
      const maxAge = 24 * 60 * 60 * 1000;
      if (Date.now() - data.timestamp < maxAge) {
        return data.answers;
      }
    } catch (e) {
      console.warn('Error al leer localStorage:', e);
    }
  }
  return null;
}

function clearLocalStorage() {
  if (!codigoExamenActual || !estudianteActual) return;
  const key = `examen_${codigoExamenActual}_${estudianteActual.id}`;
  localStorage.removeItem(key);
}

// ========== TIMER (FASE 5.3 y 5.4) ==========
let progresoTimeout = null;
let progresoInterval = null;

function respuestasPorNumero() {
  const respuestas = {};
  answers.forEach((ans, idx) => {
    if (ans !== null) respuestas[String(questions[idx].numeroOriginal)] = String.fromCharCode(97 + ans);
  });
  return respuestas;
}

// Guarda el progreso en el servidor y sincroniza el tiempo restante (incluye tiempo extra)
async function guardarProgreso() {
  if (!authToken || !codigoExamenActual || intentoId !== null) return;
  try {
    const response = await authFetch(`/api/examen/${encodeURIComponent(codigoExamenActual)}/progreso`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ respuestas: respuestasPorNumero(), incidencias })
    });
    if (response.status === 401) return logout();
    const data = await response.json().catch(() => ({}));
    if (response.ok) {
      if (typeof data.segundos_restantes === 'number') {
        tiempoRestanteSegundos = data.segundos_restantes;
        updateTimerDisplay();
      }
    } else if (response.status === 409 || response.status === 403) {
      mostrarAviso(data.detail || 'Tu examen ya no está disponible.');
      logout();
    }
  } catch (e) {
    // Sin conexión: se reintenta en el siguiente guardado; las respuestas siguen en este equipo
  }
}

function programarProgreso() {
  clearTimeout(progresoTimeout);
  progresoTimeout = setTimeout(guardarProgreso, 2000);
}

function startTimer() {
  duracionMinutos = examData.duracion_minutos || 60;
  tiempoRestanteSegundos = examData.segundos_restantes ?? duracionMinutos * 60;

  updateTimerDisplay();

  timerInterval = setInterval(() => {
    tiempoRestanteSegundos--;
    updateTimerDisplay();

    if (tiempoRestanteSegundos <= 0) {
      clearInterval(timerInterval);
      forceSubmit();
    }

    // Advertencia a los últimos 5 minutos
    if (tiempoRestanteSegundos === 5 * 60) {
      document.getElementById('timer-display').classList.add('warning');
      document.getElementById('timer-alerta').textContent = 'Quedan 5 minutos para terminar el examen.';
      mostrarAviso('Quedan 5 minutos para terminar el examen.');
    }
  }, 1000);

  clearInterval(progresoInterval);
  progresoInterval = setInterval(guardarProgreso, 30000);
}

function updateTimerDisplay() {
  const minutes = Math.floor(tiempoRestanteSegundos / 60);
  const seconds = tiempoRestanteSegundos % 60;
  const text = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  document.getElementById('timer-text').textContent = text;
}

function forceSubmit() {
  // Deshabilitar todas las opciones para que no pueda seguir contestando
  document.querySelectorAll('.option-item').forEach(el => {
    el.style.pointerEvents = 'none';
    el.style.opacity = '0.5';
  });

  // Si el aviso de preguntas sin responder estaba abierto, se cierra: el tiempo terminó
  closeWarningModal();

  // Detener el timer si no se hizo ya
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  sendExam();
}

// Init
document.addEventListener('visibilitychange', () => {
  if (document.hidden && timerInterval) incidencias++;
});

document.addEventListener('DOMContentLoaded', () => {
  // Verificar si hay sesión guardada
  if (loadSession()) {
    // Hay sesión - ir a pantalla de código
    showCodeScreen();
  } else {
    // No hay sesión - mostrar login
    showLoginScreen();
  }

  // Mostrar u ocultar la contraseña
  document.getElementById('ver-clave').addEventListener('click', (e) => {
    const campo = document.getElementById('login-password');
    const ver = campo.type === 'password';
    campo.type = ver ? 'text' : 'password';
    e.currentTarget.textContent = ver ? 'Ocultar' : 'Mostrar';
    e.currentTarget.setAttribute('aria-pressed', ver ? 'true' : 'false');
    e.currentTarget.setAttribute('aria-label', ver ? 'Ocultar la contraseña' : 'Mostrar la contraseña');
  });

  // Event listeners para login
  document.getElementById('change-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performChangePassword();
  });
  document.getElementById('login-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performLogin();
  });

  // Event listeners para código de examen
  document.getElementById('code-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startExam();
  });
});
