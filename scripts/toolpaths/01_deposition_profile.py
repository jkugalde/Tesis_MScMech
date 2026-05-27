# =============================================================================
# 01_deposition_profile.py -- Caracterizacion de perfil de deposicion
# =============================================================================
# Genera n lineas paralelas en Y, separadas por h mm en el eje Y,
# variando linealmente un parametro de proceso entre cada linea.
#
# Parametros a variar (elegir uno por sesion):
#   - Velocidad de travesia (feed)       [mm/min]
#   - Distancia de standoff              [mm]
#   - Angulo de deposicion A             [grados, sin compensacion oblicua]
#     -> Z se corrige automaticamente para mantener standoff real constante
#
# Uso:
#   Ajustar la seccion PARAMETROS DE SESION segun el experimento del dia,
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
# PARAMETROS DE SESION -- editar antes de cada experimento
# =============================================================================

# --- Tobera activa ---
NOZZLE_ID = NOZZLE_DEFAULT   # "nozzle_A" o "nozzle_B"

# --- Parametro a variar ---
# Elegir UNO: "feed", "standoff", "angle"
VARIABLE = "feed"

# Rango y numero de lineas
N_LINES   = 5          # numero de lineas (= numero de valores del parametro)
VAR_MIN   = 100.0      # valor minimo del parametro
VAR_MAX   = 500.0      # valor maximo del parametro

# --- Parametros fijos durante esta sesion ---
LINE_LENGTH_MM  = 60.0          # longitud de cada linea (mm)
LINE_SPACING_MM = 8.0           # separacion entre lineas en Y (mm)
STANDOFF_MM     = STANDOFF_NOMINAL_MM   # standoff fijo (si VARIABLE != "standoff")
FEED_MM_MIN     = FEED_DEFAULT          # feed fijo (si VARIABLE != "feed")
A_DEG           = A_NEUTRAL             # angulo A fijo (si VARIABLE != "angle")

# --- Posicion de inicio del bloque de lineas ---
# Primera linea centrada en X, bloque centrado en Y
X_START_MM = -LINE_LENGTH_MM / 2.0
X_END_MM   =  LINE_LENGTH_MM / 2.0

# Y de la primera linea; las siguientes se desplazan +LINE_SPACING_MM
Y_FIRST_MM = 0.0

# =============================================================================
# GENERACION DE G-CODE
# =============================================================================

def z_corrected(standoff, a_deg):
    """
    Corrige Z para mantener standoff real constante cuando A != 90deg.
    La componente vertical del standoff es standoff * sin(A).
    """
    return standoff * math.sin(math.radians(a_deg))


def main():
    # Generar los n valores del parametro variable (espaciado lineal)
    values = np.linspace(VAR_MIN, VAR_MAX, N_LINES)

    # Nombre de archivo descriptivo
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', 'output')
    fname = os.path.join(output_dir,
                         f"01_profile_{VARIABLE}_n{N_LINES}.gcode")

    g = GCodeWriter(fname, nozzle_id=NOZZLE_ID, feedrate=FEED_MM_MIN)

    # Cabecera
    g.header(
        f"Caracterizacion de perfil - variable: {VARIABLE} "
        f"[{VAR_MIN} -> {VAR_MAX}], n={N_LINES}"
    )
    g.blank()

    # Posicion inicial segura
    g.rapid_move(z=Z_SAFE_MM)
    g.rapid_move(x=X_START_MM, y=Y_FIRST_MM)
    g.blank()

    for i, val in enumerate(values):
        y = Y_FIRST_MM + i * LINE_SPACING_MM

        # Resolver parametros de esta linea
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

        # Z corregido segun angulo A activo
        z_work = z_corrected(standoff_i, a_i)

        g.comment(
            f"Linea {i+1}/{N_LINES} -- {VARIABLE}={val:.2f}"
            + (f" mm/min" if VARIABLE == "feed" else
               f" mm"     if VARIABLE == "standoff" else
               f"deg")
            + f" | Y={y:.2f} mm | Z={z_work:.3f} mm | A={a_i:.1f}deg"
        )

        # Reposicionamiento
        g.rapid_move(z=Z_SAFE_MM)
        g.rapid_move(x=X_START_MM, y=y)
        g.rapid_move(z=z_work, a=a_i)

        # Pasada de deposicion
        g.linear_move(x=X_END_MM, y=y, feed=feed_i)

        g.blank()

    g.footer()
    g.write()
    print(f"Parametro variado: {VARIABLE}")
    print(f"Valores: {[f'{v:.2f}' for v in values]}")


if __name__ == "__main__":
    main()
