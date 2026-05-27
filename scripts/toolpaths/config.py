# =============================================================================
# config.py -- Parametros fijos de maquina para experimentos CSAM
# PocketNC V2 modificada -- 5 ejes (X, Y, Z, A, B)
# Sistema de coordenadas de trabajo: establecido manualmente antes de cada
# experimento. Origen en centro de mesa, Z=0 en contacto tobera-sustrato.
# =============================================================================

# -----------------------------------------------------------------------------
# LIMITES DE EJES -- coordenadas de trabajo (mm / grados)
# -----------------------------------------------------------------------------

# Ejes lineales (mm)
X_MIN, X_MAX =  -40.0,  40.0
Y_MIN, Y_MAX =  -40.0,  40.0
Z_MIN, Z_MAX =    0.0,  80.0   # Z positivo se aleja del sustrato

# Eje A -- inclinacion de mesa (grados)
# Neutro en A=90deg (mesa normal a la tobera)
# Rango operativo +/-20deg desde neutro (usado en validacion de deposicion)
# Rango fisico de hardware: -25deg a 135deg (cubre A=0 para retiro de muestra)
A_NEUTRAL        =  90.0
A_MIN,   A_MAX   =  70.0, 110.0    # limites operativos (deposicion)
A_MIN_HW, A_MAX_HW = -25.0, 135.0  # limites fisicos de hardware

# Eje B -- rotacion de mesa (grados)
# Rotacion continua sin limite de hardware; solo se registra referencia de home
B_HOME      =   0.0
B_MIN, B_MAX = -9999.0, 9999.0   # libre; validacion de colision por geometria

# -----------------------------------------------------------------------------
# VELOCIDADES MAXIMAS -- limites de hardware
# -----------------------------------------------------------------------------

FEED_MAX_LINEAR  = 1524.0   # mm/min -- ejes X, Y, Z
FEED_MAX_A       =  40.0    # grados/segundo
FEED_MAX_B       =  40.0    # grados/segundo

# -----------------------------------------------------------------------------
# TOBERAS DISPONIBLES
# Offset de herramienta: distancia adicional en Z desde el punto de referencia
# hasta la punta de la tobera. Se selecciona en cada script de experimento.
# -----------------------------------------------------------------------------

NOZZLES = {
    "nozzle_A": {
        "description": "Tobera convergente-divergente, garganta 1 mm, salida 6 mm",
        "z_offset_mm": 0.0,   # completar con medicion real antes de experimentos
    },
    "nozzle_B": {
        "description": "Tobera alternativa -- completar descripcion",
        "z_offset_mm": 0.0,   # completar con medicion real antes de experimentos
    },
}

# Tobera activa por defecto (sobreescribible en cada script)
NOZZLE_DEFAULT = "nozzle_A"

# -----------------------------------------------------------------------------
# PARAMETROS DE PROCESO -- referencia nominal
# Estos valores son puntos de partida; cada script declara los suyos propios.
# -----------------------------------------------------------------------------

# Standoff distance nominal (mm) -- distancia tobera-sustrato durante deposicion
# El Z de trabajo en cualquier instante es:
#   Z = nozzle_z_offset + standoff + z_deposit_accumulated
STANDOFF_NOMINAL_MM = 20.0

# Espesor del sustrato (mm) -- se mide y actualiza antes de cada sesion
# Afecta el Z absoluto de inicio pero NO se suma en el calculo de Z de trabajo
# porque el sistema de coordenadas ya se referencia sobre el sustrato montado
SUBSTRATE_THICKNESS_MM = 0.0   # actualizar antes de cada experimento

# Incremento nominal de capa (mm) -- para experimentos multicapa
# Basado en ajuste gaussiano del perfil medido; actualizar tras caracterizacion
Z_LAYER_INCREMENT_MM = 0.1     # valor provisional hasta caracterizacion

# Velocidad de travesia por defecto (mm/min)
FEED_DEFAULT = 200.0

# -----------------------------------------------------------------------------
# POSICION DE SEGURIDAD -- retiro rapido entre pasadas o al detener
# -----------------------------------------------------------------------------

Z_SAFE_MM   = 40.0    # Z de retiro seguro entre movimientos
A_SAFE_DEG  =  0.0    # A de retiro final: mesa horizontal para retirar muestra

# -----------------------------------------------------------------------------
# PRECISION Y FORMATO DE SALIDA
# -----------------------------------------------------------------------------

DECIMAL_PLACES = 3    # cifras decimales en coordenadas del G-code generado
