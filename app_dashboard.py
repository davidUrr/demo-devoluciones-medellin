"""Simulador AS-IS vs TO-BE: devoluciones y compensaciones, Subsecretaría
de Ingresos de Medellín. Ejecutar con:  streamlit run app_dashboard.py"""

import os
import statistics

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import bpmn_layout as bl
import proceso as p
import simular as sim
from branding import colors as marca

AQUI = os.path.dirname(os.path.abspath(__file__))
COLOR_ASIS, COLOR_TOBE = marca.COLOR_ASIS, marca.COLOR_TOBE

st.set_page_config(layout="wide", page_title="Simulador de devoluciones — Medellín")
st.sidebar.markdown(f"**{marca.ENTIDAD}**  \n{marca.DEPENDENCIA}")
st.sidebar.caption("Demo con supuestos. Identidad visual provisional.")


@st.cache_data(show_spinner=False)
def cargar_layout(archivo: str) -> bl.Layout:
    return bl.parse_bpmn_di(os.path.join(AQUI, archivo))


@st.cache_data(show_spinner="Corriendo réplicas Monte Carlo…")
def correr(modo, n_replicas, n_casos, mezcla_items, llegadas, caps_items, params_items, seed, _v=1):
    return sim.monte_carlo(modo, n_replicas, n_casos, dict(mezcla_items), llegadas,
                           dict(caps_items), dict(params_items), seed_base=seed)


def prom(res, clave):
    return statistics.mean(r[clave] for r in res['replicas'])


# --- Controles ---------------------------------------------------------------
sb = st.sidebar
sb.header("Volumen")
n_casos = sb.slider("Expedientes por réplica", 20, 300, 80, step=10)
llegadas = sb.slider("Días promedio entre solicitudes", 0.3, 5.0, 1.2, step=0.1)
n_replicas = sb.slider("Réplicas Monte Carlo", 20, 300, 80, step=10)
seed = sb.number_input("Semilla", 0, 9999, 42)

sb.header("Realidad de Medellín")
pct_sap = sb.slider("% de solicitudes de rentas con desarrollo en SAP", 0, 100, 35,
                    help="Hoy solo predial (y una renta más por confirmar) tienen desarrollo en SAP, de 25 rentas.") / 100
p_falla = sb.slider("Prob. de caída de Mercurio/NAS/Internet por etapa", 0, 60, 25,
                    help="La unidad reporta: \"hoy funciona, mañana no\".") / 100
brecha = sb.slider("Días de enero sin contratistas", 0, 45, 20,
                   help="Los contratos terminan el 31 de diciembre; 85 % del equipo es contratista.")
rotacion = sb.slider("% de contratistas nuevos tras la brecha", 0, 100, 30) / 100

with sb.expander("Mezcla de trámites (%)"):
    mezcla_pct = {k: st.slider(d['nombre'], 0, 100, int(d['mezcla'] * 100), key='mz_' + k)
                  for k, d in p.TIPOS.items()}
total = sum(mezcla_pct.values()) or 1
mezcla = {k: v / total for k, v in mezcla_pct.items()}

with sb.expander("Probabilidad de reproceso"):
    rw_asis = st.slider("AS-IS", 0.0, 0.8, sim.PARAMETROS_DEFAULT['p_rework']['AS-IS'], 0.05)
    rw_tobe = st.slider("TO-BE", 0.0, 0.8, sim.PARAMETROS_DEFAULT['p_rework']['TO-BE'], 0.05)

with sb.expander("Cupos simultáneos por rol"):
    caps = {rol: (d['cupos'] if rol == 'contribuyente' else st.slider(d['nombre'], 1, 40, d['cupos'], key='cap_' + rol))
            for rol, d in p.ROLES.items()}

vigiladas = sb.multiselect("Etapas a vigilar en el diagrama", list(p.ETAPAS),
                           default=['Consolidación de información', 'Solicitud a otras unidades', 'Análisis del saldo'])

base = {'pct_con_sap': pct_sap, 'p_falla': p_falla, 'brecha_dias': brecha, 'rotacion': rotacion}
args = (n_replicas, n_casos, tuple(sorted(mezcla.items())), llegadas, tuple(sorted(caps.items())))
ra = correr('AS-IS', *args, tuple(sorted({**base, 'p_rework': rw_asis}.items())), seed)
rt = correr('TO-BE', *args, tuple(sorted({**base, 'p_rework': rw_tobe}.items())), seed)

# --- Encabezado y KPIs -------------------------------------------------------
st.title("Devoluciones y compensaciones — AS-IS vs TO-BE")
st.caption(f"{marca.ENTIDAD} · {marca.DEPENDENCIA}. {n_replicas} réplicas × {n_casos} expedientes. "
           "Cifras ilustrativas: resultan de supuestos (proceso.py), no de mediciones.")
