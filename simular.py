"""Simulación de eventos discretos + Monte Carlo del proceso de devoluciones
y compensaciones de la Subsecretaría de Ingresos de Medellín, AS-IS frente
a TO-BE.

Conserva el motor del demo de Envigado: una cola de prioridad atiende
siempre la solicitud de recurso más temprana entre todos los expedientes,
y así el personal trabaja en paralelo. Agrega tres mecanismos que salen de
las entrevistas de Medellín:

1. Rentas con y sin desarrollo en SAP. Sin desarrollo, la consolidación
   de información es manual y hay que pedir datos a otros equipos.
2. Caídas de Mercurio, NAS e Internet ("hoy funciona, mañana no"). Las
   etapas que dependen de esos sistemas pueden detenerse. El TO-BE no
   arregla esos sistemas: reduce cuántas etapas dependen de ellos.
3. Brecha de contratación. El 85 % del equipo son contratistas y los
   contratos terminan el 31 de diciembre. Durante los primeros días del año
   solo trabajan los funcionarios de planta, y luego hay curva de
   aprendizaje por rotación.

Todas las cifras son supuestos de demostración (ver proceso.py).
"""

import csv
import datetime as dt
import heapq
import os
import random
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import proceso as p

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDAS = os.path.join(AQUI, 'salidas')

# El día 0 de la simulación es el 1 de octubre: así la primera brecha de
# contratación (enero) cae dentro del horizonte simulado.
FECHA_INICIO = dt.date(2026, 10, 1)

PARAMETROS_DEFAULT = {
    'p_rework': {'AS-IS': 0.30, 'TO-BE': 0.12},
    'pct_con_sap': 0.35,          # share de solicitudes de rentas con desarrollo SAP (supuesto; predial pesa mucho)
    'p_falla': 0.25,              # prob. de que una etapa con sistemas sufra una caída
    'brecha_dias': 20,            # días de enero sin contratistas (supuesto)
    'pct_contratistas': 0.85,     # entrevista a Devoluciones
    'rotacion': 0.30,             # share de contratistas nuevos tras la brecha (supuesto)
    'dias_curva': 60,             # duración de la curva de aprendizaje (supuesto)
}

# Bucles de retorno (red de Petri): la revisión devuelve el trabajo.
REWORK = {
    'Revisión de subsanación': ['Auto inadmisorio', 'Notificación de la inadmisión',
                                'Espera de subsanación', 'Revisión de subsanación'],
    'Revisión del proyecto': ['Análisis del saldo', 'Revisión del proyecto'],
    'Revisión y firma': ['Proyección de la resolución', 'Revisión y firma'],
}

COMPONENTES = [
    ('Coordinación y traspaso', 'dias_coordinacion'),
    ('Análisis y criterio humano', 'dias_analisis'),
    ('Términos legales', 'dias_legal'),
    ('Cola por capacidad', 'dias_cola'),
    ('Caídas de sistemas', 'dias_sistemas'),
    ('Brecha de contratación', 'dias_brecha'),
]


@dataclass
class Case:
    case_id: str
    kind: str
    arrival: float
    target: float
    con_sap: bool


@dataclass
class RunResult:
    case: Case
    completion: float
    elapsed: float          # radicación → cierre (pago, compensación o recurso resuelto)
    dias_decision: float    # radicación → decisión notificada (lo que mide el término legal)
    late: float             # atraso de la decisión frente al término
    touches: int
    rework: int
    esperas: int
    path: str
    dias_coordinacion: float = 0.0
    dias_analisis: float = 0.0
    dias_legal: float = 0.0
    dias_cola: float = 0.0
    dias_sistemas: float = 0.0
    dias_brecha: float = 0.0
    # Días de trabajo que el expediente consume de cada rol (incluye caídas
    # de sistemas, porque la persona queda detenida). Mide capacidad liberada.
    carga: Dict[str, float] = None


