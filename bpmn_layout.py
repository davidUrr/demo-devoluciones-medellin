"""Parser y renderizador de diagramas BPMN usando la geometría real (bpmndi)
en vez de un layout automático. Sustituye el uso de networkx/pyvis del
dashboard: lee las coordenadas que Eraser ya calculó (carriles, cajas,
compuertas, eventos y flechas) y dibuja un visor interactivo (zoom/pan +
línea de tiempo animable) coloreado por fase del proceso según el volumen
de expedientes que trae la simulación."""

import json
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape

import proceso as _proceso

NS = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
    'di': 'http://www.omg.org/spec/DD/20100524/DI',
    'dc': 'http://www.omg.org/spec/DD/20100524/DC',
}

# Tipos de nodo de proceso que nos interesa dibujar, y cómo se ven.
TIPOS_NODO = {
    'task': 'tarea',
    'exclusiveGateway': 'compuerta',
    'parallelGateway': 'compuerta',
    'intermediateCatchEvent': 'evento',
    'startEvent': 'evento',
    'endEvent': 'evento',
}


@dataclass
class Nodo:
    id: str
    nombre: str
    tipo: str  # 'tarea' | 'compuerta' | 'evento'
    x: float
    y: float
    w: float
    h: float


@dataclass
class Carril:
    id: str
    nombre: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class Arco:
    id: str
    puntos: List[Tuple[float, float]]
    es_mensaje: bool


@dataclass
class Layout:
    nodos: Dict[str, Nodo] = field(default_factory=dict)
    carriles: List[Carril] = field(default_factory=list)
    arcos: List[Arco] = field(default_factory=list)
    ancho: float = 800.0
    alto: float = 600.0


def parse_bpmn_di(path: str) -> Layout:
    """Lee un .bpmn (procesos + bpmndi) y devuelve su geometría real."""
    tree = ET.parse(path)
    root = tree.getroot()

    tipos_por_id: Dict[str, str] = {}
    nombres_por_id: Dict[str, str] = {}
    for process in root.findall('bpmn:process', NS):
        for tag, tipo in TIPOS_NODO.items():
            for el in process.findall(f'bpmn:{tag}', NS):
                tipos_por_id[el.get('id')] = tipo
                nombres_por_id[el.get('id')] = el.get('name') or el.get('id')

    # Flujos de mensaje y asociaciones (uso de sistemas) se dibujan punteados.
    ids_mensaje = set()
    for collab in root.findall('bpmn:collaboration', NS):
        for mf in collab.findall('bpmn:messageFlow', NS):
            ids_mensaje.add(mf.get('id'))
    for process in root.findall('bpmn:process', NS):
        for asoc in process.findall('bpmn:association', NS):
            ids_mensaje.add(asoc.get('id'))

    ids_lane: Dict[str, str] = {}
    for process in root.findall('bpmn:process', NS):
        for laneset in process.findall('bpmn:laneSet', NS):
            for lane in laneset.findall('bpmn:lane', NS):
                ids_lane[lane.get('id')] = lane.get('name') or lane.get('id')

    plane = root.find('.//bpmndi:BPMNPlane', NS)
    if plane is None:
        raise ValueError(f'{path} no contiene bpmndi:BPMNDiagram/BPMNPlane')

    nodos: Dict[str, Nodo] = {}
    carriles: List[Carril] = []
    max_x = max_y = 0.0

    for shape in plane.findall('bpmndi:BPMNShape', NS):
        elemento_id = shape.get('bpmnElement')
        bounds = shape.find('dc:Bounds', NS)
        if bounds is None:
            continue
        x, y = float(bounds.get('x')), float(bounds.get('y'))
        w, h = float(bounds.get('width')), float(bounds.get('height'))
        max_x, max_y = max(max_x, x + w), max(max_y, y + h)

        if elemento_id in ids_lane:
            carriles.append(Carril(elemento_id, ids_lane[elemento_id], x, y, w, h))
        elif elemento_id in tipos_por_id:
            nodos[elemento_id] = Nodo(
                elemento_id, nombres_por_id.get(elemento_id, elemento_id),
                tipos_por_id[elemento_id], x, y, w, h,
            )

    arcos: List[Arco] = []
    for edge in plane.findall('bpmndi:BPMNEdge', NS):
        elemento_id = edge.get('bpmnElement')
        puntos = [(float(wp.get('x')), float(wp.get('y'))) for wp in edge.findall('di:waypoint', NS)]
        if len(puntos) < 2:
            continue
        arcos.append(Arco(elemento_id, puntos, elemento_id in ids_mensaje))

    carriles.sort(key=lambda c: c.y)
    return Layout(nodos=nodos, carriles=carriles, arcos=arcos,
                  ancho=max_x + 40, alto=max_y + 40)


