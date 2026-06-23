/**
 * Asistente Sedes Electrónicas — content script (Chrome MV3)
 *
 * Inyecta un botón flotante y un panel de chat en cualquier página.
 * Cuando el usuario envía una consulta:
 *   1. Detecta la URL activa y el campo del formulario con el foco.
 *   2. Envía POST a http://localhost:8000/consulta con {pregunta, url, campo}.
 *   3. Muestra la respuesta del asistente en el panel.
 *
 * Toda la comunicación es loopback local; ningún dato sale del dispositivo.
 * Sección 5.6 del TFM — UNIR Máster en Inteligencia Artificial.
 */

const BACKEND_URL = 'http://localhost:8000';
const ID_PANEL    = 'ase-panel';
const ID_BOTON    = 'ase-boton-flotante';

// ── Estado global ────────────────────────────────────────────────────────────
let campoActivo     = null;   // label semántica del campo con foco
let panelAbierto    = false;
let servidorActivo  = false;

// ── Crear DOM del panel ───────────────────────────────────────────────────────
function crearPanel() {
  if (document.getElementById(ID_PANEL)) return;

  // Botón flotante
  const boton = document.createElement('button');
  boton.id = ID_BOTON;
  boton.title = 'Asistente de trámites';
  boton.textContent = '🤖';
  boton.addEventListener('click', togglePanel);
  document.body.appendChild(boton);

  // Panel
  const panel = document.createElement('div');
  panel.id = ID_PANEL;
  panel.classList.add('ase-oculto');
  panel.innerHTML = `
    <div id="ase-cabecera">
      <span>Asistente de trámites</span>
      <button id="ase-cerrar" title="Cerrar">✕</button>
    </div>
    <div id="ase-estado-servidor">Comprobando servidor…</div>
    <div id="ase-campo-activo"></div>
    <div id="ase-mensajes"></div>
    <form id="ase-formulario" autocomplete="off">
      <textarea id="ase-input" rows="1"
        placeholder="¿En qué puedo ayudarte?"
        maxlength="500"></textarea>
      <button id="ase-enviar" type="submit" title="Enviar">➤</button>
    </form>
  `;
  document.body.appendChild(panel);

  // Eventos
  document.getElementById('ase-cerrar')
    .addEventListener('click', () => cerrarPanel());

  document.getElementById('ase-formulario')
    .addEventListener('submit', (e) => {
      e.preventDefault();
      enviarConsulta();
    });

  // Enter envía, Shift+Enter añade línea
  document.getElementById('ase-input')
    .addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        enviarConsulta();
      }
    });

  comprobarServidor();
}

// ── Visibilidad del panel ────────────────────────────────────────────────────
function togglePanel() {
  panelAbierto ? cerrarPanel() : abrirPanel();
}

function abrirPanel() {
  const panel = document.getElementById(ID_PANEL);
  if (!panel) return;
  panel.classList.remove('ase-oculto');
  panelAbierto = true;
  document.getElementById('ase-input').focus();
  if (!servidorActivo) comprobarServidor();
}

function cerrarPanel() {
  const panel = document.getElementById(ID_PANEL);
  if (!panel) return;
  panel.classList.add('ase-oculto');
  panelAbierto = false;
}

// ── Comprobar que el backend está activo ─────────────────────────────────────
async function comprobarServidor() {
  const el = document.getElementById('ase-estado-servidor');
  if (!el) return;
  try {
    const res = await fetch(`${BACKEND_URL}/health`, { method: 'GET' });
    if (res.ok) {
      servidorActivo = true;
      el.textContent = '● Servidor activo — ejecución 100% local';
      el.className = 'ase-ok';
    } else {
      throw new Error('status ' + res.status);
    }
  } catch {
    servidorActivo = false;
    el.textContent = '⚠ Servidor no disponible — inicia backend.py';
    el.className = 'ase-error';
  }
}

