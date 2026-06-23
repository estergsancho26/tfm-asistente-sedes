# -*- coding: utf-8 -*-
"""
Diagnostico del tramite "Cita previa sanitaria - Comunidad de Madrid".
URL: https://www.comunidad.madrid/servicios/salud/cita-sanitaria

Ejecutar desde la raiz del proyecto:
    .venv\Scripts\python.exe scraper\madrid_salud_diagnostico.py
"""
import asyncio
from playwright.async_api import async_playwright

URL = 'https://www.comunidad.madrid/servicios/salud/cita-sanitaria'


async def volcar_texto(page, etiqueta, limite=3000):
    texto = await page.evaluate('() => document.body.innerText')
    print(f'\n=== Texto [{etiqueta}] (primeros {limite} chars) ===')
    print(texto.strip()[:limite])


async def volcar_elementos(page, etiqueta):
    elementos = await page.evaluate('''
        () => [...document.querySelectorAll('a, button, input, select, textarea, [role="button"]')]
            .filter(el => el.offsetParent !== null)
            .map(el => ({
                tag: el.tagName,
                id: el.id || null,
                name: el.getAttribute('name'),
                type: el.type || null,
                text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 100),
                href: el.href || null,
            }))
            .filter(el => el.text.length > 0 || el.id || el.name)
    ''')
    print(f'\n--- Elementos [{etiqueta}] ({len(elementos)}) ---')
    for el in elementos:
        print(f"  [{el['tag']}] id={el['id']} name={el['name']} type={el['type']} -> {el['text']}")
        if el['href'] and ('comunidad.madrid' in (el['href'] or '') or 'madrid.org' in (el['href'] or '')):
            print(f"         href: {el['href']}")

    iframes = await page.query_selector_all('iframe')
    if iframes:
        print(f'  Iframes: {len(iframes)}')
        for ifr in iframes:
            print(f"    src: {await ifr.get_attribute('src')}")


async def aceptar_cookies(page):
    for sel in [
        '#onetrust-accept-btn-handler',
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
        'button:has-text("Acepto")',
        '#didomi-notice-agree-button',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                print(f'Cookies aceptadas: {sel}')
                await page.wait_for_timeout(1500)
                return
        except Exception:
            continue
    print('(sin banner de cookies)')


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='es-ES')
        page = await context.new_page()

        # PASO 1: Landing page de cita sanitaria
        print(f'[PASO 1] Navegando a: {URL}')
        await page.goto(URL, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)
        await aceptar_cookies(page)

        print(f'URL actual: {page.url}')
        await volcar_texto(page, 'landing cita sanitaria')
        await volcar_elementos(page, 'landing cita sanitaria')

        # Buscar enlace/botón para pedir cita
        print('\n\n[ANALISIS] Buscando enlace de acceso al formulario de cita...')
        enlaces = await page.evaluate('''
            () => [...document.querySelectorAll('a')]
                .filter(a => a.offsetParent !== null)
                .map(a => ({text: a.innerText.trim(), href: a.href}))
                .filter(a => a.text.length > 2 && a.href.length > 0)
        ''')
        for e in enlaces:
            t = e['text'].lower()
            if any(kw in t for kw in ['cita', 'pedir', 'solicitar', 'acceder', 'entrar', 'medico', 'médico', 'primaria']):
                print(f"  -> '{e['text']}' | {e['href']}")

        print('\nDejo el navegador abierto 30s para inspeccion manual...')
        await page.wait_for_timeout(30000)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
