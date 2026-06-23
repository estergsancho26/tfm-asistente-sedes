# -*- coding: utf-8 -*-
"""
Diagnostico del formulario de Cita Previa Atención Primaria - Comunidad de Madrid.
URL real: https://www.citaprevia.sanidadmadrid.org/Forms/Acceso.aspx

Ejecutar desde la raiz del proyecto:
    .venv\Scripts\python.exe scraper\madrid_salud_diagnostico2.py
"""
import asyncio
from playwright.async_api import async_playwright

URL_PRIMARIA  = 'https://www.citaprevia.sanidadmadrid.org/Forms/Acceso.aspx'


async def volcar_texto(page, etiqueta, limite=3000):
    texto = await page.evaluate('() => document.body.innerText')
    print(f'\n=== Texto [{etiqueta}] (primeros {limite} chars) ===')
    print(texto.strip()[:limite])


async def volcar_elementos(page, etiqueta):
    elementos = await page.evaluate('''
        () => [...document.querySelectorAll('a, button, input, select, textarea, [role="button"], label')]
            .filter(el => el.offsetParent !== null || el.tagName === 'LABEL')
            .map(el => ({
                tag: el.tagName,
                id: el.id || null,
                name: el.getAttribute('name'),
                type: el.type || null,
                for: el.getAttribute('for') || null,
                text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 100),
                href: el.href || null,
            }))
            .filter(el => el.text.length > 0 || el.id || el.name)
    ''')
    print(f'\n--- Elementos [{etiqueta}] ({len(elementos)}) ---')
    for el in elementos:
        label_info = f' for={el["for"]}' if el['for'] else ''
        print(f"  [{el['tag']}] id={el['id']} name={el['name']} type={el['type']}{label_info} -> {el['text']}")

    iframes = await page.query_selector_all('iframe')
    if iframes:
        print(f'  Iframes: {len(iframes)}')
        for ifr in iframes:
            print(f"    src: {await ifr.get_attribute('src')}")


async def volcar_validaciones(page, etiqueta):
    """Busca mensajes de validación o requisitos de formato."""
    validaciones = await page.evaluate('''
        () => [...document.querySelectorAll('span[id*="validator"], span[id*="Valid"], div.error, .field-validation-error, .help-text, .hint')]
            .map(el => ({id: el.id, text: el.innerText.trim(), class: el.className}))
            .filter(el => el.text.length > 0)
    ''')
    if validaciones:
        print(f'\n--- Validaciones [{etiqueta}] ---')
        for v in validaciones:
            print(f"  id={v['id']} class={v['class']} -> {v['text'][:100]}")


async def aceptar_cookies(page):
    for sel in ['#onetrust-accept-btn-handler', 'button:has-text("Aceptar")', '#didomi-notice-agree-button']:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
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

        # ── PASO 1: Formulario de acceso (tarjeta + fecha + DNI) ─────────────
        print(f'[PASO 1] Navegando a: {URL_PRIMARIA}')
        await page.goto(URL_PRIMARIA, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)
        await aceptar_cookies(page)

        print(f'URL actual: {page.url}')
        await volcar_texto(page, 'acceso cita primaria')
        await volcar_elementos(page, 'acceso cita primaria')
        await volcar_validaciones(page, 'acceso cita primaria')

        print('\nDejo el navegador abierto 45s — rellena los datos de prueba si puedes y observa el siguiente paso...')
        await page.wait_for_timeout(45000)

        # ── PASO 2: después de enviar el acceso ──────────────────────────────
        print(f'\n[PASO 2] URL tras acceso: {page.url}')
        await volcar_texto(page, 'paso 2 tras acceso')
        await volcar_elementos(page, 'paso 2 tras acceso')

        print('\nDejo el navegador abierto 30s más...')
        await page.wait_for_timeout(30000)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
