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

// ========== SCREEN MANAGEMENT ==========
function showLoginScreen() {
  document.getElementById('login-overlay').classList.add('active');
  document.getElementById('code-overlay').classList.remove('active');
  document.getElementById('results-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'none';
}

function showCodeScreen() {
  document.getElementById('login-overlay').classList.remove('active');
  document.getElementById('code-overlay').classList.add('active');
  document.getElementById('results-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'none';

  if (estudianteActual) {
    document.getElementById('code-student-name').textContent = estudianteActual.nombre;
  }
}

function showExamScreen() {
  document.getElementById('login-overlay').classList.remove('active');
  document.getElementById('code-overlay').classList.remove('active');
  document.querySelector('.exam-container').style.display = 'block';
  document.getElementById('exam-header').style.display = 'block';
}

// ========== SESSION MANAGEMENT ==========
function saveSession() {
  if (estudianteActual) {
    sessionStorage.setItem('estudianteActual', JSON.stringify(estudianteActual));
  }
}

function loadSession() {
  const saved = sessionStorage.getItem('estudianteActual');
  if (saved) {
    try {
      estudianteActual = JSON.parse(saved);
      return true;
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
  sessionStorage.removeItem('estudianteActual');
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
    errorEl.textContent = 'Por favor ingresa usuario y contraseña';
    errorEl.classList.add('active');
    return;
  }

  loginBtn.disabled = true;
  loginBtn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin-right:8px;"></span> Ingresando...';

  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();

    if (data.ok && data.estudiante) {
      estudianteActual = data.estudiante;
      saveSession();
      errorEl.classList.remove('active');
      document.getElementById('login-username').value = '';
      document.getElementById('login-password').value = '';
      showCodeScreen();
    } else {
      errorEl.textContent = 'Usuario o contraseña incorrectos';
      errorEl.classList.add('active');
    }
  } catch (error) {
    console.error('Error en login:', error);
    errorEl.textContent = 'Error de conexión. Verifica el servidor.';
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
  startBtn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin-right:8px;"></span> Cargando...';
  errorEl.classList.remove('active');

  try {
    const response = await fetch(`/api/examen/${encodeURIComponent(codigo)}`);

    if (!response.ok) {
      if (response.status === 404) {
        errorEl.textContent = 'El código ingresado no existe';
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
    errorEl.textContent = 'Error de conexión. Verifica el servidor.';
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

  // Restaurar respuestas guardadas en localStorage (FASE 5.2)
  const savedAnswers = loadFromLocalStorage();
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

// Esta función ya no se usa para cargar del API (FASE 2)
// El examen se carga mediante startExam() -> loadExamFromData()
async function loadQuestions() {
  console.warn('loadQuestions() está obsoleto. Usa startExam() para cargar un examen del API.');
}

function validateJSONStructure(data) {
  if (!data || typeof data !== 'object') throw new Error('El archivo JSON no es un objeto válido');
  if (!data.examen || typeof data.examen !== 'object') throw new Error('Falta el objeto "examen" en el JSON');

  const exam = data.examen;
  const requiredFields = ['titulo', 'institucion', 'nivel', 'total_preguntas', 'preguntas'];
  for (const field of requiredFields) {
    if (!exam[field]) throw new Error(`Falta el campo obligatorio: ${field}`);
  }
  if (!Array.isArray(exam.preguntas)) throw new Error('El campo "preguntas" debe ser un array');
  if (exam.preguntas.length === 0) throw new Error('No hay preguntas en el archivo JSON');
}

function validateAndTransformQuestions(preguntasJSON) {
  const transformedQuestions = [];

  preguntasJSON.forEach((pregunta, index) => {
    // Campos requeridos del API (incluye respuesta_correcta)
    const requiredFields = ['numero', 'tema', 'pregunta', 'opciones', 'respuesta_correcta'];
    for (const field of requiredFields) {
      if (!pregunta[field]) throw new Error(`Pregunta ${index + 1}: falta el campo "${field}"`);
    }

    if (typeof pregunta.opciones !== 'object') throw new Error(`Pregunta ${index + 1}: "opciones" debe ser un objeto`);

    const expectedKeys = ['a', 'b', 'c'];
    for (const key of expectedKeys) {
      if (!pregunta.opciones[key]) throw new Error(`Pregunta ${index + 1}: falta la opción "${key}"`);
    }

    // Convertir respuesta_correcta (a,b,c) a índice (0,1,2)
    const ansIndex = pregunta.respuesta_correcta.charCodeAt(0) - 97;

    transformedQuestions.push({
      tema: pregunta.tema,
      q: pregunta.pregunta,
      opts: [pregunta.opciones.a, pregunta.opciones.b, pregunta.opciones.c],
      ans: ansIndex,
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
    document.getElementById('exam-title-header').textContent = 'Examen Digital';
    document.getElementById('exam-subtitle-header').textContent = 'Cargando...';
    document.getElementById('exam-specialty').textContent = '';
    document.getElementById('exam-professor').textContent = '';
    document.getElementById('exam-instructions').innerHTML = '<strong>Instrucciones:</strong> Cargando examen...';
    return;
  }

  document.getElementById('exam-title-header').textContent = examData.titulo || 'Examen Digital';
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
      `<strong>Instrucciones:</strong> ${examData.instrucciones}`;
  } else {
    document.getElementById('exam-instructions').innerHTML = '<strong>Instrucciones:</strong> Sin instrucciones';
  }

  document.getElementById('pending-count').textContent = questions.length;
  document.getElementById('progress-text').textContent = `0 / ${questions.length}`;
  document.getElementById('results-total').textContent = questions.length;
}

function showLoading(show) {
  const loadingEl = document.getElementById('loading-indicator');
  const contentEl = document.getElementById('exam-content');
  const navEl = document.getElementById('question-nav');

  if (show) {
    loadingEl.style.display = 'block';
    contentEl.style.display = 'none';
    navEl.style.display = 'none';
  } else {
    loadingEl.style.display = 'none';
    contentEl.style.display = 'block';
    navEl.style.display = 'flex';
  }
}

function showError(message) {
  const errorEl = document.getElementById('error-message');
  document.getElementById('error-text').textContent = message;
  errorEl.style.display = 'block';
}

function hideError() {
  document.getElementById('error-message').style.display = 'none';
}

function submitExam() {
  // Detener el timer si está corriendo
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  const unanswered = answers.filter(a => a === null).length;
  if (unanswered > 0) {
    document.getElementById('warning-message').textContent =
      `Tienes ${unanswered} preguntas sin contestar. ¿Deseas enviar el examen de todas formas?`;
    document.getElementById('warning-overlay').classList.add('active');
  } else {
    // Limpiar localStorage al enviar
    clearLocalStorage();
    showPasswordModal();
  }
}

function closeWarningModal() {
  document.getElementById('warning-overlay').classList.remove('active');
}

function confirmSubmit() {
  closeWarningModal();
  // Limpiar localStorage al enviar
  clearLocalStorage();
  showPasswordModal();
}

function showPasswordModal() {
  document.getElementById('password-overlay').classList.add('active');
  document.getElementById('teacher-password').value = '';
  document.getElementById('password-error').style.display = 'none';
  document.getElementById('teacher-password').focus();
}

function closePasswordModal() {
  document.getElementById('password-overlay').classList.remove('active');
}

async function validatePassword() {
  const passwordInput = document.getElementById('teacher-password').value;
  const errorEl = document.getElementById('password-error');

  if (!passwordInput) {
    errorEl.textContent = 'Ingrese una contraseña';
    errorEl.style.display = 'block';
    return;
  }

  try {
    const response = await fetch('/api/verificar-docente', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: passwordInput })
    });
    const data = await response.json();

    if (data.ok) {
      closePasswordModal();
      showDetailedResults();
    } else {
      errorEl.textContent = data.error || 'Contraseña incorrecta';
      errorEl.style.display = 'block';
      document.getElementById('teacher-password').value = '';
      document.getElementById('teacher-password').focus();
    }
  } catch (error) {
    errorEl.textContent = 'Error de conexión';
    errorEl.style.display = 'block';
  }
}

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
    icon.textContent = '📝';
    title.textContent = '¡Examen Enviado!';
    subtitle.textContent = `${answered}/${total} preguntas contestadas`;
  } else if (percentage >= 80) {
    icon.textContent = '🏆';
    title.textContent = '¡Excelente!';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  } else if (percentage >= 60) {
    icon.textContent = '👍';
    title.textContent = '¡Buen trabajo!';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  } else if (percentage >= 40) {
    icon.textContent = '📚';
    title.textContent = 'Casi lo logras';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
  } else {
    icon.textContent = '💪';
    title.textContent = '¡Sigue intentando!';
    subtitle.textContent = `Puntuación: ${correct}/${total} (${percentage}%) | Nota: ${nota}`;
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
        <span class="result-student-name">${estudianteNombre}</span>
      </div>
      <div class="result-student-info">
        <span class="result-student-label">Sección:</span>
        <span class="result-student-value">${estudianteSeccion}</span>
      </div>
      <div class="result-student-info">
        <span class="result-student-label">Código Examen:</span>
        <span class="result-student-value">${codigoExamenActual || 'N/A'}</span>
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
        <td class="topic-name">${row.tema}</td>
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
      correctAnswerHtml = `<span class="correct-answer">Correcta: ${String.fromCharCode(97 + q.ans)}) ${correctAnswerText}</span>`;
      statusHtml = `<span class="result-status">${isCorrect ? '✓' : '✗'}</span>`;
    }

    const userAnswerLabel = userAnswer !== null ? `${String.fromCharCode(97 + userAnswer)}) ${q.opts[userAnswer]}` : 'Sin contestar';

    const resultItem = document.createElement('div');
    resultItem.className = `result-item ${resultClass}`;
    resultItem.innerHTML = `
      <div class="result-question-header">
        <span class="result-question-num">${q.numeroOriginal}.</span>
        <span class="result-question-topic">[${q.tema}]</span>
      </div>
      <div class="result-question-text">${q.q}</div>
      <div class="result-details">
        <span class="user-answer">Tu respuesta: ${userAnswerLabel}</span>
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

// Función para el PDF (genera datos de temas)
function generateTopicBreakdownForPDF() {
  return generateTopicBreakdown();
}

function generatePDF() {
  if (typeof jsPDF === 'undefined' && typeof window.jspdf === 'undefined') {
    const script = document.createElement('script');
    script.src = '/static/js/jspdf.min.js';
    script.onload = () => createPDF();
    script.onerror = () => alert('Error al cargar la biblioteca PDF.');
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
  doc.text("Examen Digital - Resultados", 105, 28, { align: "center" });

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
  const topicData = generateTopicBreakdownForPDF();
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
    doc.text("CTP Las Palmitas - Examen Digital", 20, 290);
    doc.text(new Date().toLocaleDateString(), 170, 290);
  }

  const filename = `resultados-${codigoExamenActual || 'examen'}-${estudianteNombre.replace(/\s+/g, '-')}-${new Date().toISOString().slice(0,10)}.pdf`;
  doc.save(filename);
}

function closeResults() {
  document.getElementById('results-overlay').classList.remove('active');
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
    const navItem = document.createElement('div');
    navItem.className = 'q-nav-item';
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
          <div class="theme-title">${tema}</div>
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

      const keys = ['a', 'b', 'c'];
      let optsHtml = q.opts.map((o, j) => `
        <div class="option-item" id="opt-${q.idx}-${j}" onclick="answer(${q.idx}, ${j})">
          <span class="option-key">${keys[j]}</span>
          <span class="option-text">${o}</span>
        </div>
      `).join('');
      card.innerHTML = `
        <div class="question-header">
          <div class="question-number">${q.numeroOriginal}</div>
          <div class="question-text">${q.q}</div>
        </div>
        <div class="options-list">${optsHtml}</div>
      `;
      sec.appendChild(card);
    });
    content.appendChild(sec);
  });
  updateSimpleStats();
}

function answer(qIdx, optIdx) {
  const wasAnswered = answers[qIdx] !== null;
  answers[qIdx] = optIdx;

  const card = document.getElementById('q' + qIdx);
  const navItem = document.getElementById('nav-' + qIdx);
  const opts = card.querySelectorAll('.option-item');

  opts.forEach((el, j) => {
    el.classList.remove('selected', 'disabled');
    if (j === optIdx) {
      el.classList.add('selected');
      // Ripple effect
      const rect = el.getBoundingClientRect();
      const x = ((optIdx / 3) * 100);
      el.style.setProperty('--ripple-x', x + '%');
      el.style.setProperty('--ripple-y', '50%');
    }
  });

  navItem.classList.add('answered');

  updateSimpleStats();
  saveToLocalStorage();
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
function startTimer() {
  duracionMinutos = examData.duracion_minutos || 60;
  tiempoRestanteSegundos = duracionMinutos * 60;

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
    }
  }, 1000);
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

  // Detener el timer si no se hizo ya
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  // Llamar submit
  submitExam();
}

// ========== SUBMIT EXAM ==========
function submitExam() {
  // Detener el timer si está corriendo
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  const unanswered = answers.filter(a => a === null).length;
  if (unanswered > 0) {
    document.getElementById('warning-message').textContent =
      `Tienes ${unanswered} preguntas sin contestar. ¿Deseas enviar el examen de todas formas?`;
    document.getElementById('warning-overlay').classList.add('active');
  } else {
    // Limpiar localStorage al enviar
    clearLocalStorage();
    showPasswordModal();
  }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  // Verificar si hay sesión guardada
  if (loadSession()) {
    // Hay sesión - ir a pantalla de código
    showCodeScreen();
  } else {
    // No hay sesión - mostrar login
    showLoginScreen();
  }

  // Event listeners para modales existentes
  document.getElementById('verify-btn').addEventListener('click', validatePassword);
  document.getElementById('teacher-password').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') validatePassword();
  });

  // Event listeners para login
  document.getElementById('login-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performLogin();
  });

  // Event listeners para código de examen
  document.getElementById('code-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startExam();
  });
});
