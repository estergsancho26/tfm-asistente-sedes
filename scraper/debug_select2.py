# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright

async def main():
    url = 'https://citaprevia-sede.sepe.gob.es/citapreviasepe/?origen=sepe&codidioma=es'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)

        # Paso 1: CP via select2
        await page.mouse.click(768, 192)
        await page.wait_for_timeout(1500)
        search = await page.query_selector('.select2-search__field')
        await search.type('28001', delay=150)
        await page.wait_for_timeout(4000)

        # Seleccionar tramite en comboNivelServicio2
        tramite = 'He finalizado un trabajo: acceso o reanudación de prestación o subsidio'
        print(f'Seleccionando tramite: {tramite[:50]}...')
        await page.select_option('#comboNivelServicio2', index=1)
        await page.wait_for_timeout(2000)

        valor = await page.evaluate(
            '() => document.querySelector("#comboNivelServicio2")?.value'
        )
        print(f'Tramite seleccionado, valor: {valor}')

        # Pulsar Continuar
        btn = await page.query_selector('#btnContinuar1')
        if btn:
            print('Pulsando Continuar...')
            await btn.click()
            await page.wait_for_timeout(4000)
            print(f'Nueva URL: {page.url}')
            print(f'Titulo: {await page.title()}')

            # Ver paso 2
            campos = await page.evaluate('''
                () => [...document.querySelectorAll("input,select,button,label,h2,h3,p")]
                    .filter(el => el.offsetParent !== null)
                    .map(el => ({
                        tag: el.tagName,
                        id: el.id,
                        type: el.type || null,
                        text: (el.innerText || el.value || el.placeholder || "").trim().substring(0,80)
                    }))
                    .filter(el => el.text.length > 0)
            ''')
            print(f'\nPASO 2 elementos ({len(campos)}):')
            for el in campos:
                print(f'  [{el["tag"]}] id={el["id"]} → {el["text"]}')

        await page.wait_for_timeout(10000)
        await browser.close()

asyncio.run(main())
