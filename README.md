# Demo: devoluciones y compensaciones — Subsecretaría de Ingresos de Medellín

Adaptación del demo de la Secretaría de Hacienda de Envigado (`../../SecHac_ENV/simulacion`) al proceso de devoluciones de Medellín. Se basa en las entrevistas ITM de octubre de 2025 que están en la carpeta del proyecto.

## Cómo correrlo

```bash
pip install -r requirements.txt
streamlit run app_dashboard.py      # simulador AS-IS vs TO-BE
streamlit run tablero_bitacora.py   # prototipo fase 1: tablero de términos y bitácora
python simular.py                   # informe y CSV en salidas/
python generar_bpmn.py              # regenera AS-IS.bpmn y TO-BE.bpmn
python exportar_diagramas.py        # SVG y PNG de los diagramas en salidas/
```

## Archivos

| Archivo | Qué es |
|---|---|
| `proceso.py` | **Catálogo único**: etapas, roles, fases, duraciones, rentas y rutas por tipo de trámite |
| `simular.py` | Simulación de eventos discretos + Monte Carlo |
| `generar_bpmn.py` | Genera los BPMN 2.0, que se pueden abrir en bpmn.io o Camunda Modeler |
| `bpmn_layout.py` | Visor del mapa de calor (reutilizado de Envigado) |
| `app_dashboard.py` | Dashboard del simulador |
| `terminos.py` | Motor de términos: días hábiles con festivos de Colombia (Ley Emiliani) |
| `tablero_bitacora.py` | Prototipo de expediente, tablero, alertas y bitácora (SQLite) |
| `caso/` | Diagnóstico, propuesta y preguntas para TI |
| `branding/` | Paleta **provisional** (falta el manual de identidad del Distrito) |

## Qué cambia frente al demo de Envigado

**Contenido de Medellín**
- 25 rentas, de las cuales solo predial (y una más por confirmar) tiene desarrollo en SAP. Las rentas sin SAP consolidan la información a mano y piden datos a otras unidades.
- Caídas de Mercurio, NAS e Internet como eventos aleatorios. El TO-BE **no** las elimina: reduce cuántas etapas dependen de esos sistemas.
- Brecha de contratación en enero (85 % de contratistas) y curva de aprendizaje por rotación.
- Actores propios: Notificaciones (Apoyo a Ingresos), otras unidades para estado de cuenta y cartera, Unidad Jurídica para recursos y Tesorería.

**Correcciones de método**
- **El término se mide contra la decisión notificada**, no contra el pago. En Envigado el objetivo de días se comparaba con la duración total, incluidos la ejecutoria y el pago, que no hacen parte del término del art. 855 E.T.
- **Días hábiles reales en el tablero.** Envigado contaba días calendario.
- **Calibración coherente con la entrevista.** La unidad dice que cumple los términos, así que el AS-IS cumple cerca del 88 %. El valor se muestra en esfuerzo (días-persona), en la cola de casos más lentos (P90) y en el tiempo hasta el pago.
- **Nueva métrica de carga por rol**: la capacidad que queda libre.

**Mejoras de código**
- Un solo catálogo (`proceso.py`) en lugar de cuatro diccionarios que había que mantener sincronizados a mano.
- Los BPMN se generan con rutas de flechas que no cruzan cajas, y se valida que cada etapa tenga su nodo.
- Rutas relativas: Envigado tenía `C:\Users\...` escrito en el código.

## Límites

- Todas las duraciones, cupos y probabilidades son **supuestos**. Ver `caso/…md`, sección 5, para los datos que se necesitan para calibrar.
- La identidad visual es provisional y no muestra logo.
- Los datos del tablero son ficticios.