def ventanas_brecha(brecha_dias: int, max_dias: int) -> List[Tuple[float, float]]:
    ventanas = []
    anio = FECHA_INICIO.year + 1
    while True:
        ini = (dt.date(anio, 1, 1) - FECHA_INICIO).days
        if ini > max_dias:
            return ventanas
        if brecha_dias > 0:
            ventanas.append((float(ini), float(ini + brecha_dias)))
        anio += 1


def _en_ventana(t: float, ventanas) -> Optional[Tuple[float, float]]:
    for v in ventanas:
        if v[0] <= t < v[1]:
            return v
    return None


def etapas_caso(case: Case, modo: str, p_rework: float, rng: random.Random):
    """Ruta del expediente con reprocesos ya resueltos."""
    nombres = p.ruta(case.kind, case.con_sap)
    resultado, reprocesos = [], 0
    for n in nombres:
        resultado.append(n)
        tramo = REWORK.get(n)
        if tramo and rng.random() < p_rework:
            tramo_presente = [t for t in tramo if t in nombres]
            if len(tramo_presente) > 1:
                reprocesos += 1
                resultado += tramo_presente
    return resultado, reprocesos


def muestrear(modo_valor: float, rng: random.Random, spread: float = 0.35) -> float:
    return rng.triangular(modo_valor * (1 - spread), modo_valor * (1 + spread), modo_valor)


def simular(modo: str, cases: List[Case], params: dict, capacidades: Dict[str, int],
            rng: random.Random, max_dias: int = 2500, registrar_historial: bool = True):
    prm = {**PARAMETROS_DEFAULT, **params}
    p_rework = prm['p_rework'][modo] if isinstance(prm['p_rework'], dict) else prm['p_rework']
    ventanas = ventanas_brecha(int(prm['brecha_dias']), max_dias)
    curva_extra = prm['rotacion'] * (0.5 if modo == 'AS-IS' else 0.25)

    disponible = {rol: [0.0] * max(1, cap) for rol, cap in capacidades.items()}
    # Cupos de planta por rol: los primeros índices. El resto son contratistas.
    planta = {}
    for rol, cap in capacidades.items():
        if p.ROLES[rol]['contratista']:
            planta[rol] = max(1, round(cap * (1 - prm['pct_contratistas'])))
        else:
            planta[rol] = cap

    hist_nodo = {d: {} for d in range(max_dias)} if registrar_historial else {}
    hist_rol = {d: {} for d in range(max_dias)} if registrar_historial else {}
    entradas_nodo, entradas_rol = {}, {}

    estado, heap, cont = {}, [], 0
    for c in cases:
        etapas, rework = etapas_caso(c, modo, p_rework, rng)
        estado[c.case_id] = {
            'case': c, 'etapas': etapas, 'paso': 0, 'touches': 0, 'esperas': 0,
            'rework': rework + (1 if c.kind == 'incompleta' else 0), 'nombres': [],
            'en_nodo': {}, 'en_rol': {},
            'dias': {k: 0.0 for _, k in COMPONENTES},
            'carga': {},
            'hito': None,
        }
        heapq.heappush(heap, (c.arrival, cont, c.case_id))
        cont += 1

    resultados = {}
    while heap:
        now, _, cid = heapq.heappop(heap)
        st = estado[cid]
        c = st['case']
        nombre = st['etapas'][st['paso']]
        etapa = p.ETAPAS[nombre]
        rol = etapa.rol

        # Elegir el cupo que pueda empezar antes, considerando la brecha.
        mejor = None
        for idx, libre in enumerate(disponible[rol]):
            inicio = max(now, libre)
            empuje = 0.0
            if idx >= planta[rol]:
                v = _en_ventana(inicio, ventanas)
                if v:
                    empuje = v[1] - inicio
                    inicio = v[1]
            if mejor is None or inicio < mejor[1]:
                mejor = (idx, inicio, empuje)
        idx, inicio, empuje = mejor

        espera = inicio - now
        if espera > 1e-9 and rol != 'contribuyente':
            st['esperas'] += 1
            st['dias']['dias_brecha'] += empuje
            st['dias']['dias_cola'] += espera - empuje

        dur = muestrear(p.duracion(nombre, modo, c.con_sap), rng)
        # Curva de aprendizaje de contratistas nuevos tras la brecha.
        if p.ROLES[rol]['contratista'] and idx >= planta[rol]:
            if any(v[1] <= inicio < v[1] + prm['dias_curva'] for v in ventanas):
                dur *= 1 + curva_extra
        st['dias']['dias_' + etapa.categoria] += dur

        caida = 0.0
        if etapa.usa_sistemas and rng.random() < prm['p_falla']:
            caida = rng.triangular(0.5, 3.0, 1.0)
            st['dias']['dias_sistemas'] += caida

        fin = inicio + dur + caida
        disponible[rol][idx] = fin
        if rol != 'contribuyente':
            st['carga'][rol] = st['carga'].get(rol, 0.0) + dur + caida

        if registrar_historial:
            d0 = min(int(inicio), max_dias - 1)
            d1 = min(int(fin) + 1, max_dias)
            st['en_rol'].setdefault(rol, d0)
            nid = p.nodo(nombre, modo)
            st['en_nodo'].setdefault(nid, d0)
            for d in range(d0, d1):
                hist_rol[d][rol] = hist_rol[d].get(rol, 0) + 1
                hist_nodo[d][nid] = hist_nodo[d].get(nid, 0) + 1

        if st['hito'] is None and nombre in p.HITOS_DECISION:
            st['hito'] = fin
        st['nombres'].append(nombre)
        st['touches'] += 1
        st['paso'] += 1
        if st['paso'] < len(st['etapas']):
            heapq.heappush(heap, (fin, cont, cid))
            cont += 1
        else:
            if registrar_historial:
                entradas_nodo[cid] = st['en_nodo']
                entradas_rol[cid] = st['en_rol']
            elapsed = fin - c.arrival
            decision = (st['hito'] if st['hito'] is not None else fin) - c.arrival
            resultados[cid] = RunResult(
                c, fin, elapsed, decision, max(0.0, decision - c.target), st['touches'], st['rework'],
                st['esperas'], ' → '.join(st['nombres']), **st['dias'], carga=st['carga'],
            )

    res = [resultados[c.case_id] for c in sorted(cases, key=lambda c: c.arrival)]
    return res, hist_nodo, hist_rol, entradas_nodo, entradas_rol


