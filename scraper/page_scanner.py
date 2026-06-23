from playwright.async_api import async_playwright, Page, ElementHandle
from dataclasses import dataclass, field, asdict
from typing import Optional
import asyncio
import json
import os

@dataclass
class UINode:
    node_type: str
    xpath: str
    label: str
    aria_label: Optional[str] = None
    aria_role: Optional[str] = None
    html_id: Optional[str] = None
    html_name: Optional[str] = None
    placeholder: Optional[str] = None
    required: bool = False
    visible: bool = True
    input_type: Optional[str] = None
    validation_pattern: Optional[str] = None
    help_text: Optional[str] = None

@dataclass
class PageSnapshot:
    url: str
    title: str
    step_num: int = 1
    breadcrumb: list = field(default_factory=list)
    nodes: list = field(default_factory=list)

async def get_xpath(page: Page, handle: ElementHandle) -> str:
    return await page.evaluate('''
        el => {
            const parts = [];
            while (el && el.nodeType === Node.ELEMENT_NODE) {
                let idx = 1;
                let sib = el.previousElementSibling;
                while (sib) {
                    if (sib.tagName === el.tagName) idx++;
                    sib = sib.previousElementSibling;
                }
                parts.unshift(el.tagName.toLowerCase() + "[" + idx + "]");
                el = el.parentElement;
            }
            return "/" + parts.join("/");
        }
    ''', handle)

async def resolve_label(page: Page, handle: ElementHandle) -> str:
    return await page.evaluate('''
        el => {
            if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
            if (el.id) {
                const lbl = document.querySelector("label[for='" + el.id + "']");
                if (lbl) return lbl.innerText.trim();
            }
            const lblId = el.getAttribute("aria-labelledby");
            if (lblId) {
                const ref = document.getElementById(lblId);
                if (ref) return ref.innerText.trim();
            }
            if (el.placeholder) return el.placeholder;
            return el.innerText ? el.innerText.trim() : "";
        }
    ''', handle)

async def resolve_help(page: Page, handle: ElementHandle) -> Optional[str]:
    return await page.evaluate('''
        el => {
            const descId = el.getAttribute("aria-describedby");
            if (descId) {
                const desc = document.getElementById(descId);
                if (desc) return desc.innerText.trim();
            }
            const parent = el.closest(".form-group, .field, fieldset");
            if (parent) {
                const hint = parent.querySelector(".hint, .help, small, .aviso");
                if (hint) return hint.innerText.trim();
            }
            return null;
        }
    ''', handle)

