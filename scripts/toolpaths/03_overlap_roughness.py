# =============================================================================
# 03_overlap_roughness.py -- Experimento de solapamiento y rugosidad
# =============================================================================
# Traza un cuadrado de lado a = n_lines * hatch_mm mediante hatching
# paralelo bidireccional (boustrophedon), centrado en el origen de la mesa.
#
# Opcionalmente ejecuta una pasada de compensacion de ondulacion entre cada
# par de lineas principales, a la mitad del espacio de hatching, con sus
# propios parametros operativos. Esta pasada intermedia tiene n_lines-1 lineas.
#
# Uso:
#   Ajustar la seccion PARAMETROS DE SESION y ejecutar:
#   python 03_overlap_roughness.py
# =============================================================================

import math
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
NOZZLE_ID = NOZZLE_DEFAULT      # "nozzle_A" o "nozzle_B"

# --- Geometria del raster ---
N_LINES    = 6                  # numero de lineas del raster principal
HATCH_MM   = 3.0                # distancia de hatching entre lineas (mm)
                                # lado del cuadrado = N_LINES * HATCH_MM

# --- Parametros operativos -- lineas principales ---
FEED_MAIN       = FEED_DEFAULT          # velocidad de travesia (mm/min)
STANDOFF_MAIN   = STANDOFF_NOMINAL_MM   # standoff (mm)
A_MAIN          = A_NEUTRAL             # angulo A (deg)

# --- Compensacion de ondulacion ---
# Si True, traza una linea intermedia entre cada par de lineas principales,
# ubicada exactamente a HATCH_MM/2 del par, con sus propios parametros.
WAVE_COMPENSATION = False

FEED_WAVE       = FEED_DEFAULT          # velocidad pasadas intermedias (mm/min)
STANDOFF_WAVE   = STANDOFF_NOMINAL_MM   # standoff pasadas intermedias (mm)
A_WAVE          = A_NEUTRAL             # angulo A pasadas intermedias (deg)

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def z_corrected(standoff, a_deg):
    """
    Corrige Z para mantener standoff real constante cuando A != 90 deg.
    Componente vertical del standoff: standoff * sin(A).
    """
    return standoff * math.sin(math.radians(a_deg))


# =============================================================================
# GENERACION DE G-CODE
# =============================================================================

def main():
    # Geometria derivada
    side_mm   = N_LINES * HATCH_MM          # lado real del cuadrado (mm)
    half_side = side_mm / 2.0

    # Coordenadas de las lineas principales en Y
    # Primera linea en y = -half_side, ultima en y = +half_side - HATCH_MM
    # (N_LINES lineas separadas por HATCH_MM, bloque centrado en Y=0)
    y_main = [-half_side + i * HATCH_MM for i in range(N_LINES)]

    # Coordenadas de las lineas de compensacion (entre cada par, a la mitad)
    y_wave = [y_main[i] + HATCH_MM / 2.0 for i in range(N_LINES - 1)]

    # Extremos X centrados en el origen
    x_left  = -half_side
    x_right =  half_side

    # Nombre de archivo descriptivo
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', 'output')
    wave_tag = "_wave" if WAVE_COMPENSATION else ""
    fname = os.path.join(output_dir,
                         f"03_overlap_n{N_LINES}_h{HATCH_MM:.1f}mm{wave_tag}.gcode")

    g = GCodeWriter(fname, nozzle_id=NOZZLE_ID, feedrate=FEED_MAIN)

    # --- Cabecera ---
    g.header(
        f"Solapamiento -- n={N_LINES} lineas, h={HATCH_MM} mm, "
        f"lado={side_mm:.1f} mm, wave={WAVE_COMPENSATION}"
    )
    g.blank()
    g.comment(f"Parametros principales: feed={FEED_MAIN} mm/min, "
              f"standoff={STANDOFF_MAIN} mm, A={A_MAIN} deg")
    if WAVE_COMPENSATION:
        g.comment(f"Parametros wave: feed={FEED_WAVE} mm/min, "
                  f"standoff={STANDOFF_WAVE} mm, A={A_WAVE} deg")
    g.blank()

    # --- Raster principal: hatching bidireccional ---
    g.comment("=== Raster principal ===")
    z_main = z_corrected(STANDOFF_MAIN, A_MAIN)

    for i, y in enumerate(y_main):
        # Direccion alternada: izquierda->derecha (par) / derecha->izquierda (impar)
        if i % 2 == 0:
            x_start, x_end = x_left, x_right
            direction = "L->R"
        else:
            x_start, x_end = x_right, x_left
            direction = "R->L"

        g.comment(f"Linea principal {i+1}/{N_LINES} | Y={y:.3f} mm | {direction}")
        if i == 0:
            # Solo en la primera linea: bajar desde Z seguro
            g.rapid_move(z=Z_SAFE_MM)
            g.rapid_move(x=x_start, y=y)
            g.rapid_move(z=z_main, a=A_MAIN)
        else:
            # Entre lineas: reposicionar en XY directamente a la misma altura
            g.rapid_move(x=x_start, y=y)
        g.linear_move(x=x_end, y=y, feed=FEED_MAIN)
        g.blank()

        # --- Compensacion de ondulacion (entre linea i e i+1) ---
        if WAVE_COMPENSATION and i < N_LINES - 1:
            y_w = y_wave[i]
            z_wave_val = z_corrected(STANDOFF_WAVE, A_WAVE)

            # La linea de compensacion mantiene la misma direccion que
            # la linea principal que la precede
            if i % 2 == 0:
                xw_start, xw_end = x_left, x_right
                dir_w = "L->R"
            else:
                xw_start, xw_end = x_right, x_left
                dir_w = "R->L"

            g.comment(
                f"  Wave {i+1}/{N_LINES-1} | Y={y_w:.3f} mm "
                f"(+{HATCH_MM/2:.2f} mm) | {dir_w}"
            )
            # Si el standoff wave es distinto al principal, hay que ajustar Z
            if abs(z_wave_val - z_main) > 0.001 or abs(A_WAVE - A_MAIN) > 0.001:
                g.rapid_move(z=Z_SAFE_MM)
                g.rapid_move(x=xw_start, y=y_w)
                g.rapid_move(z=z_wave_val, a=A_WAVE)
            else:
                g.rapid_move(x=xw_start, y=y_w)
            g.linear_move(x=xw_end, y=y_w, feed=FEED_WAVE)
            g.blank()

    g.footer()
    g.write()

    # Resumen en consola
    print(f"Lado del cuadrado:     {side_mm:.1f} mm")
    print(f"Lineas principales:    {N_LINES}")
    print(f"Distancia hatching:    {HATCH_MM} mm")
    print(f"Compensacion wave:     {WAVE_COMPENSATION}")
    if WAVE_COMPENSATION:
        print(f"Lineas intermedias:    {N_LINES - 1}")
    print(f"Archivo generado:      {fname}")


if __name__ == "__main__":
    main()
