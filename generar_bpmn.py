"""Genera AS-IS.bpmn y TO-BE.bpmn (BPMN 2.0 con geometría bpmndi) a partir
de una especificación compacta: carriles, nodos en columnas y flujos.

En Envigado los diagramas se dibujaron en Eraser y quedaron con muchos
cruces de flechas. Aquí la geometría sale de una rejilla: cada nodo tiene
columna y carril, y las flechas son ortogonales. Los archivos se pueden
abrir en bpmn.io o Camunda Modeler para ajustarlos a mano.

Los identificadores de las tareas coinciden con `nodo_asis` y `nodo_tobe`
de proceso.py: así el mapa de calor sabe qué caja pintar.
"""

import os
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape, quoteattr

import proceso as p

AQUI = os.path.dirname(os.path.abspath(__file__))

COL_W, LANE_H, X0, Y0 = 150, 120, 150, 0
TAREA = (118, 62)
COMPUERTA = (46, 46)
EVENTO = (36, 36)

# --- AS-IS ------------------------------------------------------------------
ASIS = {
    'nombre': 'AS-IS — Devoluciones y compensaciones — Subsecretaría de Ingresos de Medellín',
    'carriles': [
        ('L_contrib', 'Contribuyente'),
        ('L_radic', 'Radicación (Mercurio)'),
        ('L_lider', 'Líder y revisores'),
        ('L_sust', 'Sustanciadores (85 % contratistas)'),
        ('L_otras', 'Otras unidades de Ingresos'),
        ('L_notif', 'Notificaciones (Apoyo a Ingresos)'),
        ('L_jur', 'Unidad Jurídica'),
        ('L_fin', 'Presupuesto, contabilidad y Tesorería'),
        ('L_sis', 'Sistemas sin integrar'),
    ],
    # id, nombre, tipo, carril, columna
    'nodos': [
        ('A_Inicio', 'Solicitud', 'start', 'L_contrib', 0),
        ('A_Presentar', 'Presentar solicitud y anexos', 'task', 'L_contrib', 1),
        ('A_Radicar', 'Radicar en Mercurio', 'task', 'L_radic', 2),
        ('A_Repartir', 'Repartir por Excel o correo', 'task', 'L_lider', 3),
        ('A_Revisar_requisitos', 'Revisar requisitos y competencia', 'task', 'L_sust', 4),
        ('A_GW_completa', '¿Procede?', 'xor', 'L_sust', 5),
        ('A_Auto_inadmisorio', 'Elaborar auto inadmisorio en Word/NAS', 'task', 'L_sust', 6),
        ('A_Proyectar_rechazo', 'Proyectar rechazo (firma del líder)', 'task', 'L_sust', 7),
        ('A_Notificar_inadmision', 'Notificar inadmisión', 'task', 'L_notif', 7),
        ('A_Notificar_rechazo', 'Notificar rechazo', 'task', 'L_notif', 8),
        ('A_Fin_rechazo', 'Rechazada', 'end', 'L_notif', 9),
        ('A_Subsanar', 'Subsanar dentro del término', 'task', 'L_contrib', 8),
        ('A_Revisar_subsanacion', 'Revisar subsanación', 'task', 'L_sust', 9),
        ('A_Consolidar', 'Consolidar información a mano (Mercurio, NAS, Visor, Excel)', 'task', 'L_sust', 10),
        ('A_Solicitar_info', 'Pedir estado de cuenta o cartera por correo', 'task', 'L_otras', 11),
        ('A_Analizar', 'Analizar y verificar el saldo', 'task', 'L_sust', 12),
        ('A_Revisar_proyecto', 'Revisar proyecto de decisión', 'task', 'L_lider', 13),
        ('A_Proyectar_resolucion', 'Proyectar resolución en Word/NAS', 'task', 'L_sust', 14),
        ('A_Firmar', 'Revisar y firmar', 'task', 'L_lider', 15),
        ('A_Notificar_resolucion', 'Notificar resolución', 'task', 'L_notif', 16),
        ('A_GW_recurso', '¿Recurso?', 'xor', 'L_notif', 17),
        ('A_Interponer_recurso', 'Interponer recurso', 'task', 'L_contrib', 18),
        ('A_Resolver_recurso', 'Resolver recurso', 'task', 'L_jur', 19),
        ('A_Notificar_recurso', 'Notificar decisión del recurso', 'task', 'L_notif', 21),
        ('A_Fin_recurso', 'Recurso resuelto', 'end', 'L_notif', 23),
        ('A_Ejecutoria', 'Controlar ejecutoria en Excel', 'task', 'L_sust', 18),
        ('A_Registrar_SAP', 'Pedir a otra área el registro en cuenta corriente', 'task', 'L_otras', 19),
        ('A_GW_pago', '¿Saldo a pagar?', 'xor', 'L_otras', 20),
        ('A_Fin_compensada', 'Compensada', 'end', 'L_otras', 21),
        ('A_Cruce_cartera', 'Cruzar con cartera (Títulos, Cobranzas)', 'task', 'L_otras', 22),
        ('A_Orden_pago', 'Orden de pago y registro contable', 'task', 'L_fin', 22),
        ('A_Pagar', 'Pagar y enviar evidencia por correo', 'task', 'L_fin', 23),
        ('A_Fin_pagada', 'Pagada', 'end', 'L_fin', 24),
        # Sistemas (no son etapas simuladas: aparecen en gris)
        ('S_Mercurio', 'Mercurio (intermitente)', 'task', 'L_sis', 2),
        ('S_Excel', 'Excel y tableros', 'task', 'L_sis', 3),
        ('S_Visor', 'Visor 360 / NAS', 'task', 'L_sis', 10),
        ('S_Correo', 'Correo', 'task', 'L_sis', 11),
        ('S_NAS', 'NAS (actos)', 'task', 'L_sis', 14),
        ('S_SAP', 'SAP (solo predial)', 'task', 'L_sis', 21),
    ],
    'flujos': [
        ('A_Inicio', 'A_Presentar', ''), ('A_Presentar', 'A_Radicar', ''), ('A_Radicar', 'A_Repartir', ''),
        ('A_Repartir', 'A_Revisar_requisitos', ''), ('A_Revisar_requisitos', 'A_GW_completa', ''),
        ('A_GW_completa', 'A_Auto_inadmisorio', 'Incompleta'), ('A_GW_completa', 'A_Proyectar_rechazo', 'No procede'),
        ('A_GW_completa', 'A_Consolidar', 'Completa'),
        ('A_Auto_inadmisorio', 'A_Notificar_inadmision', ''), ('A_Notificar_inadmision', 'A_Subsanar', ''),
        ('A_Subsanar', 'A_Revisar_subsanacion', ''), ('A_Revisar_subsanacion', 'A_Consolidar', ''),
        ('A_Proyectar_rechazo', 'A_Notificar_rechazo', ''), ('A_Notificar_rechazo', 'A_Fin_rechazo', ''),
        ('A_Consolidar', 'A_Solicitar_info', ''), ('A_Solicitar_info', 'A_Analizar', ''),
        ('A_Analizar', 'A_Revisar_proyecto', ''), ('A_Revisar_proyecto', 'A_Proyectar_resolucion', ''),
        ('A_Proyectar_resolucion', 'A_Firmar', ''), ('A_Firmar', 'A_Notificar_resolucion', ''),
        ('A_Notificar_resolucion', 'A_GW_recurso', ''),
        ('A_GW_recurso', 'A_Interponer_recurso', 'Sí'), ('A_Interponer_recurso', 'A_Resolver_recurso', ''),
        ('A_Resolver_recurso', 'A_Notificar_recurso', ''), ('A_Notificar_recurso', 'A_Fin_recurso', ''),
        ('A_GW_recurso', 'A_Ejecutoria', 'No'), ('A_Ejecutoria', 'A_Registrar_SAP', ''),
        ('A_Registrar_SAP', 'A_GW_pago', ''), ('A_GW_pago', 'A_Fin_compensada', 'Compensación'),
        ('A_GW_pago', 'A_Cruce_cartera', 'Tiene deudas'), ('A_GW_pago', 'A_Orden_pago', 'Devolución'),
        ('A_Cruce_cartera', 'A_Orden_pago', ''), ('A_Orden_pago', 'A_Pagar', ''), ('A_Pagar', 'A_Fin_pagada', ''),
    ],
    'mensajes': [
        ('A_Radicar', 'S_Mercurio'), ('A_Repartir', 'S_Excel'), ('A_Consolidar', 'S_Visor'),
        ('A_Solicitar_info', 'S_Correo'), ('A_Proyectar_resolucion', 'S_NAS'), ('A_Registrar_SAP', 'S_SAP'),
    ],
}

