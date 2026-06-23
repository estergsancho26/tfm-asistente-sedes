# -*- coding: utf-8 -*-
"""
Crawler del tramite "Informe de tu vida laboral" en Import@ss (TGSS).

Ruta sin identificacion electronica (flujo mayores sin Cl@ve):
  Paso 1: Pagina informativa          -> boton-lanzamiento-operacion
  Paso 2: Modal ATRIA                 -> radio atria-opcion-no + btn-atria-continuar
  Paso 3: identificacion.seg-social.es (popup) -> formulario datos + biometria
  Paso 4: Verificacion biometrica     -> inferido (requiere camara real)
  Paso 5: Confirmacion y descarga PDF -> inferido

Ejecutar desde scraper/:
  python importass_crawler.py
"""
import asyncio, os, json
from playwright.async_api import async_playwright
from page_scanner import scan_page
from dataclasses import asdict

URL_LANDING = (
    'https://portal.seg-social.gob.es/wps/portal/importass/importass/'
    'Categorias/Vida+laboral+e+informes/Informes+sobre+tu+situacion+laboral/'
    'Informe+de+tu+vida+laboral'
)
TRAMITE = 'Informe de Vida Laboral (Import@ss)'
OUTPUT  = '../data/graphs/importass_completo.json'


async def aceptar_cookies(page):
    for sel in [
        '#onetrust-accept-btn-handler',
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(1500)
                return
        except Exception:
            continue


async def crawl_importass():
    pasos = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='es-ES')
        page    = await context.new_page()

        # ── PASO 1: Pagina informativa ─────────────────────────────────────
        print('PASO 1: Pagina informativa')
        await page.goto(URL_LANDING, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)
        await aceptar_cookies(page)

        snap1 = await scan_page(page, step_num=1)
        pasos.append(asdict(snap1))
        print(f'  {len(snap1.nodes)} nodos')

        # ── PASO 2: Modal "Elige tu metodo de identificacion" ──────────────
        print('PASO 2: Modal metodo de identificacion')
        boton = await page.query_selector('#boton-lanzamiento-operacion')
        if not boton:
            print('  ERROR: no se encontro #boton-lanzamiento-operacion')
            await browser.close()
            return
        await boton.click()
        await page.wait_for_timeout(3000)
        await page.wait_for_selector('#atria-opcion-no', timeout=8000, state='attached')

        snap2 = await scan_page(page, step_num=2)
        pasos.append(asdict(snap2))
        print(f'  {len(snap2.nodes)} nodos')

        # ── PASO 3: Popup identificacion.seg-social.es ─────────────────────
        print('PASO 3: Formulario datos de acceso (identificacion.seg-social.es)')

        # Marcar "Ninguno de los anteriores" via label (radio CSS-oculto)
        label_no = await page.query_selector('label[for="atria-opcion-no"]')
        if label_no and await label_no.is_visible():
            await label_no.click()
        else:
            opcion_no = await page.query_selector('#atria-opcion-no')
            await opcion_no.check(force=True, timeout=5000)
        await page.wait_for_timeout(500)

        # Escuchar popup ANTES del clic
        popup_future = asyncio.get_event_loop().create_future()
        context.once('page', lambda nueva: popup_future.set_result(nueva))

        await page.click('#btn-atria-continuar')

        try:
            nueva_pagina = await asyncio.wait_for(popup_future, timeout=15.0)
        except asyncio.TimeoutError:
            print('  ERROR: no aparecio popup en 15s.')
            await browser.close()
            return

        await nueva_pagina.wait_for_load_state('networkidle', timeout=20000)
        await nueva_pagina.wait_for_timeout(2000)

        snap3 = await scan_page(nueva_pagina, step_num=3)

        # Los drop-zones de foto de DNI no son <input type="file"> estandar;
        # se añaden manualmente con la informacion extraida del diagnostico.
        snap3.nodes.append({
            'node_type': 'input',
            'xpath': '',
            'label': 'Selfie del solicitante',
            'html_id': 'btnHacerFoto',
            'html_name': None,
            'placeholder': 'Haz la foto de frente, mostrando cara delantera del DNI/NIE',
            'required': True,
            'visible': True,
            'input_type': 'camera',
            'validation_pattern': None,
            'help_text': 'Se pedira permiso de camara al navegador.',
            'aria_label': None,
            'aria_role': None,
        })
        snap3.nodes.append({
            'node_type': 'input',
            'xpath': '',
            'label': 'Foto cara delantera del DNI/NIE',
            'html_id': 'upload-cara-frontal',
            'html_name': None,
            'placeholder': 'Suelta o pulsa para cargar la imagen de una cara',
            'required': True,
            'visible': True,
            'input_type': 'file',
            'validation_pattern': None,
            'help_text': 'Formato JPG o PNG. Cara delantera del documento.',
            'aria_label': None,
            'aria_role': None,
        })
        snap3.nodes.append({
            'node_type': 'input',
            'xpath': '',
            'label': 'Foto cara trasera del DNI/NIE',
            'html_id': 'upload-cara-trasera',
            'html_name': None,
            'placeholder': 'Suelta o pulsa para cargar la imagen de una cara',
            'required': True,
            'visible': True,
            'input_type': 'file',
            'validation_pattern': None,
            'help_text': 'Formato JPG o PNG. Cara trasera del documento.',
            'aria_label': None,
            'aria_role': None,
        })
        pasos.append(asdict(snap3))
        print(f'  {len(snap3.nodes)} nodos')

        # ── PASOS 4-5: inferidos (requieren biometria real) ─────────────────
        url_paso3 = nueva_pagina.url
        pasos_inferidos = [
            {
                'step_num': 4,
                'titulo': 'Verificacion biometrica',
                'descripcion': (
                    'El sistema compara el selfie con la foto del DNI/NIE para '
                    'verificar la identidad del solicitante. Requiere camara.'
                ),
            },
            {
                'step_num': 5,
                'titulo': 'Confirmacion y descarga del informe',
                'descripcion': (
                    'Tras superar la verificacion, se genera el informe de vida '
                    'laboral en PDF. Se puede descargar o recibir por correo electronico.'
                ),
            },
        ]
        for paso in pasos_inferidos:
            pasos.append({
                'url': url_paso3,
                'title': paso['titulo'],
                'step_num': paso['step_num'],
                'breadcrumb': [],
                'nodes': [{
                    'node_type': 'help_text',
                    'xpath': '',
                    'label': paso['descripcion'],
                    'aria_label': None, 'aria_role': None,
                    'html_id': None, 'html_name': None,
                    'placeholder': None, 'required': False,
                    'visible': True, 'input_type': None,
                    'validation_pattern': None,
                    'help_text': 'Paso inferido: no alcanzable sin biometria real.',
                }],
            })

        await browser.close()

    resultado = {
        'tramite': TRAMITE,
        'url_inicio': URL_LANDING,
        'total_pasos': len(pasos),
        'pasos_scrapeados': 3,
        'pasos_inferidos': 2,
        'nota': (
            'Pasos 1-3 scrapeados. Paso 3 en dominio identificacion.seg-social.es '
            '(se abre como popup). Pasos 4-5 inferidos: requieren biometria real.'
        ),
        'pasos': pasos,
    }

    os.makedirs('../data/graphs', exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f'\nTotal pasos: {len(pasos)} (3 scrapeados + 2 inferidos)')
    print(f'Guardado en {OUTPUT}')
    return resultado


if __name__ == '__main__':
    asyncio.run(crawl_importass())
