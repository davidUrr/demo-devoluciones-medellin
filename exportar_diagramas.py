"""Exporta AS-IS y TO-BE como SVG estático (colores por fase) en salidas/,
para documentos y presentaciones. Si Playwright está instalado, también
genera PNG."""
import os
import pathlib

import bpmn_layout as bl
import proceso as p

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDAS = os.path.join(AQUI, 'salidas')


def exportar():
    os.makedirs(SALIDAS, exist_ok=True)
    rutas = []
    for modo, archivo in (('AS-IS', 'AS-IS.bpmn'), ('TO-BE', 'TO-BE.bpmn')):
        layout = bl.parse_bpmn_di(os.path.join(AQUI, archivo))
        buckets = bl.construir_bucket_por_nodo({e: p.nodo(e, modo) for e in p.ETAPAS})
        svg = bl._construir_svg_estatico(layout, buckets, modo.lower().replace('-', ''))
        svg = svg.replace('width="100%" height="100%"', f'width="{layout.ancho:.0f}" height="{layout.alto:.0f}"', 1)
        ruta = os.path.join(SALIDAS, f'{modo}.svg')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(svg)
        rutas.append((ruta, layout))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [r for r, _ in rutas]
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel='msedge')
        for ruta, layout in rutas:
            pag = nav.new_page(viewport={'width': int(layout.ancho), 'height': int(layout.alto)})
            pag.goto(pathlib.Path(ruta).as_uri())
            pag.screenshot(path=ruta[:-4] + '.png', timeout=90000)
        nav.close()
    return [r for r, _ in rutas] + [r[:-4] + '.png' for r, _ in rutas]


if __name__ == '__main__':
    for r in exportar():
        print(r)