# --- TO-BE ------------------------------------------------------------------
TOBE = {
    'nombre': 'TO-BE — Devoluciones y compensaciones con expediente único — Subsecretaría de Ingresos de Medellín',
    'carriles': [
        ('L_contrib', 'Contribuyente'),
        ('L_plat', 'Plataforma de expediente (automático)'),
        ('L_lider', 'Líder y revisores'),
        ('L_sust', 'Sustanciadores'),
        ('L_otras', 'Otras unidades (solicitudes con ANS)'),
        ('L_notif', 'Notificaciones (Apoyo a Ingresos)'),
        ('L_jur', 'Unidad Jurídica'),
        ('L_fin', 'Presupuesto, contabilidad y Tesorería'),
        ('L_sis', 'Sistemas conectados progresivamente'),
    ],
    'nodos': [
        ('T_Inicio', 'Solicitud', 'start', 'L_contrib', 0),
        ('T_Presentar', 'Presentar solicitud y anexos', 'task', 'L_contrib', 1),
        ('T_Crear_expediente', 'Crear expediente desde el radicado', 'task', 'L_plat', 2),
        ('T_Repartir', 'Repartir por reglas y carga', 'task', 'L_plat', 3),
        ('T_Checklist', 'Checklist de requisitos por renta', 'task', 'L_sust', 4),
        ('T_GW_completa', '¿Procede?', 'xor', 'L_sust', 5),
        ('T_Requerimiento', 'Requerimiento desde plantilla', 'task', 'L_sust', 6),
        ('T_Proyectar_rechazo', 'Rechazo desde plantilla (firma del líder)', 'task', 'L_sust', 7),
        ('T_Notificar_inadmision', 'Notificar y trazar inadmisión', 'task', 'L_notif', 7),
        ('T_Notificar_rechazo', 'Notificar y trazar rechazo', 'task', 'L_notif', 8),
        ('T_Fin_rechazo', 'Rechazada', 'end', 'L_notif', 9),
        ('T_Subsanar', 'Subsanar dentro del término', 'task', 'L_contrib', 8),
        ('T_Validar_subsanacion', 'Validar subsanación con checklist', 'task', 'L_sust', 9),
        ('T_Vista_360', 'Vista 360 del contribuyente (solo consulta)', 'task', 'L_plat', 10),
        ('T_Solicitud_ANS', 'Atender solicitud con ANS y seguimiento', 'task', 'L_otras', 11),
        ('T_Analizar', 'Analizar y verificar el saldo', 'task', 'L_sust', 12),
        ('T_Revisar_proyecto', 'Revisar proyecto en la bandeja', 'task', 'L_lider', 13),
        ('T_Generar_resolucion', 'Generar resolución desde plantilla', 'task', 'L_sust', 14),
        ('T_Firmar', 'Revisar y firmar con versión controlada', 'task', 'L_lider', 15),
        ('T_Notificar_resolucion', 'Notificar y trazar resolución', 'task', 'L_notif', 16),
        ('T_GW_recurso', '¿Recurso?', 'xor', 'L_notif', 17),
        ('T_Interponer_recurso', 'Interponer recurso', 'task', 'L_contrib', 18),
        ('T_Resolver_recurso', 'Resolver recurso con relatoría', 'task', 'L_jur', 19),
        ('T_Notificar_recurso', 'Notificar decisión del recurso', 'task', 'L_notif', 21),
        ('T_Fin_recurso', 'Recurso resuelto', 'end', 'L_notif', 23),
        ('T_Ejecutoria', 'Motor de términos: ejecutoria', 'task', 'L_plat', 18),
        ('T_Registrar_SAP', 'Registrar en cuenta corriente (tarea con ANS)', 'task', 'L_otras', 19),
        ('T_GW_pago', '¿Saldo a pagar?', 'xor', 'L_otras', 20),
        ('T_Cierre_compensada', 'Compensada', 'end', 'L_otras', 21),
        ('T_Cruce_cartera', 'Cruzar con cartera en la vista 360', 'task', 'L_otras', 22),
        ('T_Orden_pago', 'Orden de pago y registro contable', 'task', 'L_fin', 22),
        ('T_Pagar', 'Pagar y adjuntar evidencia', 'task', 'L_fin', 23),
        ('T_Cierre', 'Cerrar expediente y bitácora', 'task', 'L_plat', 24),
        ('T_Fin_pagada', 'Pagada', 'end', 'L_plat', 25),
        ('S_Mercurio', 'Mercurio (radicado)', 'task', 'L_sis', 2),
        ('S_Tablero', 'Tablero, alertas y bitácora', 'task', 'L_sis', 18),
        ('S_Lago', 'Lago de datos / Power BI (consulta)', 'task', 'L_sis', 10),
        ('S_Plantillas', 'Plantillas y NAS', 'task', 'L_sis', 14),
        ('S_SAP', 'SAP (vía Centro de Competencias)', 'task', 'L_sis', 21),
    ],
    'flujos': [
        ('T_Inicio', 'T_Presentar', ''), ('T_Presentar', 'T_Crear_expediente', ''), ('T_Crear_expediente', 'T_Repartir', ''),
        ('T_Repartir', 'T_Checklist', ''), ('T_Checklist', 'T_GW_completa', ''),
        ('T_GW_completa', 'T_Requerimiento', 'Incompleta'), ('T_GW_completa', 'T_Proyectar_rechazo', 'No procede'),
        ('T_GW_completa', 'T_Vista_360', 'Completa'),
        ('T_Requerimiento', 'T_Notificar_inadmision', ''), ('T_Notificar_inadmision', 'T_Subsanar', ''),
        ('T_Subsanar', 'T_Validar_subsanacion', ''), ('T_Validar_subsanacion', 'T_Vista_360', ''),
        ('T_Proyectar_rechazo', 'T_Notificar_rechazo', ''), ('T_Notificar_rechazo', 'T_Fin_rechazo', ''),
        ('T_Vista_360', 'T_Solicitud_ANS', ''), ('T_Solicitud_ANS', 'T_Analizar', ''),
        ('T_Analizar', 'T_Revisar_proyecto', ''), ('T_Revisar_proyecto', 'T_Generar_resolucion', ''),
        ('T_Generar_resolucion', 'T_Firmar', ''), ('T_Firmar', 'T_Notificar_resolucion', ''),
        ('T_Notificar_resolucion', 'T_GW_recurso', ''),
        ('T_GW_recurso', 'T_Interponer_recurso', 'Sí'), ('T_Interponer_recurso', 'T_Resolver_recurso', ''),
        ('T_Resolver_recurso', 'T_Notificar_recurso', ''), ('T_Notificar_recurso', 'T_Fin_recurso', ''),
        ('T_GW_recurso', 'T_Ejecutoria', 'No'), ('T_Ejecutoria', 'T_Registrar_SAP', ''),
        ('T_Registrar_SAP', 'T_GW_pago', ''), ('T_GW_pago', 'T_Cierre_compensada', 'Compensación'),
        ('T_GW_pago', 'T_Cruce_cartera', 'Tiene deudas'), ('T_GW_pago', 'T_Orden_pago', 'Devolución'),
        ('T_Cruce_cartera', 'T_Orden_pago', ''), ('T_Orden_pago', 'T_Pagar', ''), ('T_Pagar', 'T_Cierre', ''),
        ('T_Cierre', 'T_Fin_pagada', ''),
    ],
    'mensajes': [
        ('T_Crear_expediente', 'S_Mercurio'), ('T_Ejecutoria', 'S_Tablero'), ('T_Vista_360', 'S_Lago'),
        ('T_Generar_resolucion', 'S_Plantillas'), ('T_Registrar_SAP', 'S_SAP'),
    ],
}

