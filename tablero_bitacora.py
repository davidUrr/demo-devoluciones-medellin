"""Prototipo de la fase 1: expediente único + tablero de términos + bitácora,
para la Unidad de Devoluciones de la Subsecretaría de Ingresos de Medellín.

No requiere integración con Mercurio, NAS, Visor 360 ni SAP: el radicado de
Mercurio se registra como referencia y se enlaza. Así el piloto puede
arrancar sin pasar por el Centro de Competencias SAP ni por nuevos
desarrollos de Innovación Digital. Guarda los datos en SQLite
(`tablero_medellin.db`); en producción iría a una base gestionada o a
SharePoint Lists / Dataverse, según lo que autorice TI.

Ejecutar con:  streamlit run tablero_bitacora.py
"""

import datetime as dt
import os
import sqlite3
import zlib
from contextlib import closing

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import proceso as p
import terminos as t
from branding import colors as marca

AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(AQUI, 'tablero_medellin.db')

ROLES = [r for r in p.ROLES if r != 'contribuyente']
ETAPAS = list(p.ETAPAS)
ESTADOS = ['activo', 'bloqueado', 'cerrado']
MOTIVOS_BLOQUEO = ['Caída de Mercurio', 'Caída de NAS o Visor 360', 'Caída de Internet o SAP',
                   'Esperando respuesta de otra unidad', 'Esperando al contribuyente',
                   'Firma pendiente', 'Otro']
# Después de notificar la decisión, el término de 50 días hábiles ya se cumplió.
ETAPAS_POST_DECISION = set(ETAPAS[ETAPAS.index('Notificación de la resolución'):]) | {'Notificación del rechazo'}

SEMAFORO = {
    'vencido': ('🔴', '#c0392b'), 'por vencer': ('🟡', '#d4a017'), 'en término': ('🟢', '#27ae60'),
    'bloqueado': ('🟠', '#d35400'), 'decidido': ('🔵', '#2c6fb0'), 'cerrado': ('⚪', '#8a9199'),
}
DIAS_ALERTA = 10  # hábiles


