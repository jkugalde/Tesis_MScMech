"""
generar_datos_sinteticos.py
===========================
Genera un mapa de altura 3D sintético que simula la salida CSV del
Keyence VR-6100 para un cordón de deposición Cold Spray.

El perfil transversal sigue una distribución Super-Gaussiana (n=1 → Gaussiana).
En la dirección de construcción (Y) se añaden:
  - Variación lenta de altura (ondulación longitudinal)
  - Ruido gaussiano blanco
  - Outliers aleatorios (errores de medición)
  - Celdas NaN (zonas sin medición / sombras ópticas)

Uso:
    python generar_datos_sinteticos.py

Los parámetros se configuran en la sección PARÁMETROS.
Genera:
    mapa_altura.csv   — archivo listo para usar con perfil_deposicion.py
    preview_mapa.png  — vista previa del mapa 3D y el perfil medio

Autor: generado con asistencia de Claude
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

# =============================================================================
# PARÁMETROS CONFIGURABLES
# =============================================================================

# --- Grilla ---
X_MIN, X_MAX   = -400.0, 400.0   # µm  — ancho del campo de medición
Y_MIN, Y_MAX   =     0.0, 10000.0   # µm  — largo del cordón medido
DX             =     5.0            # µm  — resolución lateral X
DY             =     5.0            # µm  — resolución lateral Y

# --- Geometría del cordón (perfil transversal Super-Gaussiano) ---
H_PEAK         =  100.0            # µm  — altura de pico
X_CENTER       =    0.0            # µm  — posición central del cordón en X
SIGMA          =  200.0            # µm  — anchura característica (~ W/2.4 para n=1)
N_ORDER        =    1.2            # —    orden super-gaussiano (1 = Gaussiana pura)

# --- Variación longitudinal (ondulación lenta en Y) ---
# La altura varía sinusoidalmente a lo largo del cordón
LONG_AMP       =    5.0            # µm  — amplitud de la ondulación
LONG_PERIOD    = 4000.0            # µm  — periodo de la ondulación

# --- Ruido y artefactos ---
NOISE_STD      =    1.5            # µm  — ruido gaussiano blanco (σ)
OUTLIER_FRAC   =    0.005          # —    fracción de celdas con outlier (0.5%)
OUTLIER_MAG    =   50.0            # µm  — magnitud media de los outliers
NAN_FRAC       =    0.008          # —    fracción de celdas NaN (sombras/errores)

# --- Sustrato ---
SUBSTRATE_Z    =    0.0            # µm  — nivel del sustrato
SUBSTRATE_TILT =    0.002          # —    inclinación leve del sustrato (µm/µm)

# --- Semilla aleatoria ---
RANDOM_SEED    =   42

# --- Salida ---
OUTPUT_CSV     = "mapa_altura.csv"
OUTPUT_PNG     = "preview_mapa.png"

# =============================================================================
# GENERACIÓN
# =============================================================================

def super_gaussiana_2d(X, Y, H, x0, sigma, n, amp_long, period_long, y_arr):
    """
    Mapa 3D: perfil transversal super-gaussiano modulado longitudinalmente.
    """
    # Ondulación lenta en Y (variación de altura pico)
    modulation = amp_long * np.sin(2 * np.pi * Y / period_long)

    # Perfil transversal
    Z = (H + modulation) * np.exp(-((np.abs(X - x0) / sigma) ** (2 * n)))
    return Z


def generar_mapa():
    rng = np.random.default_rng(RANDOM_SEED)

    # Grillas
    x_arr = np.arange(X_MIN, X_MAX + DX, DX)
    y_arr = np.arange(Y_MIN, Y_MAX + DY, DY)
    Nx, Ny = len(x_arr), len(y_arr)

    X, Y = np.meshgrid(x_arr, y_arr)   # shape: (Ny, Nx)

    print(f"  Grilla: {Ny} filas (Y) × {Nx} columnas (X)")
    print(f"  Rango X: [{X_MIN}, {X_MAX}] µm  |  ΔX = {DX} µm")
    print(f"  Rango Y: [{Y_MIN}, {Y_MAX}] µm  |  ΔY = {DY} µm")

    # --- Señal base ---
    Z = super_gaussiana_2d(X, Y, H_PEAK, X_CENTER, SIGMA, N_ORDER,
                           LONG_AMP, LONG_PERIOD, y_arr)

    # --- Sustrato con inclinación leve ---
    Z += SUBSTRATE_Z + SUBSTRATE_TILT * X

    # --- Ruido gaussiano blanco ---
    Z += rng.normal(0.0, NOISE_STD, size=Z.shape)

    # --- Outliers ---
    n_outliers = int(OUTLIER_FRAC * Ny * Nx)
    idx_r = rng.integers(0, Ny, n_outliers)
    idx_c = rng.integers(0, Nx, n_outliers)
    signo = rng.choice([-1, 1], n_outliers)
    magnitud = rng.exponential(OUTLIER_MAG, n_outliers)
    Z[idx_r, idx_c] += signo * magnitud
    print(f"  Outliers insertados: {n_outliers}")

    # --- Celdas NaN (zonas sin medición) ---
    n_nan = int(NAN_FRAC * Ny * Nx)
    idx_r_nan = rng.integers(0, Ny, n_nan)
    idx_c_nan = rng.integers(0, Nx, n_nan)
    Z[idx_r_nan, idx_c_nan] = np.nan
    print(f"  Celdas NaN insertadas: {n_nan}")

    return x_arr, y_arr, Z


# =============================================================================
# EXPORTAR CSV
# =============================================================================

def exportar_csv(x_arr, y_arr, Z, path):
    """
    Exporta la matriz en el mismo formato que el VR Analyzer:
    - Primera fila  = coordenadas X (header)
    - Primera columna = coordenadas Y (index)
    - Valores en µm, NaN → celda vacía
    """
    import pandas as pd
    df = pd.DataFrame(Z, index=y_arr, columns=x_arr)
    df.index.name   = "Y\\X"
    df.to_csv(path, float_format="%.4f", na_rep="")
    print(f"  CSV guardado en: {path}  ({Z.shape[0]}×{Z.shape[1]} celdas)")


# =============================================================================
# PREVIEW
# =============================================================================

def graficar_preview(x_arr, y_arr, Z, path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=130)

    # --- Mapa de altura ---
    ax = axes[0]
    vmin = np.nanpercentile(Z, 1)
    vmax = np.nanpercentile(Z, 99)
    im = ax.imshow(Z, aspect="auto", origin="lower",
                   extent=[x_arr[0], x_arr[-1], y_arr[0], y_arr[-1]],
                   cmap="inferno", vmin=vmin, vmax=vmax)
    plt.colorbar(im, ax=ax, label="Z [µm]", shrink=0.85)
    ax.set_xlabel("Posición transversal X [µm]", fontsize=10)
    ax.set_ylabel("Dirección de construcción Y [µm]", fontsize=10)
    ax.set_title("Mapa de altura sintético (VR-6100)", fontsize=11)

    # --- Perfil promedio con banda ±σ ---
    ax2 = axes[1]
    z_mean = np.nanmean(Z, axis=0)
    z_std  = np.nanstd(Z, axis=0)

    ax2.fill_between(x_arr, z_mean - z_std, z_mean + z_std,
                     alpha=0.3, color="#5B8DB8", label=r"$\bar{Z} \pm \sigma$")
    ax2.plot(x_arr, z_mean, color="#1A3D5C", lw=1.8, label="Perfil promedio")
    ax2.axhline(SUBSTRATE_Z, color="gray", lw=0.8, ls=":", label="Sustrato")

    ax2.set_xlabel("Posición transversal X [µm]", fontsize=10)
    ax2.set_ylabel("Altura Z [µm]", fontsize=10)
    ax2.set_title("Perfil promediado (dirección Y)", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax2.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax2.grid(True, which="major", ls="--", alpha=0.4)
    ax2.grid(True, which="minor", ls=":", alpha=0.2)

    # Parámetros usados
    param_text = (
        f"H = {H_PEAK} µm\n"
        f"σ = {SIGMA} µm\n"
        f"n = {N_ORDER}\n"
        f"Ruido σ = {NOISE_STD} µm\n"
        f"Outliers = {OUTLIER_FRAC*100:.1f}%\n"
        f"NaN = {NAN_FRAC*100:.1f}%"
    )
    ax2.text(0.97, 0.97, param_text, transform=ax2.transAxes,
             fontsize=8, va="top", ha="right",
             bbox=dict(boxstyle="round,pad=0.4", fc="white", alpha=0.8))

    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    print(f"  Preview guardado en: {path}")
    plt.show()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 52)
    print("  GENERADOR DE DATOS SINTÉTICOS — VR-6100 / CS")
    print("=" * 52)
    print("\nParámetros del cordón:")
    print(f"  H_PEAK   = {H_PEAK} µm")
    print(f"  SIGMA    = {SIGMA} µm")
    print(f"  N_ORDER  = {N_ORDER}  (1 = Gaussiana pura)")
    print(f"  FWHM_teo = {2*(2*np.log(2))**(1/(2*N_ORDER))*SIGMA:.1f} µm  (aprox.)")
    print()

    print("Generando mapa 3D...")
    x_arr, y_arr, Z = generar_mapa()

    print("\nExportando CSV...")
    exportar_csv(x_arr, y_arr, Z, OUTPUT_CSV)

    print("\nGenerando preview...")
    graficar_preview(x_arr, y_arr, Z, OUTPUT_PNG)

    print("\nListo. Puedes procesar el archivo con:")
    print(f"  python perfil_deposicion.py   (asegúrate que CSV_PATH = '{OUTPUT_CSV}')")
    print()