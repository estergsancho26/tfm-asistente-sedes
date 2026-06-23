# -*- coding: utf-8 -*-
"""
Script de diagnostico para el tramite "Informe de tu vida laboral" en el
portal Import@ss (Tesoreria General de la Seguridad Social).

Sigue el mismo patron que scraper/diagnostico.py (usado originalmente para
explorar la sede del SEPE): navega, acepta cookies, vuelca los elementos
interactivos visibles y detecta iframes, ANTES de escribir el crawler
definitivo (importass_crawler.py).

A diferencia del SEPE (una SPA con todo en una sola URL), Import@ss es un
portal con paginas informativas normales hasta llegar a "Consultar vida
laboral", donde aparece la pantalla "Elige tu metodo de identificacion"
(Cl@ve/certificado vs. "Ninguno de los anteriores"). Ese punto es justo el
que no se puede inspeccionar con web_fetch (requiere JS), de ahi este script.

Ejecutar con: python scraper/importass_diagnostico.py
y pegar la salida completa para poder escribir el crawler final.
"""
import asyncio
from playwright.async_api import async_playwright

URL = (
    'https://portal.seg-social.gob.es/wps/portal/importass/importass/'
    'Categorias/Vida+laboral+e+informes/Informes+sobre+tu+situacion+laboral/'
    'Informe+de+tu+vida+laboral'
)


async def volcar_texto(page, etiqueta: str, limite: int = 3000):
    """Vuelca el texto visible de la pagina, para leer preguntas/etiquetas
    de un modal que volcar_elementos() no captura (solo mira a, button,
    input, select)."""
    texto = await page.evaluate('() => document.body.innerText')
    texto = texto.strip()
    print(f'\n=== Texto visible [{etiqueta}] (primeros {limite} caracteres) ===')
    print(texto[:limite])


async def volcar_iframes_detalle(page):
    """Intenta volcar elementos interactivos dentro de cada iframe visible."""
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            elementos = await frame.evaluate('''
                () => [...document.querySelectorAll('a, button, input, select, [role="button"]')]
                    .filter(el => el.offsetParent !== null)
                    .map(el => ({
                        tag: el.tagName,
                        id: el.id || null,
                        type: el.type || null,
                        text: (el.innerText || el.value || el.placeholder || '').trim().substring(0, 80),
                    }))
                    .filter(el => el.text.length > 0 || el.id)
            ''')
            if elementos:
                print(f'\n  --- Elementos dentro del iframe {frame.url} ---')
                for el in elementos:
                    print(f"    [{el['tag']}] id={el['id']} type={el['type']} -> {el['text']}")
        except Exception as e:
            print(f'  (no se pudo leer el iframe {frame.url}: {e})')


