"""Catálogo único del proceso de devoluciones y compensaciones de la
Subsecretaría de Ingresos del Distrito de Medellín.

En el demo de Envigado el nombre de cada etapa se repetía en cuatro
diccionarios (mapeo AS-IS, mapeo TO-BE, categoría y fase), y bastaba un
error de digitación para que una etapa desapareciera del mapa de calor sin
aviso. Aquí cada etapa se declara una sola vez y el simulador, el visor
BPMN, el generador de diagramas y el tablero derivan todo de este archivo.

Fuentes:
- Entrevista a la Unidad de Devoluciones (22-oct-2025): 25 rentas, 85 %
  contratistas, sistemas Mercurio, NAS, Visor 360, Excel y tableros sin
  integración, desarrollo en SAP solo para predial y una renta más, fallas
  frecuentes de Mercurio, NAS e Internet, información que se pide a cada
  equipo "como islas".
- Entrevistas a Jurídica (las decisiones las carga otra área a mano en la
  cuenta corriente), Desarrollos Tecnológicos (cambios en SAP solo a
  través del Centro de Competencias; Power Automate y Power BI disponibles)
  y Títulos (los contratos terminan el 31 de diciembre).
- Estructura general del trámite: Estatuto Tributario nacional (arts. 855
  a 865) aplicable por remisión. Los términos del Acuerdo 093 de 2023 de
  Medellín deben validarse con la Unidad Jurídica.

TODAS las duraciones son supuestos de demostración, en días calendario
equivalentes. Deben reemplazarse por mediciones reales antes de usar las
cifras en una propuesta formal.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


# --- Roles (cupos simultáneos: personas × expedientes en paralelo) ---------
# Valores por defecto: supuestos. La entrevista no da el tamaño del equipo,
# solo que el 85 % son contratistas y que "el personal es suficiente".
ROLES: Dict[str, dict] = {
    'radicacion':     {'nombre': 'Radicación (Mercurio)',              'cupos': 3,  'contratista': True},
    'lider':          {'nombre': 'Líder y revisores de la unidad',      'cupos': 8,  'contratista': False},
    'sustanciador':   {'nombre': 'Sustanciadores de devoluciones',      'cupos': 20, 'contratista': True},
    'otras_unidades': {'nombre': 'Otras unidades (SAP, cartera)',       'cupos': 7,  'contratista': True},
    'notificaciones': {'nombre': 'Notificaciones (Apoyo a Ingresos)',   'cupos': 4,  'contratista': True},
    'juridica':       {'nombre': 'Unidad Jurídica (recursos)',          'cupos': 4,  'contratista': True},
    'finanzas':       {'nombre': 'Presupuesto y contabilidad',          'cupos': 2,  'contratista': False},
    'tesoreria':      {'nombre': 'Tesorería',                           'cupos': 3,  'contratista': False},
    'contribuyente':  {'nombre': 'Contribuyente',                       'cupos': 1000, 'contratista': False},
}


# --- Fases gruesas (colores del mapa de calor, CFD y Sankey) ----------------
# Colores funcionales, no de marca: cada fase debe distinguirse de las demás.
FASES: Dict[str, str] = {
    'Radicación y admisión':        '#3478b8',
    'Consolidación de información': '#8e5bb5',
    'Análisis y decisión':          '#d9822b',
    'Acto y notificación':          '#1a9a8a',
    'Registro y pago':              '#3f9b4a',
}
ORDEN_FASES: List[str] = list(FASES.keys())


@dataclass(frozen=True)
class Etapa:
    nombre: str
    rol: str
    fase: str
    # 'coordinacion' = traspasos, registro, búsqueda: muy reducible.
    # 'analisis'     = criterio humano: reducción moderada.
    # 'legal'        = término estatutario: no se acorta.
    categoria: str
    dur_asis: float
    dur_tobe: float
    nodo_asis: str
    nodo_tobe: str
    # True si la etapa depende de Mercurio, NAS, Visor o SAP y puede
    # detenerse por las caídas que describe la unidad.
    usa_sistemas: bool = False


# Duraciones que cambian según la renta tenga o no desarrollo en SAP.
# Sin desarrollo, el sustanciador arma la información del contribuyente a
# mano entre Mercurio, NAS, Visor 360, Excel y lo que le envían otros equipos.
CONSOLIDACION = {
    ('AS-IS', True): 2.0, ('AS-IS', False): 4.0,
    ('TO-BE', True): 1.0, ('TO-BE', False): 2.0,
}

_E = [
    # nombre, rol, fase, categoría, AS-IS, TO-BE, nodo AS-IS, nodo TO-BE, sistemas
    ('Radicación de la solicitud', 'radicacion', 'Radicación y admisión', 'coordinacion', 1.0, 0.3, 'A_Radicar', 'T_Crear_expediente', True),
    ('Reparto', 'lider', 'Radicación y admisión', 'coordinacion', 1.0, 0.2, 'A_Repartir', 'T_Repartir', False),
    ('Revisión de requisitos', 'sustanciador', 'Radicación y admisión', 'coordinacion', 2.5, 1.2, 'A_Revisar_requisitos', 'T_Checklist', True),
    ('Auto inadmisorio', 'sustanciador', 'Radicación y admisión', 'analisis', 2.0, 1.2, 'A_Auto_inadmisorio', 'T_Requerimiento', False),
    ('Notificación de la inadmisión', 'notificaciones', 'Radicación y admisión', 'coordinacion', 2.0, 0.5, 'A_Notificar_inadmision', 'T_Notificar_inadmision', True),
    ('Espera de subsanación', 'contribuyente', 'Radicación y admisión', 'legal', 8.0, 7.0, 'A_Subsanar', 'T_Subsanar', False),
    ('Revisión de subsanación', 'sustanciador', 'Radicación y admisión', 'coordinacion', 2.0, 0.8, 'A_Revisar_subsanacion', 'T_Validar_subsanacion', False),
    ('Proyección del rechazo', 'sustanciador', 'Análisis y decisión', 'analisis', 2.5, 1.8, 'A_Proyectar_rechazo', 'T_Proyectar_rechazo', False),
    ('Notificación del rechazo', 'notificaciones', 'Acto y notificación', 'coordinacion', 2.0, 0.5, 'A_Notificar_rechazo', 'T_Notificar_rechazo', True),
    ('Consolidación de información', 'sustanciador', 'Consolidación de información', 'coordinacion', 5.0, 2.0, 'A_Consolidar', 'T_Vista_360', True),
    ('Solicitud a otras unidades', 'otras_unidades', 'Consolidación de información', 'coordinacion', 4.0, 2.0, 'A_Solicitar_info', 'T_Solicitud_ANS', False),
    ('Análisis del saldo', 'sustanciador', 'Análisis y decisión', 'analisis', 10.0, 8.0, 'A_Analizar', 'T_Analizar', False),
    ('Revisión del proyecto', 'lider', 'Análisis y decisión', 'analisis', 3.0, 2.0, 'A_Revisar_proyecto', 'T_Revisar_proyecto', False),
    ('Proyección de la resolución', 'sustanciador', 'Acto y notificación', 'analisis', 3.0, 2.0, 'A_Proyectar_resolucion', 'T_Generar_resolucion', True),
    ('Revisión y firma', 'lider', 'Acto y notificación', 'analisis', 4.0, 2.5, 'A_Firmar', 'T_Firmar', False),
    ('Notificación de la resolución', 'notificaciones', 'Acto y notificación', 'coordinacion', 2.5, 1.0, 'A_Notificar_resolucion', 'T_Notificar_resolucion', True),
    ('Término de ejecutoria', 'contribuyente', 'Acto y notificación', 'legal', 10.0, 10.0, 'A_Ejecutoria', 'T_Ejecutoria', False),
    ('Interposición del recurso', 'contribuyente', 'Acto y notificación', 'legal', 30.0, 30.0, 'A_Interponer_recurso', 'T_Interponer_recurso', False),
    ('Resolución del recurso', 'juridica', 'Análisis y decisión', 'analisis', 30.0, 25.0, 'A_Resolver_recurso', 'T_Resolver_recurso', False),
    ('Notificación del recurso', 'notificaciones', 'Acto y notificación', 'coordinacion', 3.0, 1.0, 'A_Notificar_recurso', 'T_Notificar_recurso', True),
    ('Registro en cuenta corriente', 'otras_unidades', 'Registro y pago', 'coordinacion', 2.5, 1.0, 'A_Registrar_SAP', 'T_Registrar_SAP', True),
    ('Cruce con cartera', 'otras_unidades', 'Registro y pago', 'analisis', 5.0, 3.0, 'A_Cruce_cartera', 'T_Cruce_cartera', True),
    ('Orden de pago y registro contable', 'finanzas', 'Registro y pago', 'coordinacion', 3.0, 1.5, 'A_Orden_pago', 'T_Orden_pago', False),
    ('Pago y evidencia', 'tesoreria', 'Registro y pago', 'coordinacion', 3.5, 2.0, 'A_Pagar', 'T_Pagar', False),
]

ETAPAS: Dict[str, Etapa] = {e[0]: Etapa(*e) for e in _E}


# --- Tipos de trámite -------------------------------------------------------
# "objetivo" es el término para DECIDIR (resolución o rechazo notificados),
# no para pagar: 50 días hábiles para resolver devoluciones y compensaciones
# (art. 855 E.T., ≈ 70 calendario) y 15 hábiles para inadmitir o rechazar
# (art. 857-858, ≈ 21 calendario). Para las incompletas el término vuelve a
# correr desde la subsanación; se aproxima con 90 días desde la radicación.
# El recurso de reconsideración tiene su propio término de un año (art. 732),
# que aquí no se mide. Validar todo con Jurídica frente al Acuerdo 093 de 2023.
TIPOS: Dict[str, dict] = {
    'devolucion':   {'nombre': 'Devolución',                        'objetivo': 70.0, 'mezcla': 0.35},
    'compensacion': {'nombre': 'Compensación',                      'objetivo': 70.0, 'mezcla': 0.15},
    'con_cartera':  {'nombre': 'Devolución con cruce de cartera',   'objetivo': 70.0, 'mezcla': 0.12},
    'incompleta':   {'nombre': 'Solicitud incompleta (subsana)',    'objetivo': 90.0, 'mezcla': 0.18},
    'rechazo':      {'nombre': 'Rechazo',                           'objetivo': 21.0, 'mezcla': 0.08},
    'recurso':      {'nombre': 'Con recurso de reconsideración',    'objetivo': 70.0, 'mezcla': 0.12},
}

# Etapas cuyo fin marca la decisión notificada: contra ella se mide el término.
HITOS_DECISION = ('Notificación de la resolución', 'Notificación del rechazo')


def ruta(tipo: str, con_sap: bool) -> List[str]:
    """Secuencia de etapas que recorre un expediente según su tipo y según
    que su renta tenga desarrollo en SAP."""
    r = ['Radicación de la solicitud', 'Reparto', 'Revisión de requisitos']
    if tipo == 'rechazo':
        return r + ['Proyección del rechazo', 'Notificación del rechazo']
    if tipo == 'incompleta':
        r += ['Auto inadmisorio', 'Notificación de la inadmisión', 'Espera de subsanación', 'Revisión de subsanación']
    r.append('Consolidación de información')
    # Sin SAP, o cuando hay que cruzar deudas, hay que pedir el estado de
    # cuenta o la cartera a otros equipos.
    if not con_sap or tipo in ('compensacion', 'con_cartera'):
        r.append('Solicitud a otras unidades')
    r += ['Análisis del saldo', 'Revisión del proyecto', 'Proyección de la resolución',
          'Revisión y firma', 'Notificación de la resolución']
    if tipo == 'recurso':
        return r + ['Interposición del recurso', 'Resolución del recurso', 'Notificación del recurso']
    r += ['Término de ejecutoria', 'Registro en cuenta corriente']
    if tipo == 'compensacion':
        return r
    if tipo == 'con_cartera':
        r.append('Cruce con cartera')
    return r + ['Orden de pago y registro contable', 'Pago y evidencia']


def duracion(etapa: str, modo: str, con_sap: bool) -> float:
    if etapa == 'Consolidación de información':
        return CONSOLIDACION[(modo, con_sap)]
    e = ETAPAS[etapa]
    return e.dur_tobe if modo == 'TO-BE' else e.dur_asis


def nodo(etapa: str, modo: str) -> Optional[str]:
    e = ETAPAS.get(etapa)
    if e is None:
        return None
    return e.nodo_tobe if modo == 'TO-BE' else e.nodo_asis


# --- Rentas (entrevista a Devoluciones) -------------------------------------
# La unidad dice que hay desarrollo en SAP para el impuesto predial "y otro"
# (nombre ininteligible en la transcripción). Se marca solo predial;
# confirmar la segunda renta con la unidad.
RENTAS: Dict[str, bool] = {
    'Impuesto predial unificado': True,
    'Alumbrado público': False,
    'Impuesto de telefonía': False,
    'Delineación urbana': False,
    'Degüello de ganado menor': False,
    'Circulación y tránsito': False,
    'Sobretasa a la gasolina': False,
    'Tasa por estacionamiento': False,
    'Contribución especial por obra pública': False,
    'Contribución de estacionamientos de uso público': False,
    'Participación en plusvalía': False,
    'Estampilla procultura': False,
    'Estampilla para el bienestar del adulto mayor': False,
    'Estampilla Universidad de Antioquia': False,
    'Estampilla pro innovación': False,
    'Contribución de valorización': False,
    'Participación en el impuesto vehicular': False,
    'Tasa pro deporte': False,
    'Cuota de fiscalización (Contraloría)': False,
    'Otra renta (por confirmar)': False,
}
