"""Motor de términos: días hábiles con festivos de Colombia.

En el demo de Envigado el tablero contaba días calendario. Los términos de
devoluciones son en días hábiles (art. 855 E.T.: 50 días hábiles), así que
aquí se cuentan de lunes a viernes, sin festivos nacionales. Los festivos
se calculan con la Ley 51 de 1983 (Ley Emiliani, que traslada algunos al
lunes siguiente) y con la Pascua, para cualquier año.

No incluye suspensiones de términos (vacancia judicial, decretos de
suspensión por fallas de sistemas, etc.). Deben agregarse a
SUSPENSIONES cuando la Subsecretaría las decrete.
"""

import datetime as dt
from functools import lru_cache
from typing import Set

# Días sueltos de suspensión de términos decretados por la entidad.
SUSPENSIONES: Set[dt.date] = set()

# Término en días hábiles por tipo de trámite (validar con Jurídica frente
# al Acuerdo 093 de 2023).
TERMINO_HABILES = {
    'devolucion': 50, 'compensacion': 50, 'con_cartera': 50,
    'incompleta': 50, 'recurso': 50, 'rechazo': 15,
}


def _pascua(anio: int) -> dt.date:
    """Domingo de Pascua (algoritmo anónimo gregoriano)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(anio, mes, dia)


def _al_lunes(fecha: dt.date) -> dt.date:
    return fecha + dt.timedelta(days=(7 - fecha.weekday()) % 7)


@lru_cache(maxsize=None)
def festivos(anio: int) -> frozenset:
    fijos = [dt.date(anio, 1, 1), dt.date(anio, 5, 1), dt.date(anio, 7, 20),
             dt.date(anio, 8, 7), dt.date(anio, 12, 8), dt.date(anio, 12, 25)]
    trasladables = [dt.date(anio, 1, 6), dt.date(anio, 3, 19), dt.date(anio, 6, 29),
                    dt.date(anio, 8, 15), dt.date(anio, 10, 12), dt.date(anio, 11, 1),
                    dt.date(anio, 11, 11)]
    pascua = _pascua(anio)
    semana_santa = [pascua - dt.timedelta(days=3), pascua - dt.timedelta(days=2)]
    moviles = [pascua + dt.timedelta(days=n) for n in (39, 60, 68)]  # Ascensión, Corpus, Sagrado Corazón
    return frozenset(fijos + semana_santa + [_al_lunes(f) for f in trasladables + moviles])


def es_habil(fecha: dt.date) -> bool:
    return fecha.weekday() < 5 and fecha not in festivos(fecha.year) and fecha not in SUSPENSIONES


def sumar_habiles(inicio: dt.date, n: int) -> dt.date:
    """Fecha en que vence un término de n días hábiles contados desde el día
    hábil siguiente a `inicio`."""
    fecha, contados = inicio, 0
    while contados < n:
        fecha += dt.timedelta(days=1)
        if es_habil(fecha):
            contados += 1
    return fecha


def habiles_entre(desde: dt.date, hasta: dt.date) -> int:
    """Días hábiles transcurridos después de `desde` y hasta `hasta` inclusive.
    Negativo si `hasta` es anterior."""
    if hasta < desde:
        return -habiles_entre(hasta, desde)
    n, fecha = 0, desde
    while fecha < hasta:
        fecha += dt.timedelta(days=1)
        if es_habil(fecha):
            n += 1
    return n