def generar_casos(n: int, mezcla: Dict[str, float], dias_entre_llegadas: float,
                  pct_con_sap: float, rng: random.Random) -> List[Case]:
    tipos, pesos = list(mezcla), list(mezcla.values())
    casos, t = [], 0.0
    for i in range(1, n + 1):
        if i > 1:
            t += rng.expovariate(1.0 / max(dias_entre_llegadas, 1e-6))
        k = rng.choices(tipos, weights=pesos, k=1)[0]
        casos.append(Case(f'DEV-{i:04d}', k, t, p.TIPOS[k]['objetivo'], rng.random() < pct_con_sap))
    return casos


def metricas(rows: List[RunResult]) -> dict:
    dur = [r.elapsed for r in rows]
    m = {
        'casos': len(rows),
        'decision_promedio': statistics.mean(r.dias_decision for r in rows),
        'decision_p90': percentil([r.dias_decision for r in rows], 90),
        'duracion_promedio': statistics.mean(dur),
        'duracion_mediana': statistics.median(dur),
        'duracion_minima': min(dur),
        'duracion_maxima': max(dur),
        'pct_a_tiempo': 100 * sum(1 for r in rows if r.late <= 0) / len(rows),
        'casos_con_atraso': sum(1 for r in rows if r.late > 0),
        'atraso_total': sum(r.late for r in rows),
        'toques_promedio': statistics.mean(r.touches for r in rows),
        'reprocesos': sum(r.rework for r in rows),
        'esperas_total': sum(r.esperas for r in rows),
    }
    for rol in p.ROLES:
        if rol != 'contribuyente':
            m['carga_' + rol] = statistics.mean(r.carga.get(rol, 0.0) for r in rows)
    m['carga_total'] = statistics.mean(sum(r.carga.values()) for r in rows)
    for _, k in COMPONENTES:
        m[k + '_promedio'] = statistics.mean(getattr(r, k) for r in rows)
    return m