async def volcar_elementos(page, etiqueta: str):
    elementos = await page.evaluate('''
        () => [...document.querySelectorAll('a, button, input, select, [role="button"]')]
            .filter(el => el.offsetParent !== null)
            .map(el => ({
                tag: el.tagName,
                id: el.id || null,
                name: el.getAttribute('name'),
                type: el.type || null,
                role: el.getAttribute('role'),
                text: (el.innerText || el.value || el.placeholder || '').trim().substring(0, 80),
                href: el.href || null,
            }))
            .filter(el => el.text.length > 0 || el.id || el.name)
    ''')
    print(f'\n--- Elementos visibles [{etiqueta}] ({len(elementos)}) ---')
    for el in elementos:
        print(f"  [{el['tag']}] id={el['id']} name={el['name']} type={el['type']} -> {el['text']}")
        if el['href']:
            print(f"         href: {el['href']}")

    iframes = await page.query_selector_all('iframe')
    if iframes:
        print(f'  Iframes encontrados: {len(iframes)}')
        for iframe in iframes:
            print(f"    src: {await iframe.get_attribute('src')}")


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
                print(f'Cookies aceptadas con selector: {selector}')
                await page.wait_for_timeout(1500)
                return
        except Exception:
            continue
    print('Aviso: no se encontro boton de cookies (puede que no haya banner, o el selector no coincide).')


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='es-ES')
        page = await context.new_page()

        print(f'Navegando a: {URL}')
        await page.goto(URL, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)

        await aceptar_cookies(page)
        await volcar_elementos(page, 'pagina informativa')

        # Paso 1: pulsar "Consultar vida laboral"
        boton_consultar = await page.query_selector('text=Consultar vida laboral')
        if not boton_consultar:
            print('\nNo se encontro el boton "Consultar vida laboral". Revisa manualmente la pagina.')
            await page.wait_for_timeout(15000)
            await browser.close()
            return

        print('\nPulsando "Consultar vida laboral"...')
        await boton_consultar.click()
        await page.wait_for_timeout(3000)
        print(f'URL tras el clic: {page.url}')
        await aceptar_cookies(page)
        await volcar_texto(page, 'modal tras Consultar vida laboral')
        await volcar_elementos(page, 'tras Consultar vida laboral')

        # Paso 2: el modal usa un radio #atria-opcion-no / #atria-opcion-si,
        # no un enlace de texto "Ninguno de los anteriores" (ese texto solo
        # aparecia en el HTML estatico via web_fetch, el DOM real usa otra
        # redaccion). Se selecciona "no" explicitamente por id.
        opcion_no = await page.query_selector('#atria-opcion-no')
        if opcion_no:
            print('\nMarcando radio #atria-opcion-no...')
            # El input nativo suele estar oculto (radio "custom-styled" via
            # CSS); se intenta primero el label asociado, y si no existe o
            # falla, se fuerza el check del input y se disparan los eventos
            # change/click por si el framework de la pagina escucha en el
            # input directamente.
            marcado = False
            try:
                label = await page.query_selector('label[for="atria-opcion-no"]')
                if label and await label.is_visible():
                    await label.click()
                    marcado = True
                    print('  Marcado via label[for="atria-opcion-no"]')
            except Exception as e:
                print(f'  No se pudo clicar el label: {e}')

            if not marcado:
                try:
                    await opcion_no.check(force=True, timeout=5000)
                    marcado = True
                    print('  Marcado via check(force=True) sobre el input')
                except Exception as e:
                    print(f'  check(force=True) tambien fallo: {e}')

            # Disparar eventos manualmente como red de seguridad adicional.
            try:
                await page.evaluate('''
                    () => {
                        const el = document.getElementById('atria-opcion-no');
                        if (el) {
                            el.checked = true;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            el.dispatchEvent(new Event('click', {bubbles: true}));
                        }
                    }
                ''')
            except Exception as e:
                print(f'  No se pudo disparar eventos manualmente: {e}')

            await page.wait_for_timeout(1000)
            estado_checked = await page.evaluate(
                "() => document.getElementById('atria-opcion-no')?.checked"
            )
            print(f'  Estado final de #atria-opcion-no.checked: {estado_checked}')

            boton_continuar = await page.query_selector('#btn-atria-continuar')
            if boton_continuar:
                print('Pulsando #btn-atria-continuar...')
                await boton_continuar.click()
                await page.wait_for_timeout(3000)
            else:
                print('No se encontro #btn-atria-continuar.')

            print(f'URL tras continuar: {page.url}')
            await volcar_texto(page, 'tras marcar "no" y continuar')
            await volcar_elementos(page, 'tras marcar "no" y continuar')
            await volcar_iframes_detalle(page)
        else:
            print('\nNo se encontro el radio #atria-opcion-no en esta pantalla.')
            print('Puede que el modal use otros ids: revisa el texto volcado arriba.')

        print('\nDejo el navegador abierto 25s para inspeccion manual (revisa la ventana de Chrome)...')
        await page.wait_for_timeout(25000)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
