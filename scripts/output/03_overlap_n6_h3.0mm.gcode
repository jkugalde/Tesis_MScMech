%
; =============================================================
; Experimento CSAM -- PocketNC 5 ejes
; Solapamiento -- n=6 lineas, h=3.0 mm, lado=18.0 mm, wave=False
; Tobera: nozzle_A -- Tobera convergente-divergente, garganta 1 mm, salida 6 mm
; Z-offset tobera: 0.0 mm
; =============================================================
G21
G90
G17

; Parametros principales: feed=200.0 mm/min, standoff=20.0 mm, A=90.0 deg

G0 Z40.000

; === Raster principal ===
; Linea principal 1/6 | Y=-9.000 mm | L->R
G0 Z40.000
G0 X-9.000 Y-9.000
G0 Z20.000 A90.000
G1 X9.000 Y-9.000 F200.000

; Linea principal 2/6 | Y=-6.000 mm | R->L
G0 Z40.000
G0 X9.000 Y-6.000
G0 Z20.000 A90.000
G1 X-9.000 Y-6.000 F200.000

; Linea principal 3/6 | Y=-3.000 mm | L->R
G0 Z40.000
G0 X-9.000 Y-3.000
G0 Z20.000 A90.000
G1 X9.000 Y-3.000 F200.000

; Linea principal 4/6 | Y=0.000 mm | R->L
G0 Z40.000
G0 X9.000 Y0.000
G0 Z20.000 A90.000
G1 X-9.000 Y0.000 F200.000

; Linea principal 5/6 | Y=3.000 mm | L->R
G0 Z40.000
G0 X-9.000 Y3.000
G0 Z20.000 A90.000
G1 X9.000 Y3.000 F200.000

; Linea principal 6/6 | Y=6.000 mm | R->L
G0 Z40.000
G0 X9.000 Y6.000
G0 Z20.000 A90.000
G1 X-9.000 Y6.000 F200.000

; --- Fin de experimento ---
G0 Z40.000
G0 A0.000
M2
%
