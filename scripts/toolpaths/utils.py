# =============================================================================
# utils.py -- Funciones geometricas y de validacion para generacion de G-code
# =============================================================================

import math
from config import (
    X_MIN, X_MAX, Y_MIN, Y_MAX, Z_MIN, Z_MAX,
    A_MIN, A_MAX, A_MIN_HW, A_MAX_HW, A_NEUTRAL,
    B_MIN, B_MAX,
    FEED_MAX_LINEAR,
)


# -----------------------------------------------------------------------------
# VALIDACION DE LIMITES
# -----------------------------------------------------------------------------

def check_limits(x=None, y=None, z=None, a=None, b=None, hardware=False):
    """
    Verifica que las coordenadas dadas esten dentro de los limites de la maquina.
    Lanza ValueError con mensaje descriptivo si algun eje esta fuera de rango.
    Solo valida los ejes que se pasen explicitamente (None = no validar).

    hardware=False (default): usa limites operativos de A (deposicion, +/-20deg desde neutro)
    hardware=True:            usa limites fisicos de hardware de A (-25deg a 135deg),
                              necesario para movimientos de retiro (footer) donde A=0deg es valido
    """
    a_lo = A_MIN_HW if hardware else A_MIN
    a_hi = A_MAX_HW if hardware else A_MAX

    if x is not None and not (X_MIN <= x <= X_MAX):
        raise ValueError(f"X={x:.3f} fuera de rango [{X_MIN}, {X_MAX}] mm")
    if y is not None and not (Y_MIN <= y <= Y_MAX):
        raise ValueError(f"Y={y:.3f} fuera de rango [{Y_MIN}, {Y_MAX}] mm")
    if z is not None and not (Z_MIN <= z <= Z_MAX):
        raise ValueError(f"Z={z:.3f} fuera de rango [{Z_MIN}, {Z_MAX}] mm")
    if a is not None and not (a_lo <= a <= a_hi):
        raise ValueError(f"A={a:.3f} fuera de rango [{a_lo}, {a_hi}] deg")
    if b is not None and not (B_MIN <= b <= B_MAX):
        raise ValueError(f"B={b:.3f} fuera de rango [{B_MIN}, {B_MAX}] deg")


def check_feed(feed):
    """
    Verifica que la velocidad de avance no supere el limite de hardware.
    Lanza ValueError si se excede.
    """
    if feed <= 0:
        raise ValueError(f"Feedrate debe ser positivo, recibido: {feed}")
    if feed > FEED_MAX_LINEAR:
        raise ValueError(
            f"Feedrate={feed} mm/min supera el maximo de la maquina "
            f"({FEED_MAX_LINEAR} mm/min)"
        )


# -----------------------------------------------------------------------------
# GEOMETRIA OBLICUA -- LINEA RECTA
# -----------------------------------------------------------------------------

def oblique_angles_line(x0, y0, x1, y1, side, a_tilt_deg):
    """
    Calcula los angulos (A, B) para una pasada de compensacion oblicua
    sobre una linea recta definida por (x0,y0) -> (x1,y1).

    La inclinacion de A se aplica en el plano perpendicular a la direccion
    de avance. B se fija de modo que el eje de inclinacion quede alineado
    correctamente con dicha direccion.

    Parametros
    ----------
    x0, y0 : float   Punto de inicio de la linea (mm)
    x1, y1 : float   Punto de fin de la linea (mm)
    side   : str     'left' o 'right' visto en la direccion de avance
    a_tilt_deg : float   Desviacion de A respecto al neutro (90deg), en grados.
                         Valor positivo = inclinacion hacia la derecha del avance.

    Retorna
    -------
    a_deg : float    Angulo A de la maquina (grados)
    b_deg : float    Angulo B de la maquina (grados)
    """
    dx = x1 - x0
    dy = y1 - y0
    if math.hypot(dx, dy) < 1e-9:
        raise ValueError("Linea de longitud cero: no se puede calcular direccion.")

    # Heading de la linea en el plano XY (radianes, referencia: eje X positivo)
    heading_rad = math.atan2(dy, dx)

    # B orienta la mesa de modo que la inclinacion de A quede perpendicular
    # al avance. Para la PocketNC, B=0 cuando la mesa apunta en +Y,
    # por lo que B = heading - 90deg convierte heading a referencia de mesa.
    b_deg = math.degrees(heading_rad) - 90.0

    # A se desvia del neutro (90deg) hacia el lado indicado
    sign = 1.0 if side == 'right' else -1.0
    a_deg = A_NEUTRAL + sign * a_tilt_deg

    return a_deg, b_deg


# -----------------------------------------------------------------------------
# GEOMETRIA OBLICUA -- CIRCULO CENTRADO EN ORIGEN
# -----------------------------------------------------------------------------