TAG = {'task': 'task', 'xor': 'exclusiveGateway', 'start': 'startEvent', 'end': 'endEvent'}


def _geometria(spec) -> Tuple[Dict[str, Tuple[float, float, float, float]], Dict[str, Tuple[float, float]], float]:
    carril_y = {lid: Y0 + i * LANE_H for i, (lid, _) in enumerate(spec['carriles'])}
    cajas = {}
    for nid, _, tipo, carril, col in spec['nodos']:
        w, h = TAREA if tipo == 'task' else COMPUERTA if tipo == 'xor' else EVENTO
        cx = X0 + col * COL_W + COL_W / 2
        cy = carril_y[carril] + LANE_H / 2
        cajas[nid] = (cx - w / 2, cy - h / 2, w, h)
    ancho = X0 + (max(n[4] for n in spec['nodos']) + 1) * COL_W + 40
    return cajas, carril_y, ancho


def _cruza(p1, p2, caja, margen=4) -> bool:
    """¿El segmento ortogonal p1-p2 atraviesa la caja?"""
    x, y, w, h = caja
    x0, x1 = sorted((p1[0], p2[0]))
    y0, y1 = sorted((p1[1], p2[1]))
    return x0 < x + w - margen and x1 > x + margen and y0 < y + h - margen and y1 > y + margen


