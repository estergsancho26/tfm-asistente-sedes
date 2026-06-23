# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright, Page
from page_scanner import scan_page
from dataclasses import asdict
import json, os

DATOS = {
    'codigo_postal': '28001',
    'dni': '00000000T',
}

async def crawl_sepe():
    url = 'https://citaprevia-sede.sepe.gob.es/citapreviasepe/?origen=sepe&codidioma=es'
    pasos = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)

        # PASO 1: Eleccion de tramite
        print('PASO 1: Eleccion de tramite')
        snap = await scan_page(page, step_num=1)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')

        await page.mouse.click(768, 192)
        await page.wait_for_timeout(1500)
        search = await page.query_selector('.select2-search__field')
        await search.type(DATOS['codigo_postal'], delay=150)
        await page.wait_for_timeout(4000)
        await page.select_option('#comboNivelServicio2', index=1)
        await page.wait_for_timeout(2000)
        await page.click('#btnContinuar1')
        await page.wait_for_timeout(3000)

        # PASO 2: NIF/NIE
        print('PASO 2: NIF/NIE')
        await page.wait_for_selector('#inputDNI', timeout=8000)
        snap = await scan_page(page, step_num=2)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')

        await page.fill('#inputDNI', DATOS['dni'])
        await page.wait_for_timeout(1000)
        await page.click('#btnContinuar1')
        await page.wait_for_timeout(3000)

        # PASO 3: Bifurcacion
        print('PASO 3: Bifurcacion SEPE/AMBOS')
        await page.wait_for_selector('#btnContinuar11', timeout=8000)
        snap = await scan_page(page, step_num=3)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')

        await page.click('#btnContinuar11')
        await page.wait_for_timeout(4000)

        # PASO 4: Canal y oficina
        print('PASO 4: Canal y oficina (limite con DNI sintetico)')
        await page.wait_for_selector('#comboCanales', timeout=8000)
        snap = await scan_page(page, step_num=4)

        # Enriquecer con texto informativo de la pantalla
        texto_info = await page.evaluate('''
            () => [...document.querySelectorAll("p,h2,h3,span.pestana0")]
                .filter(el => el.offsetParent !== null && el.innerText.trim().length > 10)
                .map(el => el.innerText.trim())
        ''')
        snap.nodes.append({
            'node_type': 'help_text',
            'xpath': '/html/body',
            'label': ' '.join(texto_info[:3])[:500],
            'aria_label': None, 'aria_role': None, 'html_id': None,
            'html_name': None, 'placeholder': None, 'required': False,
            'visible': True, 'input_type': None, 'validation_pattern': None,
            'help_text': 'Pantalla de seleccion de canal y oficina con mapa'
        })
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')

        # Pasos 5-8 conocidos por estructura del breadcrumb
        pasos_conocidos = [
            {'step_num': 5, 'titulo': 'Validacion', 'descripcion': 'Verificacion de datos antes de seleccionar fecha'},
            {'step_num': 6, 'titulo': 'Dia y hora de la cita', 'descripcion': 'Calendario para seleccionar fecha y hora disponible'},
            {'step_num': 7, 'titulo': 'Datos personales', 'descripcion': 'Nombre, apellidos, telefono y email de contacto'},
            {'step_num': 8, 'titulo': 'Cita previa', 'descripcion': 'Confirmacion y resguardo de la cita concertada'},
        ]
        for p_conocido in pasos_conocidos:
            pasos.append({
                'url': url,
                'title': p_conocido['titulo'],
                'step_num': p_conocido['step_num'],
                'breadcrumb': [],
                'nodes': [{
                    'node_type': 'help_text',
                    'xpath': '',
                    'label': p_conocido['descripcion'],
                    'aria_label': None, 'aria_role': None, 'html_id': None,
                    'html_name': None, 'placeholder': None, 'required': False,
                    'visible': True, 'input_type': None,
                    'validation_pattern': None, 'help_text': 'Paso no alcanzable con DNI sintetico'
                }]
            })

        await browser.close()

    resultado = {
        'tramite': 'Cita Previa SEPE',
        'url_inicio': url,
        'total_pasos': len(pasos),
        'pasos_scrapeados': 4,
        'pasos_inferidos': 4,
        'nota': 'Pasos 5-8 inferidos del breadcrumb. DNI sintetico bloquea avance en paso 4.',
        'pasos': pasos
    }

    os.makedirs('../data/graphs', exist_ok=True)
    output = '../data/graphs/sepe_completo.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f'\nTotal pasos capturados: {len(pasos)} (4 reales + 4 inferidos)')
    print(f'Guardado en {output}')
    return resultado

if __name__ == '__main__':
    asyncio.run(crawl_sepe())