# Fases y colores: vienen del catálogo único del proceso (proceso.py).
STAGE_BUCKETS = {nombre: e.fase for nombre, e in _proceso.ETAPAS.items()}
BUCKET_COLORS = dict(_proceso.FASES)
COLOR_SIN_FASE = '#b8bec4'


def construir_bucket_por_nodo(mapeo: Dict[str, str]) -> Dict[str, str]:
    """A partir de un mapeo de stages() (nombre de etapa -> id de nodo BPMN),
    devuelve id de nodo -> tramo grueso del proceso al que pertenece."""
    resultado: Dict[str, str] = {}
    for nombre_etapa, nodo_id in mapeo.items():
        bucket = STAGE_BUCKETS.get(nombre_etapa)
        if bucket:
            resultado.setdefault(nodo_id, bucket)
    return resultado


# Orden secuencial real del proceso (de la primera fase a la última), tal
# como ocurre en el AS-IS: BUCKET_COLORS ya está declarado en este orden.
ORDEN_FASES: List[str] = list(BUCKET_COLORS.keys())


def _agregar_ocupacion(historial_por_dia: Dict[int, Dict[str, int]], agrupador,
                        grupos: List[str], dia_max: int) -> Dict[str, List[int]]:
    """Cuenta, día a día, cuántos expedientes hay ACTIVOS en cada grupo
    (fase o rol) a partir de una ocupación cruda por clave (nodo o rol)."""
    resultado = {g: [0] * (dia_max + 1) for g in grupos}
    for dia in range(dia_max + 1):
        for clave, cantidad in historial_por_dia.get(dia, {}).items():
            g = agrupador(clave)
            if g in resultado:
                resultado[g][dia] += cantidad
    return resultado


def _agregar_acumulado_distintos(primeras_entradas: Dict[str, Dict[str, int]], agrupador,
                                  grupos: List[str], dia_max: int) -> Dict[str, List[int]]:
    """Cuenta, día a día, cuántos EXPEDIENTES DISTINTOS han pasado por cada
    grupo (fase o rol) hasta ese día — no toques ni reprocesos, un caso
    cuenta una sola vez por grupo, el día de su primera entrada a él.

    `primeras_entradas` es {case_id: {clave: primer_día}} tal como lo
    devuelve `simulate_con_historial`; `clave` es un nodo BPMN o un rol,
    según cuál se esté agregando.
    """
    primer_dia_grupo_por_caso: Dict[str, Dict[str, int]] = {}
    for case_id, entradas in primeras_entradas.items():
        por_grupo: Dict[str, int] = {}
        for clave, dia in entradas.items():
            g = agrupador(clave)
            if g is None:
                continue
            if g not in por_grupo or dia < por_grupo[g]:
                por_grupo[g] = dia
        primer_dia_grupo_por_caso[case_id] = por_grupo

    dias_por_grupo: Dict[str, List[int]] = {g: [] for g in grupos}
    for por_grupo in primer_dia_grupo_por_caso.values():
        for g, dia in por_grupo.items():
            if g in dias_por_grupo:
                dias_por_grupo[g].append(dia)

    resultado = {g: [0] * (dia_max + 1) for g in grupos}
    for g in grupos:
        dias_ordenados = sorted(dias_por_grupo[g])
        idx = 0
        contador = 0
        for d in range(dia_max + 1):
            while idx < len(dias_ordenados) and dias_ordenados[idx] <= d:
                contador += 1
                idx += 1
            resultado[g][d] = contador
    return resultado