st.info(
    "La unidad dice que hoy **casi siempre cumple los términos**, a costa de trabajo manual. "
    "Por eso el valor del TO-BE se ve menos en el % a tiempo y más en el **esfuerzo por expediente**, "
    "el **riesgo de la cola** (percentil 90) y el **tiempo hasta el pago**."
)

kpis = [
    ("Días hasta la decisión (promedio)", 'decision_promedio', " d", True),
    ("Días hasta la decisión — P90", 'decision_p90', " d", True),
    ("% decisiones en término", 'pct_a_tiempo', " %", False),
    ("Días hasta el pago o cierre", 'duracion_promedio', " d", True),
    ("Días-persona por expediente", 'carga_total', "", True),
]
for col, (et, k, suf, menor) in zip(st.columns(len(kpis)), kpis):
    a, b = prom(ra, k), prom(rt, k)
    if k == 'pct_a_tiempo':
        delta = f"{b - a:+.1f} pp vs AS-IS ({a:.0f}{suf})"
    else:
        delta = f"{(b - a) / a * 100 if a else 0:+.0f} % vs AS-IS ({a:.0f}{suf})"
    col.metric(f"{et} — TO-BE", f"{b:.0f}{suf}", delta, delta_color="inverse" if menor else "normal")

st.divider()

# --- Mapa de calor sobre el BPMN ---------------------------------------------
st.subheader("Mapa de calor sobre el BPMN (réplica de referencia)")
st.caption("Color = fase · más opaco = más expedientes ese día · rueda para zoom, arrastrar para mover, ▶ para animar. "
           "Las cajas grises son sistemas o pasos que no se simulan.")
lay_a, lay_t = cargar_layout('AS-IS.bpmn'), cargar_layout('TO-BE.bpmn')
buck_a = bl.construir_bucket_por_nodo({e: p.nodo(e, 'AS-IS') for e in p.ETAPAS})
buck_t = bl.construir_bucket_por_nodo({e: p.nodo(e, 'TO-BE') for e in p.ETAPAS})
orden_roles = [r for r in p.ROLES if r != 'contribuyente']
nombre_rol = {r: p.ROLES[r]['nombre'] for r in orden_roles}


def con_nombres(hist_rol, entradas_rol):
    # El visor muestra las claves tal cual: se traducen a nombres legibles.
    h = {d: {nombre_rol.get(k, k): v for k, v in fila.items()} for d, fila in hist_rol.items()}
    e = {c: {nombre_rol.get(k, k): v for k, v in fila.items()} for c, fila in entradas_rol.items()}
    return h, e


