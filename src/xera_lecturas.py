"""
xera_lecturas.py
Genera lecturas inventadas del parque eólico de Monte Brañas
que cumplen el contrato de datos.

Uso:
    python src/xera_lecturas.py --dias 7 --inicio 2026-11-01 --semilla 42 --salida lecturas.csv
"""

import argparse
import csv
import random
import sys
from datetime import datetime, timedelta

# Los 12 aerogeneradores: MB-01, MB-02 ... MB-12
AEROXERADORES = [f"MB-{n:02d}" for n in range(1, 13)]

LECTURAS_POR_DIA = 144   # 24 h x 6 lecturas por hora
MINUTOS = 10             # una lectura cada 10 min

# Columnas del CSV = campos del contrato
COLUMNAS = ["aeroxerador_id", "data_hora", "vento_ms", "direccion_graos",
            "potencia_kw", "rotor_rpm", "temp_xerador_c", "estado"]


def limitar(valor, minimo, maximo):
    # para que nunca se salga del rango del contrato
    return max(minimo, min(maximo, valor))


def calcular_potencia(vento):
    # regla 2: la potencia depende del viento
    if vento < 3 or vento > 25:
        return 0.0                              # poco o demasiado viento: no produce
    if vento < 12:
        return 3000 * ((vento - 3) / 9) ** 3  # sube con el viento
    return random.uniform(2950, 3000)         # a tope, unos 3000 kW


def crear_lectura(aero, momento, vento, direccion):
    potencia = round(calcular_potencia(vento), 1)

    # regla 3: el estado
    if potencia == 0:
        estado = "parado"                     # parado = 0 kW y 0 rpm
        rpm = 0.0
        temp = random.uniform(15, 25)         # parado, se enfría
    else:
        rpm = limitar(5 + vento * 0.9, 0, 16) # más viento, gira más rápido
        temp = 25 + potencia / 3000 * 40 + random.uniform(-3, 3)  # más potencia, más calor
        if random.random() < 0.01:            # más o menos el 1 % son alarmas
            estado = "alarma"
            temp = random.uniform(82, 90)     # ej: temperatura alta
        else:
            estado = "ok"

    return {
        "aeroxerador_id": aero,
        "data_hora": momento.strftime("%Y-%m-%d %H:%M:%S"),
        "vento_ms": vento,
        "direccion_graos": direccion,
        "potencia_kw": potencia,
        "rotor_rpm": round(rpm, 1),
        "temp_xerador_c": round(limitar(temp, 10, 90), 1),
        "estado": estado,
    }


def xerar(dias, inicio, semilla):
    random.seed(semilla)                      # misma semilla = mismos datos

    lecturas = []
    vento_parque = 9.0                        # viento "general" del parque
    direccion_parque = random.randint(0, 359)
    momento = inicio

    for _ in range(dias * LECTURAS_POR_DIA):
        # regla 4: el viento cambia poco de una lectura a la siguiente
        # (y tiende a volver a 9 m/s para no irse a los extremos)
        vento_parque += random.uniform(-0.8, 0.8) + (9 - vento_parque) * 0.01
        vento_parque = limitar(vento_parque, 0, 30)
        direccion_parque = (direccion_parque + random.randint(-5, 5)) % 360

        for aero in AEROXERADORES:
            # regla 4: cada aerogenerador tiene un viento parecido al del parque
            vento = round(limitar(vento_parque + random.uniform(-0.8, 0.8), 0, 30), 1)
            direccion = (direccion_parque + random.randint(-10, 10)) % 360
            lecturas.append(crear_lectura(aero, momento, vento, direccion))

        momento += timedelta(minutes=MINUTOS)  # siguiente lectura: +10 min

    return lecturas


def validar(lecturas):
    # comprueba que todo cumple el contrato y devuelve la lista de errores
    errores = []
    vistas = set()
    por_dia = {}   # cuántas lecturas tiene cada aerogenerador cada día

    for l in lecturas:
        clave = (l["aeroxerador_id"], l["data_hora"])
        if clave in vistas:
            errores.append(f"Repetida: {clave}")
        vistas.add(clave)

        dia = l["data_hora"][:10]
        por_dia[(l["aeroxerador_id"], dia)] = por_dia.get((l["aeroxerador_id"], dia), 0) + 1

        # rangos del contrato
        if l["aeroxerador_id"] not in AEROXERADORES:
            errores.append(f"Aerogenerador raro: {clave}")
        if not l["data_hora"].endswith("0:00"):
            errores.append(f"Hora que no es en punto de 10 min: {clave}")
        if not 0 <= l["vento_ms"] <= 30:
            errores.append(f"Viento fuera de rango: {clave}")
        if not 0 <= l["direccion_graos"] <= 359:
            errores.append(f"Dirección fuera de rango: {clave}")
        if not 0 <= l["potencia_kw"] <= 3000:
            errores.append(f"Potencia fuera de rango: {clave}")
        if not 0 <= l["rotor_rpm"] <= 16:
            errores.append(f"Rotor fuera de rango: {clave}")
        if not 10 <= l["temp_xerador_c"] <= 90:
            errores.append(f"Temperatura fuera de rango: {clave}")
        if l["estado"] not in ("ok", "alarma", "parado"):
            errores.append(f"Estado raro: {clave}")

        # parado tiene que ser 0 kW y 0 rpm
        if l["estado"] == "parado" and (l["potencia_kw"] != 0 or l["rotor_rpm"] != 0):
            errores.append(f"Parado pero produce o gira: {clave}")

    # 144 lecturas por aerogenerador y día, sin huecos
    for (aero, dia), n in por_dia.items():
        if n != LECTURAS_POR_DIA:
            errores.append(f"{aero} el {dia} tiene {n} lecturas (deberían ser 144)")

    return errores


def main():
    parser = argparse.ArgumentParser(description="Genera lecturas del parque eólico")
    parser.add_argument("--dias", type=int, default=7, help="número de días (mínimo 7 para la práctica)")
    parser.add_argument("--inicio", default="2026-11-01", help="primer día, AAAA-MM-DD")
    parser.add_argument("--semilla", type=int, default=42, help="para poder repetir los mismos datos")
    parser.add_argument("--salida", default="lecturas.csv", help="fichero CSV de salida")
    args = parser.parse_args()

    inicio = datetime.strptime(args.inicio, "%Y-%m-%d")
    lecturas = xerar(args.dias, inicio, args.semilla)

    # antes de guardar, comprobar el contrato
    errores = validar(lecturas)
    if errores:
        print(f"ERROR: hay {len(errores)} problemas con el contrato:")
        for e in errores[:10]:
            print("  -", e)
        sys.exit(1)

    with open(args.salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writeheader()
        writer.writerows(lecturas)

    # resumen para ver que todo tiene sentido
    total = len(lecturas)
    print(f"OK: {total} lecturas guardadas en {args.salida}")
    print(f"    {args.dias} días desde {args.inicio}, semilla {args.semilla}")
    for estado in ("ok", "alarma", "parado"):
        n = sum(1 for l in lecturas if l["estado"] == estado)
        print(f"    {estado:7} {n:6}  ({n / total:.1%})")

# solo se ejecuta si lanzas este archivo directamente
if __name__ == "__main__":
    main()