def _envolver_texto(nombre: str, ancho_caja: float) -> List[str]:
    caracteres_por_linea = max(8, int(ancho_caja / 7))
    return textwrap.wrap(nombre, width=caracteres_por_linea, max_lines=3, placeholder='…')


def _construir_svg_estatico(layout: Layout, bucket_por_nodo: Dict[str, str], prefijo: str) -> str:
    """SVG con la geometría real y el color de fase de cada nodo, pero sin
    cantidades: la opacidad (acumulación) y el badge de conteo se rellenan
    en el navegador vía JS para poder animar sin regenerar el SVG.

    width/height van en porcentaje (no en píxeles) a propósito: así el
    propio navegador ajusta el SVG a su contenedor vía `preserveAspectRatio`
    (comportamiento nativo, sin JS) y el "ajuste" nunca depende de que un
    script termine de ejecutarse a tiempo. El JS de zoom solo agrega una
    transformación adicional encima de ese ajuste base.
    """
    partes = [
        f'<svg id="stage-{prefijo}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {layout.ancho:.0f} {layout.alto:.0f}" '
        f'width="100%" height="100%" preserveAspectRatio="xMidYMid meet" '
        f'style="display:block;transform-origin:0 0;" font-family="Segoe UI, Arial, sans-serif">',
        '<defs>',
        f'<marker id="flecha-{prefijo}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
        '<path d="M0,0 L10,5 L0,10 z" fill="#555"/>',
        '</marker>',
        '</defs>',
        f'<rect x="0" y="0" width="{layout.ancho:.0f}" height="{layout.alto:.0f}" fill="#f8f9fa"/>',
    ]

    for i, carril in enumerate(layout.carriles):
        fondo = '#ffffff' if i % 2 == 0 else '#f1f3f5'
        partes.append(
            f'<rect x="{carril.x:.0f}" y="{carril.y:.0f}" width="{carril.w:.0f}" height="{carril.h:.0f}" '
            f'fill="{fondo}" stroke="#dcdcdc"/>'
        )
        partes.append(
            f'<text x="{carril.x + 8:.0f}" y="{carril.y + 18:.0f}" font-size="13" fill="#666" font-weight="600">'
            f'{escape(carril.nombre)}</text>'
        )

    for arco in layout.arcos:
        puntos = ' '.join(f'{x:.0f},{y:.0f}' for x, y in arco.puntos)
        if arco.es_mensaje:
            partes.append(f'<polyline points="{puntos}" fill="none" stroke="#adb5bd" stroke-width="1.5" stroke-dasharray="6,4"/>')
        else:
            partes.append(f'<polyline points="{puntos}" fill="none" stroke="#555" stroke-width="1.6" marker-end="url(#flecha-{prefijo})"/>')

    for nodo in layout.nodos.values():
        color = BUCKET_COLORS.get(bucket_por_nodo.get(nodo.id), COLOR_SIN_FASE)
        cx, cy = nodo.x + nodo.w / 2, nodo.y + nodo.h / 2
        dom_id = f'{prefijo}-{nodo.id}'

        if nodo.tipo == 'compuerta':
            puntos = f'{cx:.0f},{nodo.y:.0f} {nodo.x + nodo.w:.0f},{cy:.0f} {cx:.0f},{nodo.y + nodo.h:.0f} {nodo.x:.0f},{cy:.0f}'
            partes.append(f'<polygon id="forma-{dom_id}" points="{puntos}" fill="{color}" fill-opacity="0.15" stroke="#555" stroke-width="1.5"/>')
        elif nodo.tipo == 'evento':
            radio = min(nodo.w, nodo.h) / 2
            partes.append(f'<circle id="forma-{dom_id}" cx="{cx:.0f}" cy="{cy:.0f}" r="{radio:.0f}" fill="{color}" fill-opacity="0.15" stroke="#555" stroke-width="1.5"/>')
        else:
            partes.append(
                f'<rect id="forma-{dom_id}" x="{nodo.x:.0f}" y="{nodo.y:.0f}" width="{nodo.w:.0f}" height="{nodo.h:.0f}" rx="8" '
                f'fill="{color}" fill-opacity="0.15" stroke="#555" stroke-width="1.5"/>'
            )

        lineas = _envolver_texto(nodo.nombre, nodo.w)
        n = len(lineas) + 1  # +1: línea reservada para el badge de conteo
        y0 = cy - (n - 1) * 6.5
        for j, linea in enumerate(lineas):
            partes.append(
                f'<text x="{cx:.0f}" y="{y0 + j * 13:.0f}" font-size="11" fill="#212529" '
                f'text-anchor="middle" dominant-baseline="middle">{escape(linea)}</text>'
            )
        partes.append(
            f'<text id="cnt-{dom_id}" x="{cx:.0f}" y="{y0 + len(lineas) * 13:.0f}" font-size="11" font-weight="700" '
            f'fill="#212529" text-anchor="middle" dominant-baseline="middle"></text>'
        )

    partes.append('</svg>')
    return '\n'.join(partes)