hr_a, er_a = con_nombres(ra['historial_rol_referencia'], ra['primeras_entradas_rol_referencia'])
hr_t, er_t = con_nombres(rt['historial_rol_referencia'], rt['primeras_entradas_rol_referencia'])
html = bl.render_comparativo(
    lay_a, ra['historial_referencia'], buck_a, lay_t, rt['historial_referencia'], buck_t,
    altura=560, puntos_interes=[(e, p.nodo(e, 'AS-IS'), p.nodo(e, 'TO-BE')) for e in vigiladas],
    primeras_entradas_nodo_asis=ra['primeras_entradas_nodo_referencia'],
    primeras_entradas_nodo_tobe=rt['primeras_entradas_nodo_referencia'],
    historial_rol_asis=hr_a, historial_rol_tobe=hr_t,
    primeras_entradas_rol_asis=er_a, primeras_entradas_rol_tobe=er_t,
    orden_roles=[nombre_rol[r] for r in orden_roles],
)
st.iframe(html, height=950 + 60 * -(-max(len(vigiladas), 1) // 5) + 150)

st.divider()
t1, t2, t3, t4, t5, t6 = st.tabs([
    "Composición del tiempo", "Carga por rol", "Rentas con y sin SAP",
    "Distribución", "Flujo acumulado", "Ficha por expediente",
])

with t1:
    fig = go.Figure()
    for modo, res, color in (('AS-IS', ra, COLOR_ASIS), ('TO-BE', rt, COLOR_TOBE)):
        vals = [prom(res, k + '_promedio') for _, k in sim.COMPONENTES]
        fig.add_trace(go.Bar(x=[n for n, _ in sim.COMPONENTES], y=vals, name=modo, marker_color=color,
                             text=[f"{v:.1f}" for v in vals], textposition='outside'))
    fig.update_layout(barmode='group', yaxis_title="Días promedio por expediente", height=420)
    st.plotly_chart(fig, width='stretch')
    st.markdown(
        "- **Coordinación y traspaso**: lo que atacan el expediente único, el reparto por reglas, la vista 360 y las solicitudes con ANS.\n"
        "- **Análisis y criterio humano**: baja poco; decide un funcionario.\n"
        "- **Términos legales**: no se acortan; el TO-BE evita que se venzan sin control.\n"
        "- **Caídas de sistemas**: el TO-BE no arregla Mercurio ni la NAS; solo depende de ellos en menos etapas.\n"
        "- **Brecha de contratación**: la resuelve la política de contratación, no la herramienta."
    )

with t2:
    filas = []
    for rol in orden_roles:
        a, b = prom(ra, 'carga_' + rol), prom(rt, 'carga_' + rol)
        filas.append({'Rol': p.ROLES[rol]['nombre'], 'AS-IS': round(a, 1), 'TO-BE': round(b, 1),
                      'Liberado': f"{(a - b) / a * 100 if a else 0:.0f} %"})
    df = pd.DataFrame(filas)
    fig = go.Figure([go.Bar(y=df['Rol'], x=df['AS-IS'], name='AS-IS', orientation='h', marker_color=COLOR_ASIS),
                     go.Bar(y=df['Rol'], x=df['TO-BE'], name='TO-BE', orientation='h', marker_color=COLOR_TOBE)])
    fig.update_layout(barmode='group', xaxis_title="Días de trabajo por expediente", height=420,
                      yaxis=dict(autorange='reversed'))
    st.plotly_chart(fig, width='stretch')
    st.dataframe(df, hide_index=True, width='stretch')
    anual = 365 / llegadas
    a, b = prom(ra, 'carga_sustanciador'), prom(rt, 'carga_sustanciador')
    st.caption(f"Con una solicitud cada {llegadas:g} días (≈ {anual:.0f} al año), el TO-BE liberaría ≈ "
               f"{(a - b) * anual:,.0f} días-cupo de sustanciador al año. Es capacidad para más rentas o para "
               "absorber la brecha de enero, no necesariamente menos personas.")

with t3:
    st.caption("Mismos expedientes de la réplica de referencia, separados por si su renta tiene desarrollo en SAP.")
    filas = []
    for modo, res in (('AS-IS', ra), ('TO-BE', rt)):
        for con in (True, False):
            rows = [r for r in res['resultados_referencia'] if r.case.con_sap == con]
            if rows:
                filas.append({'Escenario': modo, 'Renta': 'Con SAP' if con else 'Sin SAP', 'Expedientes': len(rows),
                              'Días a decisión': round(statistics.mean(r.dias_decision for r in rows), 1),
                              'Días-persona': round(statistics.mean(sum(r.carga.values()) for r in rows), 1),
                              'Coordinación (d)': round(statistics.mean(r.dias_coordinacion for r in rows), 1)})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width='stretch')
    st.markdown("Las rentas sin desarrollo en SAP son las que más ganan con la vista 360 y las solicitudes con ANS. "
                "Eso sostiene empezar por una capa de orquestación **sin esperar** al Centro de Competencias SAP.")

with t4:
    fig = go.Figure([go.Box(y=[r['decision_promedio'] for r in ra['replicas']], name='AS-IS', marker_color=COLOR_ASIS, boxmean=True),
                     go.Box(y=[r['decision_promedio'] for r in rt['replicas']], name='TO-BE', marker_color=COLOR_TOBE, boxmean=True)])
    fig.update_layout(yaxis_title="Días promedio hasta la decisión, por réplica", showlegend=False)
    st.plotly_chart(fig, width='stretch')

with t5:
    ca, cb = st.columns(2)
    for col, titulo, res, buck in ((ca, 'AS-IS', ra, buck_a), (cb, 'TO-BE', rt, buck_t)):
        hist = res['historial_referencia']
        ultimo = max((d for d, v in hist.items() if v), default=0)
        fig = go.Figure()
        for fase in p.ORDEN_FASES:
            y = [sum(c for n, c in hist[d].items() if buck.get(n) == fase) for d in range(ultimo + 1)]
            fig.add_trace(go.Scatter(x=list(range(ultimo + 1)), y=y, name=fase, stackgroup='a', mode='lines',
                                     line=dict(width=0.5, color=p.FASES[fase])))
        fig.update_layout(title=f"Expedientes en curso por fase — {titulo}", xaxis_title="Día", yaxis_title="Expedientes")
        col.plotly_chart(fig, width='stretch')
    st.caption("La capa que crece es un cuello de botella. El día 92 empieza la brecha de contratación de enero.")

with t6:
    tobe = {r.case.case_id: r for r in rt['resultados_referencia']}
    filas = []
    for r in ra['resultados_referencia']:
        q = tobe[r.case.case_id]
        filas.append({'Expediente': r.case.case_id, 'Tipo': p.TIPOS[r.case.kind]['nombre'],
                      'Renta con SAP': 'Sí' if r.case.con_sap else 'No', 'Término (d)': r.case.target,
                      'Decisión AS-IS': round(r.dias_decision, 1), 'Decisión TO-BE': round(q.dias_decision, 1),
                      'Cierre AS-IS': round(r.elapsed, 1), 'Cierre TO-BE': round(q.elapsed, 1),
                      'En término AS-IS': 'Sí' if r.late <= 0 else 'No', 'En término TO-BE': 'Sí' if q.late <= 0 else 'No'})
    st.dataframe(pd.DataFrame(filas).sort_values('Decisión AS-IS', ascending=False), hide_index=True, width='stretch')
