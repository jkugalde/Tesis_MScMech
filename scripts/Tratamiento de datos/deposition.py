"""
perfil_deposicion.py
====================
Caracterización geométrica del perfil de deposición Cold Spray
a partir del mapa de altura 3D exportado por el Keyence VR-6100.

Parámetros extraídos:
    H     — Altura de pico [µm]
    FWHM  — Ancho a media altura [µm]
    W     — Ancho a umbral configurable (default 10% de H) [µm]
    R²    — Bondad del ajuste

Ajuste primario:  Gaussiano
Ajuste fallback:  Super-Gaussiano (Vanerio 2021) si R² < R2_THRESHOLD

Autor: generado con asistencia de Claude
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.optimize import curve_fit
from scipy.stats import median_abs_deviation
from pathlib import Path

# =============================================================================
# PARÁMETROS CONFIGURABLES
# =============================================================================

CSV_PATH        = "mapa_altura.csv"   # Ruta al archivo CSV exportado
OUTPUT_DIR      = "resultados"        # Carpeta de salida para figuras y reportes

# Prefiltrado MAD
MAD_K           = 3.5    # Umbral: |Z - mediana| > MAD_K * MAD → inválido
MIN_VALID_FRAC  = 0.5    # Fracción mínima de puntos válidos por columna

# Ajuste
R2_THRESHOLD    = 0.98   # Si R² Gaussiano < umbral → intentar super-Gaussiano
BASE_THRESHOLD  = 0.10   # Fracción de H para definir ancho de base W (10%)

# Figura
FIGSIZE         = (10, 5)
DPI             = 150

# =============================================================================
# FUNCIONES DE AJUSTE
# =============================================================================

def gaussiana(x, H, x0, sigma):
    """Gaussiana estándar centrada en x0."""
    return H * np.exp(-((x - x0) ** 2) / (2 * sigma ** 2))


def super_gaussiana(x, H, x0, sigma, n):
    """
    Super-Gaussiana generalizada (Vanerio 2021).
    n=1 → Gaussiana; n>1 → perfil más flat-top.
    """
    return H * np.exp(-((np.abs(x - x0) / sigma) ** (2 * n)))


def r_squared(y_data, y_fit):
    """Coeficiente de determinación R²."""
    ss_res = np.sum((y_data - y_fit) ** 2)
    ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)
    return 1.0 - ss_res / ss_tot


def fwhm_from_sigma(sigma):
    """FWHM = 2 * sqrt(2 * ln2) * sigma."""
    return 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma


def ancho_a_umbral(x, y_fit, H, umbral_frac=0.10):
    """
    Ancho W donde la curva ajustada cruza umbral_frac * H.
    Busca los dos cruces más externos.
    """
    nivel = umbral_frac * H
    cruces = np.where(np.diff(np.sign(y_fit - nivel)))[0]
    if len(cruces) < 2:
        return np.nan
    # Interpolación lineal en cada cruce
    def interp_cruce(i):
        x0, x1 = x[i], x[i + 1]
        y0, y1 = y_fit[i], y_fit[i + 1]
        return x0 + (nivel - y0) * (x1 - x0) / (y1 - y0)

    x_izq = interp_cruce(cruces[0])
    x_der = interp_cruce(cruces[-1])
    return x_der - x_izq


# =============================================================================
# CARGA Y PREFILTRADO
# =============================================================================

def cargar_matriz(csv_path):
    """
    Carga el CSV del VR-6100.
    Formato esperado: filas = Y (dirección de construcción),
                      columnas = X (dirección transversal).
    La primera fila puede contener las coordenadas X (header).
    La primera columna puede contener las coordenadas Y (index).
    Valores no numéricos y marcadores de error se convierten a NaN.
    """
    df = pd.read_csv(csv_path, header=0, index_col=0)

    # Intentar extraer coordenadas X e Y desde header/index
    try:
        x_coords = df.columns.astype(float).values
    except (ValueError, TypeError):
        x_coords = np.arange(df.shape[1], dtype=float)

    try:
        y_coords = df.index.astype(float).values
    except (ValueError, TypeError):
        y_coords = np.arange(df.shape[0], dtype=float)

    Z = df.values.astype(float)   # NaN donde no haya datos
    return x_coords, y_coords, Z


def prefiltrar_mad(Z, k=MAD_K):
    """
    Por cada columna (dirección X), marca como NaN los outliers
    usando la desviación absoluta mediana (MAD).
    Opera sobre una copia para no modificar Z original.
    """
    Z_filt = Z.copy()
    for j in range(Z.shape[1]):
        col = Z_filt[:, j]
        validos = col[~np.isnan(col)]
        if len(validos) < 3:
            continue
        med = np.median(validos)
        mad = median_abs_deviation(validos, nan_policy='omit')
        if mad == 0:
            continue
        outliers = np.abs(col - med) > k * mad
        Z_filt[outliers, j] = np.nan
    return Z_filt


# =============================================================================
# PROMEDIADO ESTADÍSTICO
# =============================================================================

def promediar_columnas(x_coords, Z_filt, min_valid_frac=MIN_VALID_FRAC):
    """
    Para cada columna X, calcula media y std ignorando NaN.
    Columnas con menos de min_valid_frac * N_filas puntos válidos
    se marcan como NaN (no representativas).
    Retorna x, Z_mean, Z_std, N_valid.
    """
    N_filas = Z_filt.shape[0]
    Z_mean = np.nanmean(Z_filt, axis=0)
    Z_std  = np.nanstd(Z_filt, axis=0)
    N_valid = np.sum(~np.isnan(Z_filt), axis=0)

    # Enmascarar columnas con pocos puntos válidos
    mascara_baja = N_valid < min_valid_frac * N_filas
    Z_mean[mascara_baja] = np.nan
    Z_std[mascara_baja]  = np.nan

    # Eliminar NaN del perfil final para el ajuste
    validos = ~np.isnan(Z_mean)
    return x_coords[validos], Z_mean[validos], Z_std[validos], N_valid[validos]


# =============================================================================
# AJUSTE Y EXTRACCIÓN DE PARÁMETROS
# =============================================================================

def ajustar_gaussiana(x, z):
    """Ajuste Gaussiano. Retorna (params, r2, y_fit)."""
    H0   = np.max(z)
    x0_0 = x[np.argmax(z)]
    sig0 = (x[-1] - x[0]) / 6.0
    try:
        popt, _ = curve_fit(
            gaussiana, x, z,
            p0=[H0, x0_0, sig0],
            bounds=([0, x[0], 0], [np.inf, x[-1], np.inf]),
            maxfev=10000
        )
        y_fit = gaussiana(x, *popt)
        r2    = r_squared(z, y_fit)
        return popt, r2, y_fit
    except RuntimeError:
        return None, -np.inf, np.zeros_like(x)


def ajustar_super_gaussiana(x, z):
    """Ajuste super-Gaussiano. Retorna (params, r2, y_fit)."""
    H0   = np.max(z)
    x0_0 = x[np.argmax(z)]
    sig0 = (x[-1] - x[0]) / 6.0
    try:
        popt, _ = curve_fit(
            super_gaussiana, x, z,
            p0=[H0, x0_0, sig0, 1.5],
            bounds=([0, x[0], 0, 0.5], [np.inf, x[-1], np.inf, 10]),
            maxfev=20000
        )
        y_fit = super_gaussiana(x, *popt)
        r2    = r_squared(z, y_fit)
        return popt, r2, y_fit
    except RuntimeError:
        return None, -np.inf, np.zeros_like(x)


def extraer_parametros(x, z_mean, z_std):
    """
    Ejecuta el pipeline de ajuste y extrae H, FWHM, W, R².
    Retorna un diccionario con todos los resultados.
    """
    # Centrar en x=0 (opcional, para reporte limpio)
    x_c = x - x[np.argmax(z_mean)]

    # --- Ajuste Gaussiano ---
    popt_g, r2_g, y_fit_g = ajustar_gaussiana(x_c, z_mean)

    if r2_g >= R2_THRESHOLD and popt_g is not None:
        modelo     = "Gaussiano"
        H, x0, sigma = popt_g
        n_sg       = None
        r2         = r2_g
        y_fit      = y_fit_g
        fwhm       = fwhm_from_sigma(sigma)

    else:
        print(f"  R² Gaussiano = {r2_g:.4f} < {R2_THRESHOLD} → intentando Super-Gaussiano...")
        popt_sg, r2_sg, y_fit_sg = ajustar_super_gaussiana(x_c, z_mean)

        if popt_sg is not None and r2_sg > r2_g:
            modelo       = "Super-Gaussiano"
            H, x0, sigma, n_sg = popt_sg
            r2           = r2_sg
            y_fit        = y_fit_sg
            # FWHM numérico para super-Gaussiana
            x_dense  = np.linspace(x_c[0], x_c[-1], 50000)
            y_dense  = super_gaussiana(x_dense, H, x0, sigma, n_sg)
            idx_half = np.where(np.diff(np.sign(y_dense - H / 2)))[0]
            fwhm = (x_dense[idx_half[-1]] - x_dense[idx_half[0]]) if len(idx_half) >= 2 else np.nan
        else:
            print("  Advertencia: ambos ajustes fallaron. Reportando Gaussiano de todos modos.")
            modelo     = "Gaussiano (bajo R²)"
            H, x0, sigma = popt_g if popt_g is not None else (np.max(z_mean), 0, 1)
            n_sg       = None
            r2         = r2_g
            y_fit      = y_fit_g
            fwhm       = fwhm_from_sigma(sigma)

    W = ancho_a_umbral(x_c, y_fit, H, BASE_THRESHOLD)

    return {
        "modelo"  : modelo,
        "H_um"    : H,
        "x0_um"   : x0,
        "sigma_um": sigma,
        "n_sg"    : n_sg,
        "FWHM_um" : fwhm,
        "W_um"    : W,
        "R2"      : r2,
        "x_c"     : x_c,
        "z_mean"  : z_mean,
        "z_std"   : z_std,
        "y_fit"   : y_fit,
    }


# =============================================================================
# FIGURA
# =============================================================================

def graficar(res, output_dir):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    x      = res["x_c"]
    z_mean = res["z_mean"]
    z_std  = res["z_std"]
    y_fit  = res["y_fit"]
    H      = res["H_um"]
    fwhm   = res["FWHM_um"]
    W      = res["W_um"]
    r2     = res["R2"]
    modelo = res["modelo"]

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    # Banda de incertidumbre
    ax.fill_between(x, z_mean - z_std, z_mean + z_std,
                    alpha=0.25, color="#5B8DB8", label=r"$\bar{Z} \pm \sigma$")

    # Perfil promedio
    ax.plot(x, z_mean, color="#1A3D5C", lw=1.5, label="Perfil promedio")

    # Curva ajustada
    ax.plot(x, y_fit, color="#C0392B", lw=2.0, ls="--",
            label=f"Ajuste {modelo} ($R^2={r2:.4f}$)")

    # Anotación H
    ax.annotate("", xy=(0, H), xytext=(0, 0),
                arrowprops=dict(arrowstyle="<->", color="#2ECC71", lw=1.5))
    ax.text(x.max() * 0.05, H / 2,
            f"$H = {H:.1f}$ µm", color="#2ECC71", va="center", fontsize=9)

    # Anotación FWHM
    if not np.isnan(fwhm):
        ax.annotate("", xy=(fwhm / 2, H / 2), xytext=(-fwhm / 2, H / 2),
                    arrowprops=dict(arrowstyle="<->", color="#E67E22", lw=1.5))
        ax.text(0, H / 2 * 1.12,
                f"FWHM $= {fwhm:.1f}$ µm", color="#E67E22",
                ha="center", fontsize=9)

    # Anotación W
    if not np.isnan(W):
        nivel_base = BASE_THRESHOLD * H
        ax.axhline(nivel_base, color="gray", lw=0.8, ls=":")
        ax.annotate("", xy=(W / 2, nivel_base), xytext=(-W / 2, nivel_base),
                    arrowprops=dict(arrowstyle="<->", color="#8E44AD", lw=1.5))
        ax.text(0, nivel_base * 1.25,
                f"$W_{{10\%}} = {W:.1f}$ µm", color="#8E44AD",
                ha="center", fontsize=9)

    ax.set_xlabel("Posición transversal $x$ [µm]", fontsize=11)
    ax.set_ylabel("Altura $Z$ [µm]", fontsize=11)
    ax.set_title("Perfil de deposición — Cold Spray CP-Ti", fontsize=12)
    ax.legend(fontsize=9, loc="upper right")
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)
    ax.grid(True, which="minor", ls=":", alpha=0.2)

    plt.tight_layout()
    fig_path = Path(output_dir) / "perfil_deposicion.png"
    plt.savefig(fig_path, dpi=DPI, bbox_inches="tight")
    print(f"  Figura guardada en: {fig_path}")
    plt.show()


# =============================================================================
# REPORTE DE TEXTO
# =============================================================================

def imprimir_reporte(res):
    print("\n" + "=" * 50)
    print("  REPORTE DE CARACTERIZACIÓN DE PERFIL")
    print("=" * 50)
    print(f"  Modelo de ajuste : {res['modelo']}")
    print(f"  R²               : {res['R2']:.5f}")
    print(f"  H  (altura pico) : {res['H_um']:.2f} µm")
    print(f"  σ  (sigma)       : {res['sigma_um']:.2f} µm")
    if res["n_sg"] is not None:
        print(f"  n  (orden SG)    : {res['n_sg']:.3f}")
    print(f"  FWHM             : {res['FWHM_um']:.2f} µm")
    print(f"  W (base {int(BASE_THRESHOLD*100):d}%)     : {res['W_um']:.2f} µm")
    print("=" * 50 + "\n")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print(f"Cargando datos desde: {CSV_PATH}")
    x_coords, y_coords, Z = cargar_matriz(CSV_PATH)
    print(f"  Mapa cargado: {Z.shape[0]} filas × {Z.shape[1]} columnas")

    print("Prefiltrado MAD...")
    Z_filt = prefiltrar_mad(Z, k=MAD_K)
    n_outliers = np.sum(np.isnan(Z_filt) & ~np.isnan(Z))
    print(f"  Outliers eliminados: {n_outliers} celdas "
          f"({100 * n_outliers / Z.size:.2f}% del total)")

    print("Promediando en dirección de construcción (Y)...")
    x, z_mean, z_std, n_valid = promediar_columnas(x_coords, Z_filt)
    print(f"  Columnas válidas para el ajuste: {len(x)}")

    print("Ajustando perfil...")
    res = extraer_parametros(x, z_mean, z_std)

    imprimir_reporte(res)
    graficar(res, OUTPUT_DIR)