_PLANTILLA_HTML = """
<div style="font-family:Segoe UI, Arial, sans-serif;">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px;">
    <button id="btn-play" style="padding:5px 12px;cursor:pointer;">&#9654; Reproducir</button>
    <button id="btn-reset-zoom" style="padding:5px 12px;cursor:pointer;">Ajustar zoom</button>
    <input id="slider-dia" type="range" min="0" max="__DIA_MAX__" value="0" style="flex:1;min-width:160px;">
    <span id="etiqueta-dia" style="font-size:13px;color:#333;min-width:90px;">Día 0</span>
  </div>
  <div style="margin-bottom:8px;">__LEYENDA__</div>
  <div id="panel-puntos" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">__PUNTOS_HTML__</div>
  <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px;">
    <div style="flex:1;min-width:320px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">Fases del proceso (en orden, según AS-IS)</div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr style="background:#f1f3f5;">
            <th style="text-align:left;padding:3px 6px;">#</th>
            <th style="text-align:left;padding:3px 6px;">Fase</th>
            <th style="padding:3px 6px;">AS-IS actual</th>
            <th style="padding:3px 6px;">AS-IS acum.</th>
            <th style="padding:3px 6px;">TO-BE actual</th>
            <th style="padding:3px 6px;">TO-BE acum.</th>
          </tr>
        </thead>
        <tbody>__FASES_HTML__</tbody>
      </table>
    </div>
    <div style="flex:1;min-width:320px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">Carga por rol</div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr style="background:#f1f3f5;">
            <th style="text-align:left;padding:3px 6px;">Rol</th>
            <th style="padding:3px 6px;">AS-IS actual</th>
            <th style="padding:3px 6px;">AS-IS acum.</th>
            <th style="padding:3px 6px;">TO-BE actual</th>
            <th style="padding:3px 6px;">TO-BE acum.</th>
          </tr>
        </thead>
        <tbody>__ROLES_HTML__</tbody>
      </table>
    </div>
  </div>
  <div style="display:flex;gap:10px;">
    <div style="flex:1;min-width:0;">
      <div style="text-align:center;font-weight:600;margin-bottom:4px;">AS-IS (actual)</div>
      <div id="viewport-asis" style="width:100%;height:__ALTURA__px;overflow:hidden;position:relative;border:1px solid #ddd;background:#fff;cursor:grab;">__SVG_ASIS__</div>
    </div>
    <div style="flex:1;min-width:0;">
      <div style="text-align:center;font-weight:600;margin-bottom:4px;">TO-BE (mejorado)</div>
      <div id="viewport-tobe" style="width:100%;height:__ALTURA__px;overflow:hidden;position:relative;border:1px solid #ddd;background:#fff;cursor:grab;">__SVG_TOBE__</div>
    </div>
  </div>
</div>
<script>
(function () {
  const datosAsis = __DATOS_ASIS__;
  const datosTobe = __DATOS_TOBE__;
  const diaMax = __DIA_MAX__;
  const puntosInteres = __PUNTOS_JSON__;
  const fases = __FASES_JSON__;
  const roles = __ROLES_JSON__;

  function opacidad(cantidad) {
    if (cantidad <= 0) return 0.15;
    return Math.min(0.15 + cantidad * 0.16, 1.0);
  }

  function colorSemaforo(cantidad) {
    if (cantidad <= 0) return '#bdc3c7';
    if (cantidad <= 2) return '#2ecc71';
    if (cantidad <= 5) return '#f1c40f';
    return '#e74c3c';
  }

  function pintarLado(datos, dia, prefijo) {
    const estado = datos[dia] || {};
    document.querySelectorAll('[id^="forma-' + prefijo + '-"]').forEach(function (el) {
      const nodoId = el.id.slice(('forma-' + prefijo + '-').length);
      const cantidad = estado[nodoId] || 0;
      el.setAttribute('fill-opacity', opacidad(cantidad));
      const etiqueta = document.getElementById('cnt-' + prefijo + '-' + nodoId);
      if (etiqueta) etiqueta.textContent = cantidad > 0 ? ('[' + cantidad + ' exp.]') : '';
    });
  }

  function pintarPuntos(dia) {
    const estadoAsis = datosAsis[dia] || {};
    const estadoTobe = datosTobe[dia] || {};
    puntosInteres.forEach(function (p, i) {
      const cAsis = estadoAsis[p.nodoAsis] || 0;
      const cTobe = estadoTobe[p.nodoTobe] || 0;
      const elA = document.getElementById('watch-asis-' + i);
      const elT = document.getElementById('watch-tobe-' + i);
      if (elA) { elA.style.background = colorSemaforo(cAsis); elA.textContent = 'AS-IS: ' + cAsis; }
      if (elT) { elT.style.background = colorSemaforo(cTobe); elT.textContent = 'TO-BE: ' + cTobe; }
    });
  }

  function pintarGrupos(grupos, prefijoTabla, dia) {
    grupos.orden.forEach(function (nombre, i) {
      const elActualAsis = document.getElementById(prefijoTabla + '-actual-asis-' + i);
      const elAcumAsis = document.getElementById(prefijoTabla + '-acum-asis-' + i);
      const elActualTobe = document.getElementById(prefijoTabla + '-actual-tobe-' + i);
      const elAcumTobe = document.getElementById(prefijoTabla + '-acum-tobe-' + i);
      const cActualAsis = (grupos.actualAsis[nombre] || [])[dia] || 0;
      const cActualTobe = (grupos.actualTobe[nombre] || [])[dia] || 0;
      if (elActualAsis) { elActualAsis.textContent = cActualAsis; elActualAsis.style.background = colorSemaforo(cActualAsis); }
      if (elActualTobe) { elActualTobe.textContent = cActualTobe; elActualTobe.style.background = colorSemaforo(cActualTobe); }
      if (elAcumAsis) elAcumAsis.textContent = (grupos.acumAsis[nombre] || [])[dia] || 0;
      if (elAcumTobe) elAcumTobe.textContent = (grupos.acumTobe[nombre] || [])[dia] || 0;
    });
  }

  function pintar(dia) {
    pintarLado(datosAsis, dia, 'asis');
    pintarLado(datosTobe, dia, 'tobe');
    pintarPuntos(dia);
    pintarGrupos(fases, 'fase', dia);
    pintarGrupos(roles, 'rol', dia);
    document.getElementById('etiqueta-dia').textContent = 'Día ' + dia;
  }

  function habilitarZoom(viewportId, stageId) {
    // El SVG ya se ajusta solo al contenedor (width/height=100% + viewBox +
    // preserveAspectRatio, nativo del navegador, sin JS). Esta función solo
    // agrega zoom/pan ENCIMA de ese ajuste base: escala=1 siempre significa
    // "diagrama completo visible", así que restablecer es trivial y no
    // depende de leer tamaños ni de que ningún cálculo previo haya corrido.
    const viewport = document.getElementById(viewportId);
    const stage = document.getElementById(stageId);
    let escala = 1, tx = 0, ty = 0, arrastrando = false, ultimoX = 0, ultimoY = 0;

    function aplicar() {
      stage.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + escala + ')';
    }

    function restablecer() {
      escala = 1; tx = 0; ty = 0;
      aplicar();
    }

    viewport.addEventListener('wheel', function (e) {
      e.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.15 : 0.87;
      const nuevaEscala = Math.min(Math.max(escala * factor, 1), 8);
      tx = mx - (mx - tx) * (nuevaEscala / escala);
      ty = my - (my - ty) * (nuevaEscala / escala);
      escala = nuevaEscala;
      aplicar();
    }, { passive: false });

    viewport.addEventListener('mousedown', function (e) {
      arrastrando = true; ultimoX = e.clientX; ultimoY = e.clientY; viewport.style.cursor = 'grabbing';
    });
    window.addEventListener('mouseup', function () { arrastrando = false; viewport.style.cursor = 'grab'; });
    window.addEventListener('mousemove', function (e) {
      if (!arrastrando) return;
      tx += e.clientX - ultimoX; ty += e.clientY - ultimoY;
      ultimoX = e.clientX; ultimoY = e.clientY;
      aplicar();
    });

    return restablecer;
  }

  const ajustarAsis = habilitarZoom('viewport-asis', 'stage-asis');
  const ajustarTobe = habilitarZoom('viewport-tobe', 'stage-tobe');

  document.getElementById('btn-reset-zoom').addEventListener('click', function () {
    ajustarAsis(); ajustarTobe();
  });

  const slider = document.getElementById('slider-dia');
  slider.addEventListener('input', function () { pintar(parseInt(slider.value, 10)); });

  let reproduciendo = false, temporizador = null;
  const btnPlay = document.getElementById('btn-play');
  btnPlay.addEventListener('click', function () {
    reproduciendo = !reproduciendo;
    btnPlay.innerHTML = reproduciendo ? '&#10074;&#10074; Pausar' : '&#9654; Reproducir';
    if (reproduciendo) {
      temporizador = setInterval(function () {
        let dia = parseInt(slider.value, 10) + 1;
        if (dia > diaMax) dia = 0;
        slider.value = dia;
        pintar(dia);
      }, 220);
    } else {
      clearInterval(temporizador);
    }
  });

  ajustarAsis();
  ajustarTobe();
  pintar(0);
})();
</script>
"""


