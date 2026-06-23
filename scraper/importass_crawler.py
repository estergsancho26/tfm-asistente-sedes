# -*- coding: utf-8 -*-
"""
Crawler para el tramite "Informe de tu vida laboral" del portal Import@ss.

Cubre los pasos confirmados por exploracion (pagina informativa + eleccion
de metodo de identificacion). Los pasos siguientes -la rama "Ninguno de los
anteriores", que pide datos personales, selfie y foto del documento- no se
han podido inspeccionar todavia (requieren JS, no visibles via web_fetch).

Ejecutar primero scraper/importass_diagnostico.py y completar este crawler
con los selectores reales que aparezcan, igual que se hizo con el SEPE
(diagnostico.py / debug_*.py -> tramite_crawler.py).

Ejecutar con: python scraper/importass_crawler.py
"""
import asyncio
from playwright.async_api import async_playwright
from page_scanner import scan_page
from dataclasses import asdict
import json, os

URL = (
    'https://portal.seg-social.gob.es/wps/portal/importass/importass/'
    'Categorias/Vida+laboral+e+informes/Informes+sobre+tu+situacion+laboral/'
    'Informe+de+tu+vida+laboral'
)


async def aceptar_cookies(page):
    candidatos = [
        '#onetrust-accept-btn-handler',
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
    ]
    for selector in candidatos:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue


async def crawl_importass():
    pasos = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(URL, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)
        await aceptar_cookies(page)

        # PASO 1: pagina informativa "Informe de tu vida laboral"
        print('PASO 1: pagina informativa')
        snap = await scan_page(page, step_num=1)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')

        boton_consultar = await page.query_selector('text=Consultar vida laboral')
        if not boton_consultar:
            print('No se encontro el boton "Consultar vida laboral". Abortando.')
            await browser.close()
            return None

        await boton_consultar.click()
        await page.wait_for_timeout(3000)
        await aceptar_cookies(page)

        # PASO 2: Elige tu metodo de identificacion
        print('PASO 2: Elige tu metodo de identificacion')
        snap = await scan_page(page, step_num=2)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')

        # TODO: completar con scraper/importass_diagnostico.py.
        # Rama pendiente: elegir "Ninguno de los anteriores" -> Continuar ->
        # formulario de datos personales + selfie + foto del documento.
        # No se implementa a ciegas para no inventar selectores que no
        # se han verificado contra el DOM real.
        print('\nPendiente: completar pasos 3+ (rama sin Cl@ve) con el resultado de importass_diagnostico.py')

        await browser.close()

    resultado = {
        'tramite': 'Informe de tu vida laboral (Import@ss)',
        'url_inicio': URL,
        'total_pasos': len(pasos),
        'pasos_scrapeados': len(pasos),
        'pasos_inferidos': 0,
        'nota': 'Scraping parcial: pasos 3+ (verificacion sin Cl@ve) pendientes de completar tras el diagnostico.',
        'pasos': pasos,
    }

    os.makedirs('../data/graphs', exist_ok=True)
    output = '../data/graphs/importass_completo.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f'\nTotal pasos capturados: {len(pasos)}')
    print(f'Guardado en {output}')
    return resultado


if __name__ == '__main__':
    asyncio.run(crawl_importass())
