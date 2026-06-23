import asyncio
from playwright.async_api import async_playwright

async def main():
    url = 'https://sede.sepe.gob.es/portalSede/procedimientos-y-servicios/personas/proteccion-por-desempleo/cita-previa/cita-previa-solicitud.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)

        # Aceptar cookies
        try:
            btn = await page.query_selector('#onetrust-accept-btn-handler')
            if btn:
                await btn.click()
                await page.wait_for_timeout(2000)
        except:
            pass

        # Buscar todos los enlaces y botones de accion
        elementos = await page.evaluate('''
            () => {
                const links = [...document.querySelectorAll('a, button')]
                    .filter(el => el.offsetParent !== null)
                    .map(el => ({
                        tag: el.tagName,
                        text: el.innerText.trim().substring(0, 60),
                        href: el.href || null,
                        onclick: el.getAttribute("onclick") || null
                    }))
                    .filter(el => el.text.length > 0);
                return links;
            }
        ''')

        print("Enlaces y botones visibles:\n")
        for el in elementos:
            print(f"  [{el['tag']}] {el['text']}")
            if el['href']:
                print(f"         href: {el['href']}")
            if el['onclick']:
                print(f"         onclick: {el['onclick']}")

        # Buscar iframes
        iframes = await page.query_selector_all('iframe')
        print(f"\nIframes encontrados: {len(iframes)}")
        for iframe in iframes:
            src = await iframe.get_attribute('src')
            print(f"  iframe src: {src}")

        await page.wait_for_timeout(5000)
        await browser.close()

asyncio.run(main())