def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with closing(con()) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS expedientes (
            id TEXT PRIMARY KEY, radicado TEXT, contribuyente TEXT NOT NULL, renta TEXT NOT NULL,
            tipo TEXT NOT NULL, fecha_radicacion TEXT NOT NULL, termino_habiles INTEGER NOT NULL,
            etapa TEXT NOT NULL, responsable TEXT, rol TEXT, estado TEXT NOT NULL DEFAULT 'activo',
            motivo_bloqueo TEXT, bloqueado_desde TEXT, ultimo_movimiento TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS bitacora (
            id INTEGER PRIMARY KEY AUTOINCREMENT, expediente_id TEXT NOT NULL, fecha_hora TEXT NOT NULL,
            usuario TEXT NOT NULL, etapa_anterior TEXT, etapa_nueva TEXT, estado_anterior TEXT,
            estado_nuevo TEXT, comentario TEXT, documento TEXT,
            FOREIGN KEY(expediente_id) REFERENCES expedientes(id))""")
        c.commit()


def siguiente_id(c, anio):
    f = c.execute("SELECT id FROM expedientes WHERE id LIKE ? ORDER BY id DESC LIMIT 1", (f'DEV-{anio}-%',)).fetchone()
    return f"DEV-{anio}-{(int(f['id'].split('-')[-1]) + 1) if f else 1:04d}"


def crear(radicado, contribuyente, renta, tipo, fecha, etapa, responsable, rol, usuario, comentario, cuando=None):
    ahora = cuando or dt.datetime.now().isoformat(timespec='seconds')
    with closing(con()) as c:
        eid = siguiente_id(c, fecha.year)
        c.execute("INSERT INTO expedientes (id, radicado, contribuyente, renta, tipo, fecha_radicacion, termino_habiles,"
                  " etapa, responsable, rol, estado, ultimo_movimiento) VALUES (?,?,?,?,?,?,?,?,?,?, 'activo', ?)",
                  (eid, radicado, contribuyente, renta, tipo, fecha.isoformat(), t.TERMINO_HABILES[tipo],
                   etapa, responsable, rol, ahora))
        c.execute("INSERT INTO bitacora (expediente_id, fecha_hora, usuario, etapa_nueva, estado_nuevo, comentario)"
                  " VALUES (?,?,?,?, 'activo', ?)", (eid, ahora, usuario or 'Sistema', etapa, comentario or 'Expediente creado'))
        c.commit()
    return eid


def mover(exp, etapa, estado, responsable, rol, motivo, comentario, documento, usuario, cuando=None):
    ahora = cuando or dt.datetime.now().isoformat(timespec='seconds')
    desde = exp['bloqueado_desde'] if exp['estado'] == 'bloqueado' and estado == 'bloqueado' else (
        ahora[:10] if estado == 'bloqueado' else None)
    with closing(con()) as c:
        c.execute("UPDATE expedientes SET etapa=?, responsable=?, rol=?, estado=?, motivo_bloqueo=?, bloqueado_desde=?,"
                  " ultimo_movimiento=? WHERE id=?",
                  (etapa, responsable, rol, estado, motivo if estado == 'bloqueado' else None, desde, ahora, exp['id']))
        c.execute("INSERT INTO bitacora (expediente_id, fecha_hora, usuario, etapa_anterior, etapa_nueva, estado_anterior,"
                  " estado_nuevo, comentario, documento) VALUES (?,?,?,?,?,?,?,?,?)",
                  (exp['id'], ahora, usuario or 'Sistema', exp['etapa'], etapa, exp['estado'], estado, comentario, documento))
        c.commit()


def listar():
    with closing(con()) as c:
        return [dict(f) for f in c.execute("SELECT * FROM expedientes ORDER BY fecha_radicacion")]


def bitacora(eid):
    with closing(con()) as c:
        return [dict(f) for f in c.execute("SELECT * FROM bitacora WHERE expediente_id=? ORDER BY fecha_hora DESC", (eid,))]


def sembrar_demo():
    """Expedientes ficticios para la demo (nombres inventados)."""
    if listar():
        return
    hoy = dt.date.today()
    demo = [
        ('Comercializadora Demo S.A.S.', 'Impuesto predial unificado', 'devolucion', 'Análisis del saldo', 'Sustanciador 1', 'sustanciador', 30, None),
        ('Contribuyente de prueba 01', 'Alumbrado público', 'compensacion', 'Solicitud a otras unidades', 'Unidad de Títulos', 'otras_unidades', 44, 'Esperando respuesta de otra unidad'),
        ('Constructora Ejemplo Ltda.', 'Participación en plusvalía', 'con_cartera', 'Revisión del proyecto', 'Líder 1', 'lider', 80, None),
        ('Contribuyente de prueba 02', 'Estampilla procultura', 'incompleta', 'Espera de subsanación', 'Sustanciador 2', 'sustanciador', 18, None),
        ('Transportes Ficticios S.A.', 'Sobretasa a la gasolina', 'devolucion', 'Consolidación de información', 'Sustanciador 3', 'sustanciador', 47, 'Caída de NAS o Visor 360'),
        ('Contribuyente de prueba 03', 'Impuesto predial unificado', 'rechazo', 'Notificación del rechazo', 'Notificaciones', 'notificaciones', 12, None),
        ('Servicios Modelo S.A.S.', 'Contribución de valorización', 'recurso', 'Resolución del recurso', 'Unidad Jurídica', 'juridica', 120, None),
        ('Contribuyente de prueba 04', 'Impuesto de telefonía', 'devolucion', 'Proyección de la resolución', 'Sustanciador 1', 'sustanciador', 63, None),
        ('Inversiones Prueba S.A.S.', 'Estampilla Universidad de Antioquia', 'devolucion', 'Orden de pago y registro contable', 'Presupuesto', 'finanzas', 75, None),
        ('Contribuyente de prueba 05', 'Tasa por estacionamiento', 'devolucion', 'Revisión de requisitos', 'Sustanciador 2', 'sustanciador', 3, 'Caída de Mercurio'),
    ]
    for contrib, renta, tipo, etapa_actual, resp, rol, dias_atras, bloqueo in demo:
        fecha = hoy - dt.timedelta(days=dias_atras)
        con_sap = p.RENTAS.get(renta, False)
        camino = p.ruta(tipo, con_sap)
        recorrido = camino[:camino.index(etapa_actual) + 1] if etapa_actual in camino else camino[:1] + [etapa_actual]
        n = max(len(recorrido) - 1, 1)

        def cuando(i):
            return dt.datetime.combine(fecha + dt.timedelta(days=round(dias_atras * i / n)), dt.time(9)).isoformat(timespec='seconds')

        eid = crear(f'MER-{fecha:%Y}-{zlib.crc32(contrib.encode()) % 90000 + 10000}', contrib, renta, tipo, fecha,
                    recorrido[0], resp, rol, 'Semilla demo', 'Expediente de ejemplo', cuando(0))
        exp = next(e for e in listar() if e['id'] == eid)
        for i, etapa in enumerate(recorrido[1:], start=1):
            estado = 'bloqueado' if bloqueo and i == len(recorrido) - 1 else 'activo'
            mover(exp, etapa, estado, resp, rol, bloqueo, 'Avance simulado para la demo', None, 'Semilla demo', cuando(i))
            exp = next(e for e in listar() if e['id'] == eid)
        if bloqueo:  # que la demo muestre bloqueos con antigüedad
            with closing(con()) as c:
                c.execute("UPDATE expedientes SET bloqueado_desde=? WHERE id=?", ((hoy - dt.timedelta(days=6)).isoformat(), eid))
                c.commit()


def enriquecer(e, hoy):
    rad = dt.date.fromisoformat(e['fecha_radicacion'])
    e['vence'] = t.sumar_habiles(rad, e['termino_habiles'])
    e['habiles_restantes'] = t.habiles_entre(hoy, e['vence'])
    e['fase'] = p.ETAPAS[e['etapa']].fase if e['etapa'] in p.ETAPAS else 'Sin clasificar'
    e['con_sap'] = p.RENTAS.get(e['renta'], False)
    e['dias_bloqueado'] = t.habiles_entre(dt.date.fromisoformat(e['bloqueado_desde']), hoy) if e['bloqueado_desde'] else 0
    if e['estado'] == 'cerrado':
        e['semaforo'] = 'cerrado'
    elif e['estado'] == 'bloqueado':
        e['semaforo'] = 'bloqueado'
    elif e['etapa'] in ETAPAS_POST_DECISION:
        e['semaforo'] = 'decidido'
    elif e['habiles_restantes'] < 0:
        e['semaforo'] = 'vencido'
    elif e['habiles_restantes'] <= DIAS_ALERTA:
        e['semaforo'] = 'por vencer'
    else:
        e['semaforo'] = 'en término'
    return e


# --- App ---------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Tablero de devoluciones — Medellín")
init_db()
sembrar_demo()

st.sidebar.markdown(f"**{marca.ENTIDAD}**  \n{marca.DEPENDENCIA}")
st.sidebar.caption("Prototipo con datos ficticios. Identidad visual provisional.")
st.session_state.setdefault('usuario', '')
st.session_state.usuario = st.sidebar.text_input("Tu nombre (queda en la bitácora)", st.session_state.usuario)
st.sidebar.header("Filtros")
f_fase = st.sidebar.multiselect("Fase", p.ORDEN_FASES, default=p.ORDEN_FASES)
f_estado = st.sidebar.multiselect("Estado", ESTADOS, default=['activo', 'bloqueado'])
f_sap = st.sidebar.radio("Renta", ['Todas', 'Con desarrollo SAP', 'Sin desarrollo SAP'])
buscar = st.sidebar.text_input("Buscar contribuyente, ID o radicado")

st.title("Tablero de términos y bitácora — Devoluciones")
st.caption("Fase 1 de la propuesta: expediente único, responsable, término en **días hábiles** (festivos de Colombia), "
           "alertas y bitácora de cada movimiento. Funciona sin integración con Mercurio, NAS, Visor ni SAP.")

with st.expander("➕ Registrar solicitud"):
    with st.form("nuevo", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        contrib = c1.text_input("Contribuyente")
        radicado = c2.text_input("Radicado Mercurio")
        fecha = c3.date_input("Fecha de radicación", dt.date.today())
        c4, c5, c6 = st.columns(3)
        renta = c4.selectbox("Renta", list(p.RENTAS))
        tipo = c5.selectbox("Tipo de trámite", list(p.TIPOS), format_func=lambda k: p.TIPOS[k]['nombre'])
        resp = c6.text_input("Responsable")
        coment = st.text_area("Comentario")
        if st.form_submit_button("Crear expediente"):
            if not contrib:
                st.error("El contribuyente es obligatorio.")
            else:
                nuevo = crear(radicado, contrib, renta, tipo, fecha, 'Radicación de la solicitud', resp, 'radicacion',
                              st.session_state.usuario, coment)
                st.success(f"Expediente {nuevo} creado. Vence el {t.sumar_habiles(fecha, t.TERMINO_HABILES[tipo]):%d/%m/%Y}.")
                st.rerun()

hoy = dt.date.today()
exps = [enriquecer(e, hoy) for e in listar()]
abiertos = [e for e in exps if e['estado'] != 'cerrado']

k = st.columns(5)
k[0].metric("Expedientes abiertos", len(abiertos))
k[1].metric("Vencidos", sum(e['semaforo'] == 'vencido' for e in abiertos))
k[2].metric(f"Vencen en ≤ {DIAS_ALERTA} días hábiles", sum(e['semaforo'] == 'por vencer' for e in abiertos))
k[3].metric("Bloqueados", sum(e['semaforo'] == 'bloqueado' for e in abiertos))
k[4].metric("Decididos, pendientes de pago", sum(e['semaforo'] == 'decidido' for e in abiertos))

alertas = sorted([e for e in abiertos if e['semaforo'] in ('vencido', 'por vencer') or
                  (e['semaforo'] == 'bloqueado' and e['etapa'] not in ETAPAS_POST_DECISION)],
                 key=lambda e: e['habiles_restantes'])
if alertas:
    st.subheader("Alertas de hoy")
    for e in alertas:
        n = e['habiles_restantes']
        plazo = f"vencido hace {-n} días hábiles" if n < 0 else f"quedan {n} días hábiles"
        txt = (f"**{e['id']}** · {e['contribuyente']} · {e['renta']} · {e['etapa']} · vence {e['vence']:%d/%m/%Y} "
               f"({plazo})")
        if e['semaforo'] == 'bloqueado':
            st.warning(f"🟠 {txt} · bloqueado {e['dias_bloqueado']} días hábiles: {e['motivo_bloqueo']}")
        elif e['semaforo'] == 'vencido':
            st.error(f"🔴 {txt}")
        else:
            st.warning(f"🟡 {txt}")

g1, g2 = st.columns(2)
cf = {f: sum(e['fase'] == f for e in abiertos) for f in p.ORDEN_FASES}
g1.plotly_chart(go.Figure(go.Bar(x=list(cf), y=list(cf.values()), marker_color=[p.FASES[f] for f in cf]))
                .update_layout(title="Expedientes abiertos por fase", height=320), width='stretch')
motivos = {}
with closing(con()) as c:
    for f in c.execute("SELECT e.motivo_bloqueo m FROM expedientes e WHERE e.motivo_bloqueo IS NOT NULL"):
        motivos[f['m']] = motivos.get(f['m'], 0) + 1
g2.plotly_chart(go.Figure(go.Bar(y=list(motivos), x=list(motivos.values()), orientation='h', marker_color='#d35400'))
                .update_layout(title="Bloqueos por motivo (evidencia para TI)", height=320), width='stretch')

vista = [e for e in exps if e['fase'] in f_fase and e['estado'] in f_estado
         and (f_sap == 'Todas' or (f_sap == 'Con desarrollo SAP') == e['con_sap'])
         and (not buscar or buscar.lower() in f"{e['contribuyente']} {e['id']} {e['radicado']}".lower())]
st.subheader(f"Expedientes ({len(vista)} de {len(exps)})")
if vista:
    st.dataframe(pd.DataFrame([{
        'ID': e['id'], 'Radicado': e['radicado'], 'Contribuyente': e['contribuyente'], 'Renta': e['renta'],
        'SAP': 'Sí' if e['con_sap'] else 'No', 'Tipo': p.TIPOS[e['tipo']]['nombre'], 'Etapa': e['etapa'],
        'Responsable': e['responsable'] or '—', 'Vence': e['vence'].strftime('%d/%m/%Y'),
        'Hábiles restantes': e['habiles_restantes'],
        'Estado': f"{SEMAFORO[e['semaforo']][0]} {e['semaforo']}",
    } for e in sorted(vista, key=lambda e: e['habiles_restantes'])]), hide_index=True, width='stretch')
else:
    st.info("Ningún expediente coincide con los filtros.")

st.divider()
st.subheader("Detalle y bitácora")
opciones = {f"{e['id']} — {e['contribuyente']} ({e['etapa']})": e for e in exps}
exp = opciones[st.selectbox("Expediente", list(opciones))]
color = SEMAFORO[exp['semaforo']][1]
st.markdown(f"### {exp['id']} — {exp['contribuyente']}")
st.markdown(
    f"**Radicado:** {exp['radicado'] or '—'} · **Renta:** {exp['renta']} "
    f"({'con' if exp['con_sap'] else 'sin'} desarrollo SAP) · **Tipo:** {p.TIPOS[exp['tipo']]['nombre']}  \n"
    f"**Radicado el** {exp['fecha_radicacion']} · **Término:** {exp['termino_habiles']} días hábiles · "
    f"**Vence:** {exp['vence']:%d/%m/%Y} · **Restan:** {exp['habiles_restantes']} hábiles  \n"
    f"<span style='background:{color};color:#fff;padding:2px 10px;border-radius:6px;font-weight:600'>{exp['semaforo']}</span>",
    unsafe_allow_html=True)
if exp['motivo_bloqueo']:
    st.warning(f"Bloqueado desde {exp['bloqueado_desde']}: {exp['motivo_bloqueo']}")

mov = bitacora(exp['id'])
primera = {}
for m in reversed(mov):
    primera.setdefault(m['etapa_nueva'], m['fecha_hora'])
camino = p.ruta(exp['tipo'], exp['con_sap'])
st.markdown("**Camino esperado vs. recorrido**")
st.dataframe(pd.DataFrame([{
    'Etapa': et, 'Fase': p.ETAPAS[et].fase, 'Responsable típico': p.ROLES[p.ETAPAS[et].rol]['nombre'],
    'Estado': '🔵 Actual' if et == exp['etapa'] else ('✅ Hecha' if et in primera else '⚪ Pendiente'),
    'Llegó': primera.get(et, '—'),
} for et in camino]), hide_index=True, width='stretch')

ca, cb = st.columns(2)
with ca, st.form("mov"):
    st.markdown("**Registrar movimiento**")
    etapa = st.selectbox("Nueva etapa", ETAPAS, index=ETAPAS.index(exp['etapa']) if exp['etapa'] in ETAPAS else 0)
    resp = st.text_input("Responsable", exp['responsable'] or '')
    rol = st.selectbox("Rol", ROLES, index=ROLES.index(exp['rol']) if exp['rol'] in ROLES else 0,
                       format_func=lambda r: p.ROLES[r]['nombre'])
    estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(exp['estado']))
    motivo = st.selectbox("Motivo de bloqueo", MOTIVOS_BLOQUEO,
                          index=MOTIVOS_BLOQUEO.index(exp['motivo_bloqueo']) if exp['motivo_bloqueo'] in MOTIVOS_BLOQUEO else 0)
    coment = st.text_area("Comentario")
    doc = st.text_input("Documento o enlace (NAS, Mercurio)")
    if st.form_submit_button("Registrar en la bitácora"):
        mover(exp, etapa, estado, resp, rol, motivo, coment, doc, st.session_state.usuario)
        st.success("Movimiento registrado.")
        st.rerun()
with cb:
    st.markdown("**Bitácora (más reciente primero)**")
    st.dataframe(pd.DataFrame([{
        'Fecha y hora': m['fecha_hora'], 'Usuario': m['usuario'],
        'Etapa': f"{m['etapa_anterior']} → {m['etapa_nueva']}" if m['etapa_anterior'] else m['etapa_nueva'],
        'Estado': f"{m['estado_anterior']} → {m['estado_nuevo']}" if m['estado_anterior'] else m['estado_nuevo'],
        'Comentario': m['comentario'] or '', 'Documento': m['documento'] or '',
    } for m in mov]), hide_index=True, width='stretch', height=min(38 * len(mov) + 38, 420))
