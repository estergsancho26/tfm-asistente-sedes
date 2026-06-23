# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright
from page_scanner import scan_page
from dataclasses import asdict
import json, os

DNI_SINTETICO = '00000000T'

async def main():
    url = 'https://citaprevia-sede.sepe.gob.es/citapreviasepe/?origen=sepe&codidioma=es'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)

        pasos = []

        # PASO 1: CP y tramite
        print('PASO 1')
        await page.mouse.click(768, 192)
        await page.wait_for_timeout(1500)
        search = await page.query_selector('.select2-search__field')
        await search.type('28001', delay=150)
        await page.wait_for_timeout(4000)
        await page.select_option('#comboNivelServicio2', index=1)
        await page.wait_for_timeout(2000)
        snap = await scan_page(page, step_num=1)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')
        await page.click('#btnContinuar1')
        await page.wait_for_timeout(3000)

        # PASO 2: NIF/NIE
        print('PASO 2')
        await page.wait_for_selector('#inputDNI', timeout=8000)
        snap = await scan_page(page, step_num=2)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')
        await page.fill('#inputDNI', DNI_SINTETICO)
        await page.wait_for_timeout(1000)
        await page.click('#btnContinuar1')
        await page.wait_for_timeout(3000)

        # PASO 3: bifurcacion — elegir SOLO SEPE
        print('PASO 3 — bifurcacion')
        await page.wait_for_selector('#btnContinuar11', timeout=8000)
        snap = await scan_page(page, step_num=3)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')
        print('  Eligiendo SOLO SEPE')
        await page.click('#btnContinuar11')
        await page.wait_for_timeout(4000)

        # PASO 4
        print('PASO 4')
        snap = await scan_page(page, step_num=4)
        pasos.append(asdict(snap))
        print(f'  {len(snap.nodes)} nodos')
        for n in snap.nodes:
            print(f'    [{n["node_type"]}] {n["label"][:70]}')

        campos = await page.evaluate('''
            () => [...document.querySelectorAll("input,select,button,label,h2,h3,p,table")]
                .filter(el => el.offsetParent !== null)
                .map(el => ({
                    tag: el.tagName, id: el.id,
                    text: (el.innerText || el.value || el.placeholder || "").trim().substring(0,100)
                }))
                .filter(el => el.text.length > 0)
        ''')
        print(f'\n  Elementos paso 4 ({len(campos)}):')
        for el in campos:
            print(f'    [{el["tag"]}] id={el["id"]} → {el["text"]}')

        os.makedirs('../data/graphs', exist_ok=True)
        with open('../data/graphs/sepe_debug.json', 'w', encoding='utf-8') as f:
            json.dump(pasos, f, ensure_ascii=False, indent=2)
        print('\nGuardado en data/graphs/sepe_debug.json')

        await page.wait_for_timeout(10000)
        await browser.close()

asyncio.run(main())