def percentil(valores: List[float], q: float) -> float:
    if not valores:
        return 0.0
    v = sorted(valores)
    k = (len(v) - 1) * q / 100
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def monte_carlo(modo: str, n_replicas: int, n_casos: int, mezcla: Dict[str, float],
                dias_entre_llegadas: float, capacidades: Dict[str, int], params: dict,
                seed_base: int = 42, max_dias: int = 2500) -> dict:
    """Mismas semillas en AS-IS y TO-BE: los dos escenarios reciben los
    mismos expedientes (tipo, llegada, renta), así la comparación es justa."""
    prm = {**PARAMETROS_DEFAULT, **params}
    replicas, ref = [], None
    for r in range(n_replicas):
        rng_casos = random.Random(seed_base + r)
        casos = generar_casos(n_casos, mezcla, dias_entre_llegadas, prm['pct_con_sap'], rng_casos)
        rng = random.Random((seed_base + r) * 7919 + (0 if modo == 'AS-IS' else 1))
        out = simular(modo, casos, prm, capacidades, rng, max_dias, registrar_historial=(r == 0))
        replicas.append(metricas(out[0]))
        if r == 0:
            ref = out
    return {
        'replicas': replicas,
        'resultados_referencia': ref[0],
        'historial_referencia': ref[1],
        'historial_rol_referencia': ref[2],
        'primeras_entradas_nodo_referencia': ref[3],
        'primeras_entradas_rol_referencia': ref[4],
    }


def capacidades_default() -> Dict[str, int]:
    return {rol: d['cupos'] for rol, d in p.ROLES.items()}


def mezcla_default() -> Dict[str, float]:
    return {k: d['mezcla'] for k, d in p.TIPOS.items()}


# --- Salidas de línea de comandos -------------------------------------------

def _pct(a, b):
    return (a - b) / a * 100 if a else 0.0


def guardar_informe(ra: dict, rt: dict, n_replicas: int, n_casos: int, llegadas: float) -> str:
    def prom(res, k):
        return statistics.mean(x[k] for x in res['replicas'])

    os.makedirs(SALIDAS, exist_ok=True)
    ruta = os.path.join(SALIDAS, 'informe_simulacion.md')
    filas = [
        ('Días hasta la decisión notificada (promedio)', 'decision_promedio', ' días'),
        ('Días hasta la decisión, percentil 90', 'decision_p90', ' días'),
        ('% de decisiones dentro del término', 'pct_a_tiempo', ' %'),
        ('Decisiones fuera del término', 'casos_con_atraso', ''),
        ('Atraso total acumulado', 'atraso_total', ' días'),
        ('Días hasta el cierre (pago o compensación)', 'duracion_promedio', ' días'),
        ('Reprocesos', 'reprocesos', ''),
        ('Esperas por recurso ocupado', 'esperas_total', ''),
        ('Días-persona de trabajo por expediente', 'carga_total', ''),
        ('… de ellos, de sustanciador', 'carga_sustanciador', ''),
    ]
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('# Simulación demostrativa: devoluciones y compensaciones — Subsecretaría de Ingresos de Medellín\n\n')
        f.write(f'{n_replicas} réplicas Monte Carlo de {n_casos} expedientes cada una, con un expediente cada '
                f'{llegadas:g} días en promedio. Las cifras son **promedios entre réplicas** y resultan de '
                'supuestos de demostración: no son una línea base institucional.\n\n')
        f.write('## Resultados\n\n| Indicador | AS-IS | TO-BE | Cambio |\n|---|---:|---:|---:|\n')
        for et, k, suf in filas:
            a, b = prom(ra, k), prom(rt, k)
            cambio = b - a if k == 'pct_a_tiempo' else -_pct(a, b)
            unidad = ' pp' if k == 'pct_a_tiempo' else ' %'
            f.write(f'| {et} | {a:.1f}{suf} | {b:.1f}{suf} | {cambio:+.1f}{unidad} |\n')
        f.write('\n## Composición del tiempo promedio por expediente\n\n| Componente | AS-IS | TO-BE | Cambio |\n|---|---:|---:|---:|\n')
        for et, k in COMPONENTES:
            a, b = prom(ra, k + '_promedio'), prom(rt, k + '_promedio')
            f.write(f'| {et} | {a:.1f} días | {b:.1f} días | {-_pct(a, b):+.1f} % |\n')
        f.write('\n## Cómo leerlo\n\n'
                '- **Coordinación y traspaso** es lo que atacan el expediente único, el reparto por reglas, la vista 360 '
                'y las solicitudes con acuerdo de servicio (ANS) a otras unidades.\n'
                '- **Análisis y criterio humano** baja poco: la decisión sigue siendo de un funcionario.\n'
                '- **Términos legales** no se acortan; el TO-BE solo evita que se venzan sin control.\n'
                '- **Caídas de sistemas**: el TO-BE no arregla Mercurio ni la NAS, pero reduce cuántas etapas dependen de ellos.\n'
                '- **Brecha de contratación**: depende de la política de contratación, no de la herramienta. El TO-BE '
                'solo acorta la curva de aprendizaje (checklist guiado y bitácora).\n\n'
                '## Datos que se necesitan para calibrarlo\n\n'
                'Por expediente y etapa, de al menos 6 meses: fecha de entrada y salida, renta, tipo de solicitud, '
                'responsable, devoluciones internas, fecha de notificación, ejecutoria, orden de pago y pago; además, '
                'número de personas por rol, días de caída de Mercurio, NAS y SAP, y fechas reales de inicio de contratos.\n')
    return ruta


