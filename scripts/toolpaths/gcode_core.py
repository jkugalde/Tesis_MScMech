# =============================================================================
# gcode_core.py -- Clase GCodeWriter para generacion de G-code CSAM
# PocketNC V2 modificada -- 5 ejes simultaneos (X, Y, Z, A, B)
# =============================================================================

import math
import os
from config import (
    A_NEUTRAL, Z_SAFE_MM, A_SAFE_DEG,
    FEED_DEFAULT, FEED_MAX_LINEAR,
    DECIMAL_PLACES, NOZZLES, NOZZLE_DEFAULT,
)
from utils import (
    check_limits, check_feed, compute_z,
    oblique_angles_line, interpolate_circle_oblique,
    normalize_b,
)


class GCodeWriter:
    """
    Generador de G-code para experimentos CSAM en PocketNC 5 ejes.

    Acumula lineas en un buffer interno y vuelca al archivo con write().
    El sistema de coordenadas de trabajo se establece manualmente antes
    de cada experimento; esta clase asume origen ya referenciado.

    Parametros
    ----------
    filename    : str    Ruta del archivo de salida .gcode
    nozzle_id   : str    Clave de tobera en config.NOZZLES
    feedrate    : float  Velocidad de avance por defecto (mm/min)
    """

    def __init__(self, filename, nozzle_id=NOZZLE_DEFAULT, feedrate=FEED_DEFAULT):
        self.filename = filename
        self.nozzle_id = nozzle_id
        self.nozzle = NOZZLES[nozzle_id]
        self.nozzle_z_offset = self.nozzle["z_offset_mm"]
        self.feedrate = feedrate

        self._buffer = []

        # Estado interno de posicion (para validaciones y comentarios)
        self._x = 0.0
        self._y = 0.0
        self._z = Z_SAFE_MM
        self._a = A_NEUTRAL
        self._b = 0.0
        self._current_feed = feedrate

        # Acumulador de capas
        self._z_deposit = 0.0

    # =========================================================================
    # ESCRITURA A ARCHIVO
    # =========================================================================

    def write(self):
        """Vuelca el buffer completo al archivo de salida."""
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self._buffer))
            f.write('\n')
        print(f"G-code escrito: {self.filename} ({len(self._buffer)} lineas)")

    def _emit(self, line):
        """Anade una linea al buffer."""
        self._buffer.append(line)

    def _fmt(self, val):
        """Formatea un numero con la precision configurada."""
        return f"{val:.{DECIMAL_PLACES}f}"

    # =========================================================================
    # CABECERA Y PIE
    # =========================================================================

    def header(self, comment=""):
        """
        Emite cabecera estandar: unidades metricas, coordenadas absolutas,
        plano XY activo, y comentario descriptivo del experimento.
        """
        self._emit("%")
        self._emit(f"; =============================================================")
        self._emit(f"; Experimento CSAM -- PocketNC 5 ejes")
        if comment:
            self._emit(f"; {comment}")
        self._emit(f"; Tobera: {self.nozzle_id} -- {self.nozzle['description']}")
        self._emit(f"; Z-offset tobera: {self.nozzle_z_offset} mm")
        self._emit(f"; =============================================================")
        self._emit("G21")        # Unidades metricas
        self._emit("G90")        # Coordenadas absolutas
        self._emit("G17")        # Plano de trabajo XY activo

    def footer(self):
        """
        Emite pie estandar: retiro a posicion segura y fin de programa.
        """
        self._emit("; --- Fin de experimento ---")
        self.rapid_move(z=Z_SAFE_MM)            # Retirar herramienta a Z seguro primero
        self._emit(f"G0 A{self._fmt(0.0)}")     # A=0: mesa horizontal para retirar muestra
        self._a = 0.0
        self._emit("M2")                        # Fin de programa
        self._emit("%")

    def comment(self, text):
        """Inserta una linea de comentario en el G-code."""
        self._emit(f"; {text}")

    def blank(self):
        """Inserta una linea en blanco para legibilidad."""
        self._emit("")

    # =========================================================================
    # PRIMITIVAS ATOMICAS DE MOVIMIENTO
    # =========================================================================

    def rapid_move(self, x=None, y=None, z=None, a=None, b=None):
        """
        Movimiento rapido G0. Solo posicionamiento, sin deposicion.
        Acepta cualquier subconjunto de ejes.
        """
        parts = ["G0"]
        if x is not None:
            check_limits(x=x)
            parts.append(f"X{self._fmt(x)}")
            self._x = x
        if y is not None:
            check_limits(y=y)
            parts.append(f"Y{self._fmt(y)}")
            self._y = y
        if z is not None:
            check_limits(z=z)
            parts.append(f"Z{self._fmt(z)}")
            self._z = z
        if a is not None:
            check_limits(a=a)
            parts.append(f"A{self._fmt(a)}")
            self._a = a
        if b is not None:
            parts.append(f"B{self._fmt(b)}")
            self._b = b
        if len(parts) > 1:
            self._emit(" ".join(parts))

    def linear_move(self, x=None, y=None, z=None, a=None, b=None, feed=None):
        """
        Movimiento lineal G1 con deposicion. Soporta los 5 ejes simultaneos.
        Si feed=None usa el feedrate actual.
        """
        f = feed if feed is not None else self._current_feed
        check_feed(f)

        parts = ["G1"]
        if x is not None:
            check_limits(x=x)
            parts.append(f"X{self._fmt(x)}")
            self._x = x
        if y is not None:
            check_limits(y=y)
            parts.append(f"Y{self._fmt(y)}")
            self._y = y
        if z is not None:
            check_limits(z=z)
            parts.append(f"Z{self._fmt(z)}")
            self._z = z
        if a is not None:
            check_limits(a=a)
            parts.append(f"A{self._fmt(a)}")
            self._a = a
        if b is not None:
            parts.append(f"B{self._fmt(b)}")
            self._b = b

        parts.append(f"F{self._fmt(f)}")
        if len(parts) > 2:  # Al menos un eje ademas de G1 y F
            self._emit(" ".join(parts))
        self._current_feed = f

    def arc_move(self, x_end, y_end, i, j, clockwise=True, feed=None):
        """
        Movimiento de arco G2/G3 en plano XY con A=90deg fijo.
        Solo valido para pasadas principales (sin movimiento de ejes rotativos).

        Parametros
        ----------
        x_end, y_end : float   Punto final del arco (mm)
        i, j         : float   Offsets del centro del arco respecto al punto
                               actual (mm), en X e Y respectivamente
        clockwise    : bool    True = G2 (horario), False = G3 (antihorario)
        feed         : float   Feedrate (mm/min), None = usa el actual
        """
        f = feed if feed is not None else self._current_feed
        check_feed(f)
        check_limits(x=x_end, y=y_end)

        cmd = "G2" if clockwise else "G3"
        self._emit(
            f"{cmd} X{self._fmt(x_end)} Y{self._fmt(y_end)} "
            f"I{self._fmt(i)} J{self._fmt(j)} F{self._fmt(f)}"
        )
        self._x = x_end
        self._y = y_end
        self._current_feed = f

    def dwell(self, seconds):
        """Pausa G4 -- util para estabilizacion de gas antes de deposicion."""
        ms = int(seconds * 1000)
        self._emit(f"G4 P{ms}")

    # =========================================================================
    # PRIMITIVAS DE PASADA -- LINEA RECTA
    # =========================================================================

    def line_pass(self, x0, y0, x1, y1, standoff, feed=None, z_deposit=None):
        """
        Pasada lineal principal con A=90deg (normal a la tobera).

        Reposiciona en G0 al punto de inicio, ajusta Z y A, luego ejecuta
        el recorrido lineal con G1.

        Parametros
        ----------
        x0, y0   : float   Punto de inicio (mm)
        x1, y1   : float   Punto de fin (mm)
        standoff : float   Distancia tobera-sustrato (mm)
        feed     : float   Feedrate (mm/min), None = usa el por defecto
        z_deposit: float   Altura acumulada de deposito (mm), None = usa interno
        """
        f = feed if feed is not None else self.feedrate
        zd = z_deposit if z_deposit is not None else self._z_deposit
        z_work = compute_z(standoff, zd, self.nozzle_z_offset)

        # Reposicionamiento seguro
        self.rapid_move(z=Z_SAFE_MM)
        self.rapid_move(x=x0, y=y0)
        self.rapid_move(z=z_work, a=A_NEUTRAL)

        # Pasada de deposicion
        self.linear_move(x=x1, y=y1, feed=f)

    def line_pass_oblique(self, x0, y0, x1, y1, standoff, a_tilt_deg,
                          feed=None, z_deposit=None):
        """
        Pasada de compensacion oblicua sobre una linea recta.
        Ejecuta dos pasadas: pared izquierda y pared derecha del cordon.

        B se calcula automaticamente para orientar A perpendicular al avance.

        Parametros
        ----------
        x0, y0      : float   Punto de inicio (mm)
        x1, y1      : float   Punto de fin (mm)
        standoff    : float   Distancia tobera-superficie para las pasadas
                              oblicuas (mm)
        a_tilt_deg  : float   Desviacion de A respecto al neutro (grados)
        feed        : float   Feedrate (mm/min), None = usa el por defecto
        z_deposit   : float   Altura acumulada (mm), None = usa interno
        """
        f = feed if feed is not None else self.feedrate
        zd = z_deposit if z_deposit is not None else self._z_deposit
        z_work = compute_z(standoff, zd, self.nozzle_z_offset)

        for side in ('left', 'right'):
            a_deg, b_deg = oblique_angles_line(x0, y0, x1, y1, side, a_tilt_deg)
            b_norm = normalize_b(b_deg)

            self.comment(f"Compensacion oblicua -- {side}, A={a_deg:.1f}deg, B={b_norm:.1f}deg")
            self.rapid_move(z=Z_SAFE_MM)
            self.rapid_move(x=x0, y=y0, b=b_norm)
            self.rapid_move(z=z_work, a=a_deg)
            self.linear_move(x=x1, y=y1, feed=f)

    # =========================================================================
    # PRIMITIVAS DE PASADA -- CIRCULO
    # =========================================================================

    def circle_pass(self, cx, cy, radius, standoff, clockwise=True,
                    feed=None, z_deposit=None):
        """
        Pasada circular principal con A=90deg (normal a la tobera).
        Usa G2/G3 para el arco completo.

        El circulo se traza como dos semiarcos para compatibilidad con
        controladores que no cierran G2/G3 completos en una sola linea.

        Parametros
        ----------
        cx, cy   : float   Centro del circulo (mm)
        radius   : float   Radio (mm)
        standoff : float   Distancia tobera-sustrato (mm)
        clockwise: bool    True = G2, False = G3
        feed     : float   Feedrate (mm/min)
        z_deposit: float   Altura acumulada (mm)
        """
        f = feed if feed is not None else self.feedrate
        zd = z_deposit if z_deposit is not None else self._z_deposit
        z_work = compute_z(standoff, zd, self.nozzle_z_offset)

        # Punto de entrada: extremo derecho del circulo (theta=0)
        x_start = cx + radius
        y_start = cy
        x_mid   = cx - radius
        y_mid   = cy

        self.rapid_move(z=Z_SAFE_MM)
        self.rapid_move(x=x_start, y=y_start)
        self.rapid_move(z=z_work, a=A_NEUTRAL)

        # Primer semiarco: (cx+r, cy) -> (cx-r, cy)
        i_1 = cx - x_start   # offset al centro desde punto actual
        j_1 = cy - y_start
        self.arc_move(x_mid, y_mid, i_1, j_1, clockwise=clockwise, feed=f)

        # Segundo semiarco: (cx-r, cy) -> (cx+r, cy)
        i_2 = cx - x_mid
        j_2 = cy - y_mid
        self.arc_move(x_start, y_start, i_2, j_2, clockwise=clockwise, feed=f)

    def circle_pass_oblique(self, radius, standoff, a_tilt_deg,
                             feed=None, z_deposit=None, resolution_deg=1.0):
        """
        Pasada de compensacion oblicua sobre un circulo centrado en el origen.
        Genera movimientos G1 interpolados con X, Y, Z, A, B simultaneos.

        Ejecuta dos pasadas: pared interior y pared exterior.

        NOTA: Version actual solo valida para circulos centrados en el origen.
        Para circulos descentrados se requiere calculo geometrico adicional
        (implementacion futura).

        Parametros
        ----------
        radius         : float   Radio del circulo (mm)
        standoff       : float   Standoff para pasadas oblicuas (mm)
        a_tilt_deg     : float   Desviacion de A respecto al neutro (grados)
        feed           : float   Feedrate (mm/min)
        z_deposit      : float   Altura acumulada (mm)
        resolution_deg : float   Paso angular de interpolacion (grados)
        """
        f = feed if feed is not None else self.feedrate
        zd = z_deposit if z_deposit is not None else self._z_deposit

        for side in ('inner', 'outer'):
            self.comment(
                f"Compensacion oblicua circular -- {side}, "
                f"R={radius} mm, A_tilt={a_tilt_deg}deg, res={resolution_deg}deg"
            )

            points = interpolate_circle_oblique(
                radius=radius,
                side=side,
                a_tilt_deg=a_tilt_deg,
                standoff=standoff,
                z_deposit=zd,
                resolution_deg=resolution_deg,
            )

            # Ir al punto de inicio en modo seguro
            x0, y0, z0, a0, b0 = points[0]
            self.rapid_move(z=Z_SAFE_MM)
            self.rapid_move(x=x0, y=y0, b=normalize_b(b0))
            self.rapid_move(z=z0, a=a0)

            # Recorrer todos los puntos interpolados
            for (x, y, z, a, b) in points[1:]:
                self.linear_move(x=x, y=y, z=z, a=a, b=normalize_b(b), feed=f)

    # =========================================================================
    # GESTION DE CAPAS
    # =========================================================================

    def next_layer(self, dz=None):
        """
        Incrementa la altura acumulada de deposito en dz mm.
        Si dz=None usa Z_LAYER_INCREMENT_MM del config.
        """
        from config import Z_LAYER_INCREMENT_MM
        increment = dz if dz is not None else Z_LAYER_INCREMENT_MM
        self._z_deposit += increment
        self.comment(f"Capa siguiente -- z_deposit acumulado: {self._z_deposit:.3f} mm")

    def set_z_deposit(self, z_deposit):
        """Establece la altura acumulada de deposito directamente."""
        self._z_deposit = z_deposit
        self.comment(f"z_deposit establecido en: {self._z_deposit:.3f} mm")

    def get_z_deposit(self):
        """Retorna la altura acumulada de deposito actual."""
        return self._z_deposit
