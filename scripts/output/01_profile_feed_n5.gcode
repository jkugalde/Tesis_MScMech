; =============================================================
; Experimento CSAM -- PocketNC 5 ejes
; Caracterizacion de perfil - variable: feed [100.0 -> 500.0], n=5
; Tobera: nozzle_A -- Tobera convergente-divergente, garganta 1 mm, salida 6 mm
; Z-offset tobera: 0.0 mm
; =============================================================
%
G21
G90
G17

G0 Z-20
G0 X-30.000 Y0.000

; Linea 1/5 -- feed=100.00 mm/min | Y=0.00 mm | Z=20.000 mm | A=90.0deg
G0 Z-20.000
G0 X-30.000 Y0.000
G0 Z-20.000 A90.000
G1 X30.000 Y0.000 F100.000

; Linea 2/5 -- feed=200.00 mm/min | Y=8.00 mm | Z=20.000 mm | A=90.0deg
G0 Z-20.000
G0 X-30.000 Y8.000
G0 Z-20.000 A90.000
G1 X30.000 Y8.000 F200.000

; Linea 3/5 -- feed=300.00 mm/min | Y=16.00 mm | Z=20.000 mm | A=90.0deg
G0 Z-20.000
G0 X-30.000 Y16.000
G0 Z-20.000 A90.000
G1 X30.000 Y16.000 F300.000

; Linea 4/5 -- feed=400.00 mm/min | Y=24.00 mm | Z=20.000 mm | A=90.0deg
G0 Z-20.000
G0 X-30.000 Y24.000
G0 Z-20.000 A90.000
G1 X30.000 Y24.000 F400.000

; Linea 5/5 -- feed=500.00 mm/min | Y=32.00 mm | Z=20.000 mm | A=90.0deg
G0 Z-20.000
G0 X-30.000 Y32.000
G0 Z-20.000 A90.000
G1 X30.000 Y32.000 F500.000

; --- Fin de experimento ---
G0 Z-20.000
G0 A90.000
M30
%