def guardar_csv(ref_asis: List[RunResult], ref_tobe: List[RunResult]) -> str:
    os.makedirs(SALIDAS, exist_ok=True)
    ruta = os.path.join(SALIDAS, 'expedientes_replica_referencia.csv')
    with open(ruta, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['modo', 'expediente', 'tipo', 'renta_con_sap', 'llegada', 'terminacion', 'dias_hasta_decision',
                    'dias_hasta_cierre', 'atraso_decision',
                    'toques', 'reprocesos'] + [k for _, k in COMPONENTES] + ['ruta'])
        for modo, rows in (('AS-IS', ref_asis), ('TO-BE', ref_tobe)):
            for r in rows:
                w.writerow([modo, r.case.case_id, r.case.kind, 'sí' if r.case.con_sap else 'no',
                            round(r.case.arrival, 2), round(r.completion, 2), round(r.dias_decision, 2),
                            round(r.elapsed, 2), round(r.late, 2),
                            r.touches, r.rework] + [round(getattr(r, k), 2) for _, k in COMPONENTES] + [r.path])
    return ruta


if __name__ == '__main__':
    N_REP, N_CASOS, LLEGADAS = 100, 80, 1.2
    caps, mezcla = capacidades_default(), mezcla_default()
    ra = monte_carlo('AS-IS', N_REP, N_CASOS, mezcla, LLEGADAS, caps, {})
    rt = monte_carlo('TO-BE', N_REP, N_CASOS, mezcla, LLEGADAS, caps, {})
    print(guardar_informe(ra, rt, N_REP, N_CASOS, LLEGADAS))
    print(guardar_csv(ra['resultados_referencia'], rt['resultados_referencia']))
    for modo, res in (('AS-IS', ra), ('TO-BE', rt)):
        m = {k: round(statistics.mean(x[k] for x in res['replicas']), 1)
             for k in ('decision_promedio', 'decision_p90', 'duracion_promedio', 'pct_a_tiempo', 'dias_cola_promedio', 'dias_sistemas_promedio',
                       'dias_brecha_promedio', 'dias_coordinacion_promedio', 'dias_analisis_promedio',
                       'carga_total', 'carga_sustanciador')}
        print(modo, m)