def oblique_point_circle(theta_deg, radius, side, a_tilt_deg, standoff, z_deposit=0.0):
    """
    Calcula la posicion (X, Y, Z, A, B) para un punto de la pasada de
    compensacion oblicua sobre un circulo centrado en el origen de la mesa.

    Para un circulo centrado en el origen, B = theta (el eje de inclinacion
    siempre apunta radialmente), y A se inclina hacia dentro o hacia fuera.

    Parametros
    ----------
    theta_deg  : float   Angulo azimutal del punto en el circulo (grados)
    radius     : float   Radio del circulo (mm)
    side       : str     'inner' (pared interior) o 'outer' (pared exterior)
    a_tilt_deg : float   Desviacion de A respecto al neutro (90deg), en grados
    standoff   : float   Distancia tobera-superficie para esta pasada (mm)
    z_deposit  : float   Altura acumulada de deposito (mm), default 0

    Retorna
    -------
    x, y, z, a_deg, b_deg : float
    """
    theta_rad = math.radians(theta_deg)

    x = radius * math.cos(theta_rad)
    y = radius * math.sin(theta_rad)
    z = standoff + z_deposit

    # B apunta radialmente: la inclinacion de A queda en el plano radial
    b_deg = theta_deg

    # Inner: A se inclina hacia el centro (positivo desde neutro)
    # Outer: A se inclina alejandose del centro (negativo desde neutro)
    sign = 1.0 if side == 'inner' else -1.0
    a_deg = A_NEUTRAL + sign * a_tilt_deg

    return x, y, z, a_deg, b_deg


def interpolate_circle_oblique(radius, side, a_tilt_deg, standoff,
                                z_deposit=0.0, resolution_deg=1.0,
                                theta_start_deg=0.0, theta_end_deg=360.0):
    """
    Genera la lista de puntos (x, y, z, a, b) para una pasada de compensacion
    oblicua sobre un circulo centrado en el origen.

    Parametros
    ----------
    radius          : float   Radio del circulo (mm)
    side            : str     'inner' o 'outer'
    a_tilt_deg      : float   Desviacion de A respecto a neutro (grados)
    standoff        : float   Standoff para esta pasada (mm)
    z_deposit       : float   Altura acumulada de deposito (mm)
    resolution_deg  : float   Paso angular de interpolacion (grados), default 1deg
    theta_start_deg : float   Angulo de inicio (grados), default 0deg
    theta_end_deg   : float   Angulo de fin (grados), default 360deg

    Retorna
    -------
    list of tuples (x, y, z, a, b)
    """
    points = []
    theta = theta_start_deg
    # Determinar direccion de barrido
    if theta_end_deg >= theta_start_deg:
        step = abs(resolution_deg)
    else:
        step = -abs(resolution_deg)

    while (step > 0 and theta <= theta_end_deg) or \
          (step < 0 and theta >= theta_end_deg):
        pt = oblique_point_circle(theta, radius, side, a_tilt_deg,
                                  standoff, z_deposit)
        points.append(pt)
        theta += step

    # Asegurar que el punto final este incluido exactamente
    if points and abs(points[-1][4] - theta_end_deg) > 1e-6:
        pt = oblique_point_circle(theta_end_deg, radius, side, a_tilt_deg,
                                  standoff, z_deposit)
        points.append(pt)

    return points


# -----------------------------------------------------------------------------
# CALCULO DE Z DE TRABAJO
# -----------------------------------------------------------------------------

def compute_z(standoff, z_deposit=0.0, nozzle_z_offset=0.0):
    """
    Calcula la coordenada Z absoluta de trabajo.

    Z = nozzle_z_offset + standoff + z_deposit

    El sistema de coordenadas ya esta referenciado sobre el sustrato montado,
    por lo que el espesor del sustrato no entra en este calculo.

    Parametros
    ----------
    standoff        : float   Distancia tobera-superficie (mm)
    z_deposit       : float   Altura acumulada de deposito (mm), default 0
    nozzle_z_offset : float   Offset de la tobera activa (mm), default 0

    Retorna
    -------
    float : coordenada Z absoluta de trabajo (mm)
    """
    return nozzle_z_offset + standoff + z_deposit


# -----------------------------------------------------------------------------
# UTILIDADES GENERALES
# -----------------------------------------------------------------------------

def line_length(x0, y0, x1, y1):
    """Longitud euclidiana de un segmento en el plano XY."""
    return math.hypot(x1 - x0, y1 - y0)


def normalize_b(b_deg):
    """
    Normaliza un angulo B al rango (-180, 180] para minimizar recorrido
    rotacional desde cero. No impone limite de hardware (B es libre).
    """
    b = b_deg % 360.0
    if b > 180.0:
        b -= 360.0
    return b
