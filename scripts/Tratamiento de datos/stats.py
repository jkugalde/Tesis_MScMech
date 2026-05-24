import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.neighbors import KDTree

# ─────────────────────────────────────────
# 1. CARGAR DATOS
# ─────────────────────────────────────────
df = pd.read_csv("vertices2.txt", header=None, sep=r"\s+",
                 names=["x", "y", "z", "R", "G", "B", "d"])

print(f"Puntos totales: {len(df)}")
print(f"Rango distancias: {df['d'].min():.6f} a {df['d'].max():.6f} mm\n")

# ─────────────────────────────────────────
# 2. ESTADÍSTICAS DESCRIPTIVAS
# ─────────────────────────────────────────
over  = df[df["d"] >  0.0]
under = df[df["d"] <  0.0]
exact = df[df["d"] == 0.0]

print("═══ ESTADÍSTICAS GENERALES ═══")
print(f"  Media:              {df['d'].mean():.6f} mm")
print(f"  Desv. estándar:     {df['d'].std():.6f} mm")
print(f"  Mediana:            {df['d'].median():.6f} mm")
print(f"  RMSE:               {np.sqrt((df['d']**2).mean()):.6f} mm")
print(f"  Mín:                {df['d'].min():.6f} mm")
print(f"  Máx:                {df['d'].max():.6f} mm")
print(f"  Rango total:        {df['d'].max() - df['d'].min():.6f} mm")

print("\n═══ PERCENTILES ═══")
for p in [25, 50, 75, 90, 95, 99]:
    print(f"  P{p:02d}:               {df['d'].quantile(p/100):.6f} mm")

print("\n═══ DISTRIBUCIÓN ═══")
print(f"  Sobredepósito (d>0): {len(over):5d} pts  ({100*len(over)/len(df):.1f}%)")
print(f"  Subdepósito   (d<0): {len(under):5d} pts  ({100*len(under)/len(df):.1f}%)")
print(f"  Exacto        (d=0): {len(exact):5d} pts  ({100*len(exact)/len(df):.1f}%)")

print("\n═══ TOLERANCIAS ═══")
for tol in [0.05, 0.10, 0.20, 0.50]:
    dentro = df[df["d"].abs() <= tol]
    print(f"  Dentro de ±{tol:.2f} mm:  {len(dentro):5d} pts  ({100*len(dentro)/len(df):.1f}%)")

# ─────────────────────────────────────────
# 3. CÁLCULO DE VOLÚMENES
# ─────────────────────────────────────────
print("\n═══ VOLÚMENES ═══")

# Área por punto via k-NN
points = df[["x", "y", "z"]].values
tree = KDTree(points)
dist_knn, _ = tree.query(points, k=2)
r_mean = dist_knn[:, 1].mean()
A_per_point = np.pi * r_mean**2

print(f"  Área estimada por punto: {A_per_point:.6f} mm²")

V_over  =  (over["d"]  * A_per_point).sum()
V_under =  (under["d"] * A_per_point).sum()
V_neto  = V_over + V_under

print(f"  Volumen sobredepósito:  +{V_over:.4f} mm³")
print(f"  Volumen subdepósito:     {V_under:.4f} mm³")
print(f"  Desviación volumétrica neta: {V_neto:.4f} mm³")

# ─────────────────────────────────────────
# 4. FIGURAS
# ─────────────────────────────────────────

fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# --- Histograma general ---
ax = axes[0]
ax.hist(df["d"], bins=60, color="steelblue", edgecolor="white", linewidth=0.3)
ax.axvline(df["d"].mean(),   color="red",    linestyle="--", label=f"Media = {df['d'].mean():.4f}")
ax.axvline(df["d"].median(), color="orange", linestyle="--", label=f"Mediana = {df['d'].median():.4f}")
ax.axvline(0, color="black", linestyle="-", linewidth=1.5, label="Nominal")
ax.set_xlabel("Distancia signed (mm)")
ax.set_ylabel("Frecuencia")
ax.set_title("Distribución de desviaciones")
ax.legend(fontsize=8)

# --- Histograma separado sobre/sub ---
ax = axes[1]
ax.hist(over["d"],  bins=40, color="tomato",     alpha=0.7, label=f"Sobredepósito (n={len(over)})")
ax.hist(under["d"], bins=40, color="dodgerblue", alpha=0.7, label=f"Subdepósito (n={len(under)})")
ax.axvline(0, color="black", linestyle="-", linewidth=1.5)
ax.set_xlabel("Distancia signed (mm)")
ax.set_ylabel("Frecuencia")
ax.set_title("Sobre vs. subdepósito")
ax.legend(fontsize=8)

# --- Mapa espacial (vista superior X-Z) ---
ax = axes[2]
sc = ax.scatter(df["x"], df["z"], c=df["d"], cmap="RdBu_r",
                s=1, vmin=-df["d"].abs().quantile(0.99),
                      vmax= df["d"].abs().quantile(0.99))
plt.colorbar(sc, ax=ax, label="Distancia signed (mm)")
ax.set_xlabel("x (mm)")
ax.set_ylabel("z (mm)")
ax.set_title("Mapa espacial de desviaciones")
ax.set_aspect("equal")

plt.tight_layout()
plt.savefig("comparacion_geometrica.png", dpi=200, bbox_inches="tight")
plt.show()
print("\nFigura guardada: comparacion_geometrica.png")