def _tabla_grupos_html(orden: List[str], id_prefijo: str, con_numero: bool) -> str:
    filas = []
    for i, nombre in enumerate(orden):
        celda_numero = f'<td style="padding:3px 6px;font-weight:700;">{i + 1}</td>' if con_numero else ''
        filas.append(
            f'<tr style="border-bottom:1px solid #eee;">'
            f'{celda_numero}'
            f'<td style="padding:3px 6px;">{escape(nombre)}</td>'
            f'<td style="padding:3px 6px;text-align:center;">'
            f'<span id="{id_prefijo}-actual-asis-{i}" style="display:inline-block;min-width:24px;padding:2px 6px;'
            f'border-radius:5px;font-weight:700;color:#fff;background:#bdc3c7;">0</span></td>'
            f'<td style="padding:3px 6px;text-align:center;font-weight:600;" id="{id_prefijo}-acum-asis-{i}">0</td>'
            f'<td style="padding:3px 6px;text-align:center;">'
            f'<span id="{id_prefijo}-actual-tobe-{i}" style="display:inline-block;min-width:24px;padding:2px 6px;'
            f'border-radius:5px;font-weight:700;color:#fff;background:#bdc3c7;">0</span></td>'
            f'<td style="padding:3px 6px;text-align:center;font-weight:600;" id="{id_prefijo}-acum-tobe-{i}">0</td>'
            f'</tr>'
        )
    return ''.join(filas)


