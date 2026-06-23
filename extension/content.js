/**
 * Asistente Sedes Electrónicas — content script (Chrome MV3)
 *
 * Inyecta un botón flotante y un panel de chat en cualquier página.
 * Funcionalidades:
 *   - Consulta al backend FastAPI local (POST /consulta)
 *   - Detección automática del campo de formulario con foco
 *   - Dictado por voz (SpeechRecognition, es-ES) — botón mic
 *   - Lectura de respuestas en voz alta (SpeechSynthesis, es-ES) — toggle
 *
 * Toda la comunicación es loopback local; ningún dato sale del dispositivo.
 * Sección 5.6 del TFM — UNIR Máster en Inteligencia Artificial.
 */

const BACKEND_URL = 'http://localhost:8000';
const ID_PANEL    = 'ase-panel';
const ID_BOTON    = 'ase-boton-flotante';

// Estado global
let campoActivo    = null;
let panelAbierto   = false;
let servidorActivo = false;
let vozActiva      = true;
let escuchando     = false;

// SpeechRecognition
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition  = null;

if (SpeechRec) {
  recognition = new SpeechRec();
  recognition.lang            = 'es-ES';
  recognition.continuous      = false;
  recognition.interimResults  = false;
  recognition.maxAlternatives = 1;
}

// Crear DOM del panel
function crearPanel() {
  if (document.getElementById(ID_PANEL)) return;

  const boton = document.createElement('button');
  boton.id = ID_BOTON;
  boton.title = 'Asistente de trámites';
  boton.textContent = '🤖';
  boton.addEventListener('click', togglePanel);
  document.body.appendChild(boton);

  const panel = document.createElement('div');
  panel.id = ID_PANEL;
  panel.classList.add('ase-oculto');
  panel.innerHTML = `
    <div id="ase-cabecera">
      <span>Asistente de trámites</span>
      <button id="ase-voz-toggle" title="Activar/desactivar voz">🔊</button>
      <button id="ase-cerrar" title="Cerrar">✕</button>
    </div>
    <div id="ase-estado-servidor">Comprobando servidor…</div>
    <div id="ase-campo-activo"></div>
    <div id="ase-mensajes"></div>
    <form id="ase-formulario" autocomplete="off">
      <button id="ase-mic" type="button" title="Hablar">🎤</button>
      <textarea id="ase-input" rows="1"
        placeholder="¿En qué puedo ayudarte?"
        maxlength="500"></textarea>
      <button id="ase-enviar" type="submit" title="Enviar">➤</button>
    </form>
  `;
  document.body.appendChild(panel);

  document.getElementById('ase-cerrar').addEventListener('click', () => cerrarPanel());
  document.getElementById('ase-voz-toggle').addEventListener('click', toggleVoz);
  document.getElementById('ase-formulario').addEventListener('submit', (e) => { e.preventDefault(); enviarConsulta(); });
  document.getElementById('ase-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarConsulta(); }
  });
  document.getElementById('ase-mic').addEventListener('click', toggleDictado);

  comprobarServidor();
}

// Visibilidad
function togglePanel() { panelAbierto ? cerrarPanel() : abrirPanel(); }

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
  detenerDictado();
  window.speechSynthesis && window.speechSynthesis.cancel();
}

// Servidor
async function comprobarServidor() {
  const el = document.getElementById('ase-estado-servidor');
  if (!el) return;
  try {
    const res = await fetch(`${BACKEND_URL}/health`, { method: 'GET' });
    if (res.ok) {
      servidorActivo = true;
      el.textContent = '● Servidor activo — ejecución 100% local';
      el.className = 'ase-ok';
    } else throw new Error('status ' + res.status);
  } catch {
    servidorActivo = false;
    el.textContent = '⚠ Servidor no disponible — inicia backend.py';
    el.className = 'ase-error';
  }
}