def _colisiones(puntos, obstaculos) -> int:
    return sum(_cruza(a, b, c) for a, b in zip(puntos, puntos[1:]) for c in obstaculos)


def _candidatas(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2
    abajo = bcy > acy + 1
    arriba = bcy < acy - 1
    c = []
    if not abajo and not arriba:  # mismo carril
        if bx >= ax + aw:
            c.append([(ax + aw, acy), (bx, bcy)])
        for yb in (min(ay, by) - 16, max(ay + ah, by + bh) + 16):  # rodear por arriba o por abajo
            ys, ye = (ay, by) if yb < acy else (ay + ah, by + bh)
            c.append([(acx, ys), (acx, yb), (bcx, yb), (bcx, ye)])
        return c
    y_sal = ay + ah if abajo else ay
    y_ent = by if abajo else by + bh
    if abs(acx - bcx) < 1:
        c.append([(acx, y_sal), (bcx, y_ent)])
    if bcx > acx:
        c.append([(acx, y_sal), (acx, bcy), (bx, bcy)])            # baja y entra por el lado
        c.append([(ax + aw, acy), (bcx, acy), (bcx, y_ent)])       # sale por el lado y baja
        xc = bx - 16                                               # canal justo antes del destino
        c.append([(ax + aw, acy), (xc, acy), (xc, bcy), (bx, bcy)])
        xc = ax + aw + 16                                          # canal justo después del origen
        c.append([(ax + aw, acy), (xc, acy), (xc, bcy), (bx, bcy)])
    else:
        ymid = (y_sal + y_ent) / 2
        c.append([(acx, y_sal), (acx, ymid), (bcx, ymid), (bcx, y_ent)])
    c.append([(acx, y_sal), (acx, bcy), (bx if bcx > acx else bx + bw, bcy)])
    return c


def _ruta_flujo(a, b, obstaculos) -> List[Tuple[float, float]]:
    """Primera ruta ortogonal sin colisiones; si ninguna está libre, la de menos."""
    otros = [c for c in obstaculos if c is not a and c is not b]
    mejor = None
    for cand in _candidatas(a, b):
        n = _colisiones(cand, otros)
        if n == 0:
            return cand
        if mejor is None or n < mejor[0]:
            mejor = (n, cand)
    return mejor[1]


def generar(spec, ruta_salida: str) -> None:
    cajas, carril_y, ancho = _geometria(spec)
    alto = Y0 + len(spec['carriles']) * LANE_H
    salida, entrada = {}, {}
    flujos = []
    for i, (a, b, etiqueta) in enumerate(spec['flujos']):
        fid = f'F{i:03d}_{a}_{b}'
        flujos.append((fid, a, b, etiqueta))
        salida.setdefault(a, []).append(fid)
        entrada.setdefault(b, []).append(fid)

    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" '
         'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
         'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
         'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
         'id="Definitions_1" targetNamespace="http://medellin.demo/bpmn" exporter="generar_bpmn.py">',
         '  <collaboration id="Collab_1">',
         f'    <participant id="Pool_1" name={quoteattr(spec["nombre"])} processRef="Proceso_1"/>',
         '  </collaboration>',
         '  <process id="Proceso_1" isExecutable="false">',
         '    <laneSet id="LaneSet_1">']
    for lid, nombre in spec['carriles']:
        L.append(f'      <lane id="{lid}" name={quoteattr(nombre)}>')
        for nid, _, _, carril, _ in spec['nodos']:
            if carril == lid:
                L.append(f'        <flowNodeRef>{nid}</flowNodeRef>')
        L.append('      </lane>')
    L.append('    </laneSet>')
    for nid, nombre, tipo, _, _ in spec['nodos']:
        L.append(f'    <{TAG[tipo]} id="{nid}" name={quoteattr(nombre)}>')
        for f in entrada.get(nid, []):
            L.append(f'      <incoming>{f}</incoming>')
        for f in salida.get(nid, []):
            L.append(f'      <outgoing>{f}</outgoing>')
        L.append(f'    </{TAG[tipo]}>')
    for fid, a, b, etiqueta in flujos:
        nombre = f' name={quoteattr(etiqueta)}' if etiqueta else ''
        L.append(f'    <sequenceFlow id="{fid}" sourceRef="{a}" targetRef="{b}"{nombre}/>')
    # Uso de sistemas: asociaciones (línea punteada), no flujo de secuencia.
    for i, (a, b) in enumerate(spec['mensajes']):
        L.append(f'    <association id="As{i:02d}_{a}_{b}" sourceRef="{a}" targetRef="{b}"/>')
    L.append('  </process>')

    L.append('  <bpmndi:BPMNDiagram id="Diagrama_1">')
    L.append('    <bpmndi:BPMNPlane id="Plano_1" bpmnElement="Collab_1">')
    L.append(f'      <bpmndi:BPMNShape id="Pool_1_di" bpmnElement="Pool_1" isHorizontal="true">'
             f'<dc:Bounds x="0" y="{Y0}" width="{ancho:.0f}" height="{alto - Y0:.0f}"/></bpmndi:BPMNShape>')
    for lid, _ in spec['carriles']:
        L.append(f'      <bpmndi:BPMNShape id="{lid}_di" bpmnElement="{lid}" isHorizontal="true">'
                 f'<dc:Bounds x="30" y="{carril_y[lid]:.0f}" width="{ancho - 30:.0f}" height="{LANE_H}"/></bpmndi:BPMNShape>')
    for nid, (x, y, w, h) in cajas.items():
        L.append(f'      <bpmndi:BPMNShape id="{nid}_di" bpmnElement="{nid}">'
                 f'<dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}"/></bpmndi:BPMNShape>')
    aristas = [(fid, a, b) for fid, a, b, _ in flujos] + \
              [(f'As{i:02d}_{a}_{b}', a, b) for i, (a, b) in enumerate(spec['mensajes'])]
    for eid, a, b in aristas:
        L.append(f'      <bpmndi:BPMNEdge id="{eid}_di" bpmnElement="{eid}">')
        for x, y in _ruta_flujo(cajas[a], cajas[b], list(cajas.values())):
            L.append(f'        <di:waypoint x="{x:.0f}" y="{y:.0f}"/>')
        L.append('      </bpmndi:BPMNEdge>')
    L += ['    </bpmndi:BPMNPlane>', '  </bpmndi:BPMNDiagram>', '</definitions>']
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))


def validar(spec, modo: str) -> None:
    """Toda etapa simulada debe tener su caja en el diagrama."""
    ids = {n[0] for n in spec['nodos']}
    faltan = [e for e in p.ETAPAS if p.nodo(e, modo) not in ids]
    if faltan:
        raise ValueError(f'{modo}: etapas sin nodo en el diagrama: {faltan}')
    for a, b, _ in spec['flujos']:
        if a not in ids or b not in ids:
            raise ValueError(f'{modo}: flujo con nodo inexistente {a} -> {b}')


if __name__ == '__main__':
    for spec, modo, archivo in ((ASIS, 'AS-IS', 'AS-IS.bpmn'), (TOBE, 'TO-BE', 'TO-BE.bpmn')):
        validar(spec, modo)
        generar(spec, os.path.join(AQUI, archivo))
        print('OK', archivo)