def render_comparativo(layout_asis: Layout, historial_asis: Dict[int, Dict[str, int]], bucket_asis: Dict[str, str],
                        layout_tobe: Layout, historial_tobe: Dict[int, Dict[str, int]], bucket_tobe: Dict[str, str],
                        altura: int = 650, puntos_interes: List[Tuple[str, str, str]] = None,
                        primeras_entradas_nodo_asis: Dict[str, Dict[str, int]] = None,
                        primeras_entradas_nodo_tobe: Dict[str, Dict[str, int]] = None,
                        historial_rol_asis: Dict[int, Dict[str, int]] = None,
                        historial_rol_tobe: Dict[int, Dict[str, int]] = None,
                        primeras_entradas_rol_asis: Dict[str, Dict[str, int]] = None,
                        primeras_entradas_rol_tobe: Dict[str, Dict[str, int]] = None,
                        orden_roles: List[str] = None) -> str:
    """Visor único (un solo iframe) con AS-IS y TO-BE lado a lado: zoom/pan
    independiente por panel, coloreado por fase del proceso (más opaco =
    más expedientes acumulados), una línea de tiempo con reproducción
    automática, tarjetas de "puntos de interés" (semáforo) para los puntos
    del proceso que el usuario elija vigilar, y dos tablas — fases del
    proceso numeradas en su orden real, y carga por rol — con "actual"
    (semáforo, expedientes activos ese día) y "acumulado" (expedientes
    DISTINTOS que ya pasaron por ahí, sin contar reprocesos dos veces).

    `puntos_interes` es una lista de (nombre_etapa, nodo_id_asis, nodo_id_tobe).
    Los `primeras_entradas_*`/`historial_rol_*` son las estructuras que
    devuelve `simular_devoluciones.simulate_con_historial` para la réplica
    de referencia; si se omiten, las tablas de fases/roles quedan vacías.
    """
    puntos_interes = puntos_interes or []
    primeras_entradas_nodo_asis = primeras_entradas_nodo_asis or {}
    primeras_entradas_nodo_tobe = primeras_entradas_nodo_tobe or {}
    historial_rol_asis = historial_rol_asis or {}
    historial_rol_tobe = historial_rol_tobe or {}
    primeras_entradas_rol_asis = primeras_entradas_rol_asis or {}
    primeras_entradas_rol_tobe = primeras_entradas_rol_tobe or {}
    orden_roles = orden_roles or []

    def ultimo_dia_con_actividad(historial: Dict[int, Dict[str, int]]) -> int:
        dias = [d for d, estado in historial.items() if estado]
        return max(dias) if dias else 0

    dia_max = max(ultimo_dia_con_actividad(historial_asis), ultimo_dia_con_actividad(historial_tobe), 1)
    datos_asis = {d: historial_asis.get(d, {}) for d in range(dia_max + 1)}
    datos_tobe = {d: historial_tobe.get(d, {}) for d in range(dia_max + 1)}

    svg_asis = _construir_svg_estatico(layout_asis, bucket_asis, 'asis')
    svg_tobe = _construir_svg_estatico(layout_tobe, bucket_tobe, 'tobe')

    leyenda = ''.join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:14px;font-size:12px;color:#333;">'
        f'<span style="width:12px;height:12px;border-radius:3px;background:{color};display:inline-block;"></span>{escape(nombre)}</span>'
        for nombre, color in BUCKET_COLORS.items()
    )

    puntos_html = ''.join(
        f'<div style="border:1px solid #ddd;border-radius:8px;padding:6px 10px;min-width:170px;background:#fafafa;">'
        f'<div style="font-size:12px;color:#555;margin-bottom:4px;">{escape(nombre)}</div>'
        f'<div style="display:flex;gap:6px;">'
        f'<div id="watch-asis-{i}" style="flex:1;text-align:center;padding:3px 6px;border-radius:5px;'
        f'font-weight:700;font-size:12px;color:#fff;background:#bdc3c7;">AS-IS: 0</div>'
        f'<div id="watch-tobe-{i}" style="flex:1;text-align:center;padding:3px 6px;border-radius:5px;'
        f'font-weight:700;font-size:12px;color:#fff;background:#bdc3c7;">TO-BE: 0</div>'
        f'</div></div>'
        for i, (nombre, _, _) in enumerate(puntos_interes)
    )
    puntos_json = json.dumps([
        {'nombre': nombre, 'nodoAsis': nodo_asis, 'nodoTobe': nodo_tobe}
        for nombre, nodo_asis, nodo_tobe in puntos_interes
    ])

    # --- Fases: "actual" viene de la ocupación ya usada para el diagrama; el
    # "acumulado" cuenta expedientes DISTINTOS que ya entraron a la fase. ---
    fases_actual_asis = _agregar_ocupacion(historial_asis, lambda n: bucket_asis.get(n), ORDEN_FASES, dia_max)
    fases_actual_tobe = _agregar_ocupacion(historial_tobe, lambda n: bucket_tobe.get(n), ORDEN_FASES, dia_max)
    fases_acum_asis = _agregar_acumulado_distintos(primeras_entradas_nodo_asis, lambda n: bucket_asis.get(n), ORDEN_FASES, dia_max)
    fases_acum_tobe = _agregar_acumulado_distintos(primeras_entradas_nodo_tobe, lambda n: bucket_tobe.get(n), ORDEN_FASES, dia_max)
    fases_json = json.dumps({
        'orden': ORDEN_FASES,
        'actualAsis': fases_actual_asis, 'actualTobe': fases_actual_tobe,
        'acumAsis': fases_acum_asis, 'acumTobe': fases_acum_tobe,
    })
    fases_html = _tabla_grupos_html(ORDEN_FASES, 'fase', con_numero=True)

    # --- Roles: la ocupación ya viene agrupada por rol; el acumulado también
    # cuenta expedientes distintos que ya pasaron por ese rol. ---
    rol_actual_asis = _agregar_ocupacion(historial_rol_asis, lambda r: r, orden_roles, dia_max)
    rol_actual_tobe = _agregar_ocupacion(historial_rol_tobe, lambda r: r, orden_roles, dia_max)
    rol_acum_asis = _agregar_acumulado_distintos(primeras_entradas_rol_asis, lambda r: r, orden_roles, dia_max)
    rol_acum_tobe = _agregar_acumulado_distintos(primeras_entradas_rol_tobe, lambda r: r, orden_roles, dia_max)
    roles_json = json.dumps({
        'orden': orden_roles,
        'actualAsis': rol_actual_asis, 'actualTobe': rol_actual_tobe,
        'acumAsis': rol_acum_asis, 'acumTobe': rol_acum_tobe,
    })
    roles_html = _tabla_grupos_html(orden_roles, 'rol', con_numero=False)

    html = (
        _PLANTILLA_HTML
        .replace('__DIA_MAX__', str(dia_max))
        .replace('__ALTURA__', str(altura))
        .replace('__LEYENDA__', leyenda)
        .replace('__PUNTOS_HTML__', puntos_html)
        .replace('__FASES_HTML__', fases_html)
        .replace('__ROLES_HTML__', roles_html)
        .replace('__SVG_ASIS__', svg_asis)
        .replace('__SVG_TOBE__', svg_tobe)
        .replace('__DATOS_ASIS__', json.dumps(datos_asis))
        .replace('__DATOS_TOBE__', json.dumps(datos_tobe))
        .replace('__PUNTOS_JSON__', puntos_json)
        .replace('__FASES_JSON__', fases_json)
        .replace('__ROLES_JSON__', roles_json)
    )
    return html