async def scan_page(page: Page, step_num: int = 1) -> PageSnapshot:
    url = page.url
    title = await page.title()

    breadcrumb = await page.evaluate('''
        () => [...document.querySelectorAll(
            "nav[aria-label='breadcrumb'] a, .breadcrumb a, ol.pasos li, .step-indicator li"
        )].map(el => el.innerText.trim()).filter(t => t.length > 0)
    ''')

    snapshot = PageSnapshot(url=url, title=title, step_num=step_num, breadcrumb=breadcrumb)

    # Botones
    buttons = await page.query_selector_all(
        'button, input[type="submit"], input[type="button"], '
        'a[role="button"], [role="button"]'
    )
    for btn in buttons:
        if not await btn.is_visible():
            continue
        label = await btn.get_attribute('value') or await resolve_label(page, btn)
        if not label:
            continue
        node = UINode(
            node_type='button',
            xpath=await get_xpath(page, btn),
            label=label,
            aria_label=await btn.get_attribute('aria-label'),
            html_id=await btn.get_attribute('id'),
            aria_role=await btn.get_attribute('role') or 'button',
        )
        snapshot.nodes.append(asdict(node))

    # Inputs y selects
    inputs = await page.query_selector_all(
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), '
        'textarea, select'
    )
    for inp in inputs:
        if not await inp.is_visible():
            continue
        input_type = await inp.get_attribute('type') or 'text'
        tag = await inp.evaluate('el => el.tagName.toLowerCase()')

        if tag == 'select':
            html_id = await inp.get_attribute('id')
            label = await page.evaluate(
                '''(id) => {
                    const lbl = document.querySelector("label[for='" + id + "']");
                    return lbl ? lbl.innerText.trim() : "";
                }''',
                html_id
            )
            options = await inp.evaluate('''
                el => [...el.options]
                    .map(o => o.text.trim())
                    .filter(t => t && t !== "--- Seleccionar ---")
            ''')
            input_type = 'select'
            help_text = 'Opciones: ' + ', '.join(options) if options else None
        else:
            html_id = await inp.get_attribute('id')
            label = await resolve_label(page, inp)
            help_text = await resolve_help(page, inp)
            options = []

        if not label:
            label = await inp.get_attribute('name') or html_id or 'sin etiqueta'

        node = UINode(
            node_type='input',
            xpath=await get_xpath(page, inp),
            label=label,
            html_id=html_id,
            html_name=await inp.get_attribute('name'),
            placeholder=await inp.get_attribute('placeholder'),
            required=await inp.get_attribute('required') is not None,
            input_type=input_type,
            validation_pattern=await inp.get_attribute('pattern'),
            help_text=help_text,
            aria_label=await inp.get_attribute('aria-label'),
        )
        snapshot.nodes.append(asdict(node))

    # Textos de ayuda
    helps = await page.query_selector_all(
        '.aviso, .nota, .instruccion, .help-block, [role="note"], '
        '.informacion-adicional, .alert, .aviso-informativo'
    )
    for h in helps:
        text = (await h.inner_text()).strip()
        if text and len(text) > 10:
            node = UINode(
                node_type='help_text',
                xpath=await get_xpath(page, h),
                label=text[:500],
            )
            snapshot.nodes.append(asdict(node))

    # Errores activos
    errors = await page.query_selector_all(
        '[role="alert"], .error, .alert-danger, .mensaje-error, [aria-live="assertive"]'
    )
    for err in errors:
        text = (await err.inner_text()).strip()
        if text and len(text) > 5:
            node = UINode(
                node_type='error',
                xpath=await get_xpath(page, err),
                label=text,
                aria_role='alert',
            )
            snapshot.nodes.append(asdict(node))

    return snapshot

async def main():
    url = 'https://citaprevia-sede.sepe.gob.es/citapreviasepe/?origen=sepe&codidioma=es'
    print(f'Escaneando: {url}')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='es-ES')
        page = await context.new_page()

        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)

        # Aceptar cookies si aparecen
        try:
            accept_btn = await page.query_selector(
                '#onetrust-accept-btn-handler, '
                'button:has-text("Aceptar todas"), '
                'button:has-text("Aceptar")'
            )
            if accept_btn:
                await accept_btn.click()
                print('Cookies aceptadas')
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # Esperar al formulario
        try:
            await page.wait_for_selector(
                '#datosCodigoPostal, #btnContinuar1, select, input',
                timeout=10000
            )
            print('Formulario detectado')
        except Exception:
            print('Formulario no detectado en 10s — escaneando lo que hay')

        snapshot = await scan_page(page, step_num=1)

        print(f'\nTitulo: {snapshot.title}')
        print(f'URL: {snapshot.url}')
        print(f'Nodos extraidos: {len(snapshot.nodes)}')
        for node in snapshot.nodes:
            print(f'  [{node["node_type"]}] {node["label"][:80]}')
            if node.get('help_text'):
                print(f'    ayuda: {node["help_text"][:60]}')

        os.makedirs('data/graphs', exist_ok=True)
        with open('data/graphs/sepe_paso1.json', 'w', encoding='utf-8') as f:
            json.dump(asdict(snapshot), f, ensure_ascii=False, indent=2)
        print(f'\nGuardado en data/graphs/sepe_paso1.json')

        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