// ── Detección del campo con foco ─────────────────────────────────────────────
document.addEventListener('focusin', (e) => {
  const el = e.target;
  if (!['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) return;
  // Ignorar los propios elementos del panel del asistente
  if (el.closest('#ase-panel') || el.id === 'ase-input') return;

  // Intentar obtener la etiqueta semántica del campo
  let label = null;

  // 1. aria-label
  label = label || el.getAttribute('aria-label');

  // 2. <label for="id">
  if (!label && el.id) {
    const lbl = document.querySelector(`label[for="${el.id}"]`);
    if (lbl) label = lbl.innerText.trim();
  }

  // 3. aria-labelledby
  if (!label) {
    const lblId = el.getAttribute('aria-labelledby');
    if (lblId) {
      const ref = document.getElementById(lblId);
      if (ref) label = ref.innerText.trim();
    }
  }

  // 4. placeholder
  label = label || el.placeholder || el.name || el.id || null;

  campoActivo = label ? label.substring(0, 80) : null;

  // Mostrar campo activo en el panel si está abierto
  const indicador = document.getElementById('ase-campo-activo');
  if (indicador) {
    if (campoActivo) {
      indicador.textContent = `📌 Campo activo: ${campoActivo}`;
      indicador.classList.add('ase-visible');
    } else {
      indicador.classList.remove('ase-visible');
    }
  }
}, true);

document.addEventListener('focusout', () => {
  // Pequeño retraso para no perder el campo si el usuario hace clic en el panel
  setTimeout(() => {
    const activo = document.activeElement;
    if (!activo || !['INPUT', 'SELECT', 'TEXTAREA'].includes(activo.tagName)) {
      const indicador = document.getElementById('ase-campo-activo');
      if (indicador) indicador.classList.remove('ase-visible');
      // Nota: mantenemos campoActivo en memoria para la siguiente consulta
    }
  }, 200);
}, true);

// ── Enviar consulta al backend ───────────────────────────────────────────────
async function enviarConsulta() {
  const inputEl  = document.getElementById('ase-input');
  const enviarEl = document.getElementById('ase-enviar');
  const pregunta = inputEl.value.trim();
  if (!pregunta) return;

  if (!servidorActivo) {
    agregarMensaje('El servidor no está disponible. Asegúrate de que backend.py está en ejecución.', 'sistema');
    return;
  }

  // Mostrar mensaje del usuario
  agregarMensaje(pregunta, 'usuario');
  inputEl.value = '';
  enviarEl.disabled = true;

  // Indicador de carga
  const idPensando = agregarMensaje('Pensando…', 'pensando');

  try {
    const res = await fetch(`${BACKEND_URL}/consulta`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pregunta: pregunta,
        url:      window.location.href,
        campo:    campoActivo,
      }),
    });

    eliminarMensaje(idPensando);

    if (!res.ok) {
      throw new Error(`Error del servidor: ${res.status}`);
    }

    const data = await res.json();
    agregarMensaje(data.respuesta, 'asistente');

    // Aviso si se detectó PII (sin mostrar qué dato era)
    if (data.pii_detected) {
      agregarMensaje(
        '🔒 He detectado datos personales en tu mensaje y los he eliminado antes de procesarlo.',
        'sistema'
      );
    }

  } catch (err) {
    eliminarMensaje(idPensando);
    agregarMensaje(`Error al conectar con el asistente: ${err.message}`, 'sistema');
  } finally {
    enviarEl.disabled = false;
    inputEl.focus();
  }
}

// ── Utilidades de mensajes ───────────────────────────────────────────────────
let _msgCounter = 0;

function agregarMensaje(texto, tipo) {
  const contenedor = document.getElementById('ase-mensajes');
  if (!contenedor) return null;

  const id = `ase-msg-${++_msgCounter}`;
  const div = document.createElement('div');
  div.id = id;
  div.className = `ase-msg ase-msg-${tipo}`;
  div.textContent = texto;
  contenedor.appendChild(div);
  contenedor.scrollTop = contenedor.scrollHeight;
  return id;
}

function eliminarMensaje(id) {
  if (!id) return;
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Inicializar cuando el DOM esté listo ─────────────────────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', crearPanel);
} else {
  crearPanel();
}
