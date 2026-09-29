# Simulación demostrativa: devoluciones y compensaciones — Subsecretaría de Ingresos de Medellín

100 réplicas Monte Carlo de 80 expedientes cada una, con un expediente cada 1.2 días en promedio. Las cifras son **promedios entre réplicas** y resultan de supuestos de demostración: no son una línea base institucional.

## Resultados

| Indicador | AS-IS | TO-BE | Cambio |
|---|---:|---:|---:|
| Días hasta la decisión notificada (promedio) | 52.4 días | 27.0 días | -48.5 % |
| Días hasta la decisión, percentil 90 | 75.9 días | 39.5 días | -47.9 % |
| % de decisiones dentro del término | 88.7 % | 99.9 % | +11.2 pp |
| Decisiones fuera del término | 9.1 | 0.1 | -99.0 % |
| Atraso total acumulado | 61.0 días | 0.1 días | -99.8 % |
| Días hasta el cierre (pago o compensación) | 78.0 días | 46.8 días | -40.0 % |
| Reprocesos | 61.1 | 33.6 | -45.0 % |
| Esperas por recurso ocupado | 342.0 | 83.3 | -75.7 % |
| Días-persona de trabajo por expediente | 52.4 | 30.2 | -42.4 % |
| … de ellos, de sustanciador | 23.8 | 14.7 | -38.1 % |

## Composición del tiempo promedio por expediente

| Componente | AS-IS | TO-BE | Cambio |
|---|---:|---:|---:|
| Coordinación y traspaso | 20.7 días | 9.1 días | -56.1 % |
| Análisis y criterio humano | 29.4 días | 18.9 días | -35.8 % |
| Términos legales | 13.5 días | 13.0 días | -3.5 % |
| Cola por capacidad | 8.3 días | 2.5 días | -70.4 % |
| Caídas de sistemas | 2.4 días | 2.3 días | -3.8 % |
| Brecha de contratación | 3.7 días | 1.1 días | -71.1 % |

## Cómo leerlo

- **Coordinación y traspaso** es lo que atacan el expediente único, el reparto por reglas, la vista 360 y las solicitudes con acuerdo de servicio (ANS) a otras unidades.
- **Análisis y criterio humano** baja poco: la decisión sigue siendo de un funcionario.
- **Términos legales** no se acortan; el TO-BE solo evita que se venzan sin control.
- **Caídas de sistemas**: el TO-BE no arregla Mercurio ni la NAS, pero reduce cuántas etapas dependen de ellos.
- **Brecha de contratación**: depende de la política de contratación, no de la herramienta. El TO-BE solo acorta la curva de aprendizaje (checklist guiado y bitácora).

## Datos que se necesitan para calibrarlo

Por expediente y etapa, de al menos 6 meses: fecha de entrada y salida, renta, tipo de solicitud, responsable, devoluciones internas, fecha de notificación, ejecutoria, orden de pago y pago; además, número de personas por rol, días de caída de Mercurio, NAS y SAP, y fechas reales de inicio de contratos.
