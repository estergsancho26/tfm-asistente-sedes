# -*- coding: utf-8 -*-
"""
Crawler del trámite "Programa de Turismo del IMSERSO" (Alta).
Scraping del formulario único — no requiere autenticación.

Ejecutar desde la raíz del proyecto:
    .venv\Scripts\python.exe scraper\imserso_crawler.py

Genera: data/graphs/imserso_completo.json
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

URL_ALTA = (
    'https://sede.imserso.gob.es/sedecdi'
    '?locale=es&sia=0994874&action=alta&representante=no&aut=no'
)
OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'graphs', 'imserso_completo.json'
)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def aceptar_cookies(page):
    for sel in [
        '#onetrust-accept-btn-handler',
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
        'button:has-text("Acepto")',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                print(f'  Cookies aceptadas: {sel}')
                await page.wait_for_timeout(1500)
                return
        except Exception:
            continue
    print('  (sin banner de cookies)')


async def extraer_nodos_formulario(page):
    """Extrae todos los campos interactivos visibles del formulario."""
    nodos = await page.evaluate('''
        () => {
            const campos = [];
            const inputs = document.querySelectorAll('input, select, textarea, button[type="button"], button[type="submit"]');

            for (const el of inputs) {
                // Solo visibles (excluyendo hidden)
                if (el.type === 'hidden') continue;
                if (el.offsetParent === null && el.type !== 'checkbox' && el.type !== 'radio') continue;

                // Buscar label asociado
                let label = null;
                if (el.id) {
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl) label = lbl.innerText.trim();
                }
                if (!label) label = el.getAttribute('aria-label') || el.placeholder || el.value || null;
                if (!label && el.tagName === 'BUTTON') label = el.innerText.trim();

                // Opciones de select
                let opciones = null;
                if (el.tagName === 'SELECT') {
                    opciones = [...el.options].map(o => o.text.trim()).filter(t => t.length > 0);
                }

                campos.push({
                    tag: el.tagName,
                    id: el.id || null,
                    name: el.getAttribute('name') || null,
                    type: el.type || null,
                    label: label ? label.substring(0, 120) : null,
                    required: el.required || false,
                    placeholder: el.placeholder || null,
                    opciones: opciones,
                });
            }
            return campos;
        }
    ''')
    return nodos


# ── Crawl principal ────────────────────────────────────────────────────────────

async def crawl_imserso():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='es-ES')
        page = await context.new_page()

        # ── PASO 1: formulario de alta ──────────────────────────────────────
        print('\n[PASO 1] Navegando al formulario de alta...')
        await page.goto(URL_ALTA, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)
        await aceptar_cookies(page)

        url_real = page.url
        titulo = await page.title()
        print(f'  URL: {url_real}')
        print(f'  Título: {titulo}')

        nodos_raw = await extraer_nodos_formulario(page)
        print(f'  Campos extraídos: {len(nodos_raw)}')

        # Convertir a formato grafo
        nodos_paso1 = []
        for n in nodos_raw:
            tipo = 'input'
            if n['tag'] == 'SELECT':
                tipo = 'select'
            elif n['tag'] == 'BUTTON':
                tipo = 'button'
            elif n['type'] == 'checkbox':
                tipo = 'checkbox'
            elif n['type'] == 'radio':
                tipo = 'radio'

            nodo = {
                'node_type': tipo,
                'label': n['label'],
                'html_id': n['id'],
                'html_name': n['name'],
                'required': n['required'],
                'visible': True,
                'input_type': n['type'],
                'placeholder': n['placeholder'],
                'help_text': None,
            }
            if n['opciones']:
                nodo['options'] = n['opciones']

            nodos_paso1.append(nodo)

        await browser.close()

    # ── Construir grafo ────────────────────────────────────────────────────
    grafo = {
        'tramite': 'Programa de Turismo del IMSERSO (Alta)',
        'url_inicio': 'https://sede.imserso.gob.es/procedimientos-servicios/turismo-termalismo-imserso',
        'total_pasos': 3,
        'pasos_scrapeados': 1,
        'pasos_inferidos': 2,
        'nota': 'Paso 1 scrapeado. Pasos 2-3 inferidos (preview + confirmación). No requiere autenticación.',
        'pasos': [
            {
                'url': url_real,
                'title': titulo,
                'step_num': 1,
                'breadcrumb': ['Inicio', 'Trámites y servicios', 'Turismo y termalismo', 'Alta de solicitud'],
                'seccion': 'Formulario de solicitud',
                'nodes': nodos_paso1,
            },
            {
                'url': 'https://sede.imserso.gob.es/sedecdi/app/tramite/turismo/preview.jsf',
                'title': 'Previsualización — IMSERSO Turismo',
                'step_num': 2,
                'breadcrumb': ['Inicio', 'Trámites y servicios', 'Turismo y termalismo', 'Previsualización'],
                'seccion': 'Confirmación de datos',
                'inferido': True,
                'nodes': [
                    {
                        'node_type': 'info',
                        'label': 'Pantalla de previsualización',
                        'help_text': (
                            'Antes de enviar definitivamente, el sistema muestra un resumen con todos los datos '
                            'introducidos. Revise que la información es correcta. '
                            'Si detecta algún error puede volver al formulario con el botón Modificar.'
                        ),
                    },
                    {'node_type': 'button', 'label': 'Confirmar y enviar',
                     'help_text': 'Confirma el envío definitivo. Se genera el número de expediente y el acuse de recibo.'},
                    {'node_type': 'button', 'label': 'Modificar',
                     'help_text': 'Vuelve al formulario para corregir datos antes del envío definitivo.'},
                ],
            },
            {
                'url': 'https://sede.imserso.gob.es/sedecdi/app/tramite/turismo/confirmation.jsf',
                'title': 'Solicitud registrada — IMSERSO Turismo',
                'step_num': 3,
                'breadcrumb': ['Inicio', 'Trámites y servicios', 'Turismo y termalismo', 'Confirmación'],
                'seccion': 'Acuse de recibo',
                'inferido': True,
                'nodes': [
                    {
                        'node_type': 'info',
                        'label': 'Resultado del envío',
                        'help_text': (
                            'Una vez enviada la solicitud, el sistema genera un número de expediente y un acuse de '
                            'recibo en PDF. La resolución (asignación de plazas) se notifica por el medio elegido. '
                            'El plazo de resolución es de varios meses tras el cierre del período de solicitud.'
                        ),
                    },
                    {'node_type': 'button', 'label': 'Descargar acuse de recibo (PDF)',
                     'help_text': 'Descarga el justificante del registro con el número de expediente asignado.'},
                ],
            },
        ],
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(grafo, f, ensure_ascii=False, indent=2)

    print(f'\nGuardado en: {OUTPUT_PATH}')
    total_nodos = sum(len(p['nodes']) for p in grafo['pasos'])
    print(f'Total nodos: {total_nodos} ({len(nodos_paso1)} scrapeados + inferidos)')


if __name__ == '__main__':
    asyncio.run(crawl_imserso())
