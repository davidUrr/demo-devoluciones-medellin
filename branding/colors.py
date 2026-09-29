"""Paleta PROVISIONAL para el demo de Medellín.

No tenemos el Manual de Identidad Visual vigente del Distrito de Medellín
(en Envigado se usó el manual oficial CP-M-002). Mientras llega, se usa una
paleta neutra y sobria, y NO se muestra logo ni escudo, para no presentar
como institucional algo que no lo es. Cuando se reciba el manual:
1. reemplazar estos valores por los hex oficiales,
2. poner el logo entregado por la Alcaldía en branding/assets/logo.png,
3. actualizar .streamlit/config.toml (primaryColor).
"""

PRIMARIO = '#1F5A96'       # azul institucional neutro (provisional)
FONDO_SUAVE = '#F2F4F7'
TEXTO = '#1B1F24'
GRIS = '#8A9199'

COLOR_ASIS = GRIS          # estado actual, sin connotación de marca
COLOR_TOBE = PRIMARIO      # hacia dónde apunta la propuesta

ENTIDAD = 'Distrito de Medellín'
DEPENDENCIA = 'Secretaría de Hacienda · Subsecretaría de Ingresos'
LOGO = None                # pendiente: logo oficial entregado por la Alcaldía
