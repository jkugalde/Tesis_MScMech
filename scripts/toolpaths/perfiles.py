# =============================================================================
# 01_deposition_profile.py — Caracterización de perfil de deposición
# =============================================================================
# Genera n líneas paralelas en Y, separadas por h mm en el eje Y,
# variando linealmente un parámetro de proceso entre cada línea.
#
# Parámetros a variar (elegir uno por sesión):
#   - Velocidad de travesía (feed)       [mm/min]
#   - Distancia de standoff              [mm]
#   - Ángulo de deposición A             [grados, sin compensación oblicua]
#     → Z se corrige automáticamente para mantener standoff real constante
#
# Uso:
#   Ajustar la sección PARÁMETROS DE SESIÓN según el experimento del día,
#   luego ejecutar: python 01_deposition_profile.py
# =============================================================================

import math
import numpy as np
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gcode_core import GCodeWriter
from config import (
    A_NEUTRAL, STANDOFF_NOMINAL_MM, FEED_DEFAULT,
    NOZZLE_DEFAULT, Z_SAFE_MM,
)

# =============================================================================
# PARÁMETROS DE SESIÓN — editar antes de cada experimento
# =============================================================================

# --- Tobera activa ---
NOZZLE_ID = NOZZLE_DEFAULT   # "nozzle_A" o "nozzle_B"

# --- Parámetro a variar ---
# Elegir UNO: "feed", "standoff", "angle"
VARIABLE = "feed"

# Rango y número de líneas
N_LINES   = 5          # número de líneas (= número de valores del parámetro)
VAR_MIN   = 100.0      # valor mínimo del parámetro
VAR_MAX   = 500.0      # valor máximo del parámetro

# --- Parámetros fijos durante esta sesión ---
LINE_LENGTH_MM  = 60.0          # longitud de cada línea (mm)
LINE_SPACING_MM = 8.0           # separación entre líneas en Y (mm)
STANDOFF_MM     = STANDOFF_NOMINAL_MM   # standoff fijo (si VARIABLE != "standoff")
FEED_MM_MIN     = FEED_DEFAULT          # feed fijo (si VARIABLE != "feed")
A_DEG           = A_NEUTRAL             # ángulo A fijo (si VARIABLE != "angle")

# --- Posición de inicio del bloque de líneas ---
# Primera línea centrada en X, bloque centrado en Y
X_START_MM = -LINE_LENGTH_MM / 2.0
X_END_MM   =  LINE_LENGTH_MM / 2.0

# Y de la primera línea; las siguientes se desplazan +LINE_SPACING_MM
Y_FIRST_MM = 0.0

# =============================================================================
# GENERACIÓN DE G-CODE
# =============================================================================

def z_corrected(standoff, a_deg):
    """
    Corrige Z para mantener standoff real constante cuando A ≠ 90°.
    La componente vertical del standoff es standoff * sin(A).
    """
    return standoff * math.sin(math.radians(a_deg))


def main():
    # Generar los n valores del parámetro variable (espaciado lineal)
    values = np.linspace(VAR_MIN, VAR_MAX, N_LINES)

    # Nombre de archivo descriptivo
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', 'output')
    fname = os.path.join(output_dir,
                         f"01_profile_{VARIABLE}_n{N_LINES}.gcode")

    g = GCodeWriter(fname, nozzle_id=NOZZLE_ID, feedrate=FEED_MM_MIN)

    # Cabecera
    g.header(
        f"Caracterización de perfil — variable: {VARIABLE} "
        f"[{VAR_MIN} → {VAR_MAX}], n={N_LINES}"
    )
    g.blank()

    # Posición inicial segura
    g.rapid_move(z=Z_SAFE_MM)
    g.rapid_move(x=X_START_MM, y=Y_FIRST_MM)
    g.blank()

    for i, val in enumerate(values):
        y = Y_FIRST_MM + i * LINE_SPACING_MM

        # Resolver parámetros de esta línea
        if VARIABLE == "feed":
            feed_i     = val
            standoff_i = STANDOFF_MM
            a_i        = A_DEG
        elif VARIABLE == "standoff":
            feed_i     = FEED_MM_MIN
            standoff_i = val
            a_i        = A_DEG
        elif VARIABLE == "angle":
            feed_i     = FEED_MM_MIN
            standoff_i = STANDOFF_MM
            a_i        = val
        else:
            raise ValueError(f"VARIABLE='{VARIABLE}' no reconocida. "
                             f"Usar 'feed', 'standoff' o 'angle'.")

        # Z corregido según ángulo A activo
        z_work = z_corrected(standoff_i, a_i)

        g.comment(
            f"Línea {i+1}/{N_LINES} — {VARIABLE}={val:.2f}"
            + (f" mm/min" if VARIABLE == "feed" else
               f" mm"     if VARIABLE == "standoff" else
               f"°")
            + f" | Y={y:.2f} mm | Z={z_work:.3f} mm | A={a_i:.1f}°"
        )

        # Reposicionamiento
        g.rapid_move(z=Z_SAFE_MM)
        g.rapid_move(x=X_START_MM, y=y)
        g.rapid_move(z=z_work, a=a_i)

        # Pasada de deposición
        g.linear_move(x=X_END_MM, y=y, feed=feed_i)

        g.blank()

    g.footer()
    g.write()
    print(f"Parámetro variado: {VARIABLE}")
    print(f"Valores: {[f'{v:.2f}' for v in values]}")


if __name__ == "__main__":
    main()