// Campo con foco
document.addEventListener('focusin', (e) => {
  const el = e.target;
  if (!['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) return;
  if (el.closest('#ase-panel') || el.id === 'ase-input') return;

  let label = null;
  label = label || el.getAttribute('aria-label');
  if (!label && el.id) {
    const lbl = document.querySelector(`label[for="${el.id}"]`);
    if (lbl) label = lbl.innerText.trim();
  }
  if (!label) {
    const lblId = el.getAttribute('aria-labelledby');
    if (lblId) { const ref = document.getElementById(lblId); if (ref) label = ref.innerText.trim(); }
  }
  label = label || el.placeholder || el.name || el.id || null;
  campoActivo = label ? label.substring(0, 80) : null;

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
  setTimeout(() => {
    const activo = document.activeElement;
    if (!activo || !['INPUT', 'SELECT', 'TEXTAREA'].includes(activo.tagName)) {
      const indicador = document.getElementById('ase-campo-activo');
      if (indicador) indicador.classList.remove('ase-visible');
    }
  }, 200);
}, true);

// TTS
function toggleVoz() {
  vozActiva = !vozActiva;
  const btn = document.getElementById('ase-voz-toggle');
  if (btn) btn.textContent = vozActiva ? '🔊' : '🔇';
  if (!vozActiva) window.speechSynthesis && window.speechSynthesis.cancel();
}

function leerRespuesta(texto) {
  if (!vozActiva || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(texto);
  utt.lang  = 'es-ES';
  utt.rate  = 0.95;
  utt.pitch = 1.0;
  const voces = window.speechSynthesis.getVoices();
  const vozES = voces.find(v => v.lang.startsWith('es') && v.localService) ||
                voces.find(v => v.lang.startsWith('es'));
  if (vozES) utt.voice = vozES;
  window.speechSynthesis.speak(utt);
}

// STT
function toggleDictado() { escuchando ? detenerDictado() : iniciarDictado(); }

function iniciarDictado() {
  if (!recognition) {
    agregarMensaje('Tu navegador no soporta reconocimiento de voz.', 'sistema');
    return;
  }
  if (escuchando) return;
  escuchando = true;
  actualizarBotonMic(true);

  recognition.onresult = (e) => {
    const texto = e.results[0][0].transcript;
    const input = document.getElementById('ase-input');
    if (input) { input.value = texto; input.focus(); }
  };

  recognition.onerror = (e) => {
    console.warn('[ASE] SpeechRecognition error:', e.error);
    detenerDictado();
    if (e.error === 'not-allowed') {
      agregarMensaje('Permiso de micrófono denegado. Actívalo en la configuración del navegador.', 'sistema');
    }
  };

  recognition.onend = () => detenerDictado();

  try { recognition.start(); } catch (_) { detenerDictado(); }
}

function detenerDictado() {
  escuchando = false;
  actualizarBotonMic(false);
  try { recognition && recognition.stop(); } catch (_) {}
}

function actualizarBotonMic(activo) {
  const btn = document.getElementById('ase-mic');
  if (!btn) return;
  btn.textContent = activo ? '⏹' : '🎤';
  btn.title       = activo ? 'Detener dictado' : 'Hablar';
  btn.classList.toggle('ase-mic-activo', activo);
}

// Enviar consulta
async function enviarConsulta() {
  const inputEl  = document.getElementById('ase-input');
  const enviarEl = document.getElementById('ase-enviar');
  const pregunta = inputEl.value.trim();
  if (!pregunta) return;

  if (!servidorActivo) {
    agregarMensaje('El servidor no está disponible. Asegúrate de que backend.py está en ejecución.', 'sistema');
    return;
  }

  detenerDictado();
  agregarMensaje(pregunta, 'usuario');
  inputEl.value = '';
  enviarEl.disabled = true;

  const idPensando = agregarMensaje('Pensando…', 'pensando');

  try {
    const res = await fetch(`${BACKEND_URL}/consulta`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta, url: window.location.href, campo: campoActivo }),
    });

    eliminarMensaje(idPensando);
    if (!res.ok) throw new Error(`Error del servidor: ${res.status}`);

    const data = await res.json();
    agregarMensaje(data.respuesta, 'asistente');
    leerRespuesta(data.respuesta);

    if (data.pii_detected) {
      agregarMensaje('🔒 He detectado datos personales en tu mensaje y los he eliminado antes de procesarlo.', 'sistema');
    }

  } catch (err) {
    eliminarMensaje(idPensando);
    agregarMensaje(`Error al conectar con el asistente: ${err.message}`, 'sistema');
  } finally {
    enviarEl.disabled = false;
    inputEl.focus();
  }
}

// Mensajes
let _msgCounter = 0;

function agregarMensaje(texto, tipo) {
  const contenedor = document.getElementById('ase-mensajes');
  if (!contenedor) return null;
  const id  = `ase-msg-${++_msgCounter}`;
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

// Init
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', crearPanel);
} else {
  crearPanel();
}
