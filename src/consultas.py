import argparse
from datetime import date
from decimal import Decimal
from cassandra.query import SimpleStatement
from conexiones import conectar_cassandra
from consistencia import LEER_ALARMAS, LEER_LECTURAS
from sentencias_cql import (
    CONSULTAR_ALARMAS_PARQUE,
    CONSULTAR_ENERGIA_DIA,
    CONSULTAR_LECTURAS_DIA,
    CONSULTAR_LECTURAS_DIA_CON_LIMITE,
    CONSULTAR_ULTIMA_LECTURA,
)


def leer_argumentos():
    # Preparamos los parametros que recibe el script por consola
    analizador = argparse.ArgumentParser(
        description="Ejecuta las 4 consultas del parque eolico en Cassandra."
    )
    analizador.add_argument(
        "--aeroxerador",
        default="MB-01",
        help="Identificador del aerogenerador (por defecto: MB-01).",
    )
    analizador.add_argument(
        "--dia",
        required=True,
        help="Dia a consultar en formato AAAA-MM-DD.",
    )
    analizador.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Numero maximo de lecturas a mostrar en la consulta 1 (por defecto muestra todas).",
    )
    return analizador.parse_args()


def con_nivel(sentencia_cql, nivel):
    # Envuelve la consulta para que se ejecute con su nivel de consistencia (ver consistencia.py)
    return SimpleStatement(sentencia_cql, consistency_level=nivel)


def consultar_lecturas_dia(sesion, aeroxerador_id, dia, limite):
    print(f"\n=== 1. Lecturas de {aeroxerador_id} el {dia} (mas recientes primero) ===")

    # Si el usuario pasa un limite, usamos la consulta con LIMIT
    if limite is not None:
        filas = list(
            sesion.execute(con_nivel(CONSULTAR_LECTURAS_DIA_CON_LIMITE, LEER_LECTURAS),
                           (aeroxerador_id, dia, limite))
        )
    else:
        filas = list(
            sesion.execute(con_nivel(CONSULTAR_LECTURAS_DIA, LEER_LECTURAS),
                           (aeroxerador_id, dia))
        )

    print(f"Total filas mostradas: {len(filas)}")
    for fila in filas:
        print(
            f"  {fila.data_hora} | viento={fila.vento_ms} m/s | dir={fila.direccion_graos} | "
            f"pot={fila.potencia_kw} kW | rpm={fila.rotor_rpm} | "
            f"temp={fila.temp_xerador_c} C | estado={fila.estado}"
        )


def consultar_energia_dia(sesion, aeroxerador_id, dia):
    print(f"\n=== 2. Energia producida por {aeroxerador_id} el {dia} ===")

    # Cassandra suma todas las potencias de esa particion directamente
    fila = sesion.execute(con_nivel(CONSULTAR_ENERGIA_DIA, LEER_LECTURAS),
                          (aeroxerador_id, dia)).one()

    # Si no hay lecturas para ese dia, la suma viene como None y ponemos 0
    suma_potencia = fila.suma_potencia if fila and fila.suma_potencia is not None else Decimal("0")

    # Cada lectura son 10 minutos (10/60 de hora), asi pasamos de kW a kWh
    energia_kwh = suma_potencia * Decimal(10) / Decimal(60)
    print(f"  Suma de potencias: {suma_potencia:.1f} kW")
    print(f"  Energia total:     {energia_kwh:.2f} kWh")


def consultar_alarmas_parque(sesion, parque_id, dia):
    print(f"\n=== 3. Alarmas del parque {parque_id} el {dia} (orden horario) ===")

    filas = list(sesion.execute(con_nivel(CONSULTAR_ALARMAS_PARQUE, LEER_ALARMAS),
                                (parque_id, dia)))

    print(f"Total alarmas: {len(filas)}")
    for fila in filas:
        print(
            f"  {fila.data_hora} | {fila.aeroxerador_id} | viento={fila.vento_ms} m/s | "
            f"pot={fila.potencia_kw} kW | temp={fila.temp_xerador_c} C"
        )


def consultar_ultima_lectura(sesion, parque_id):
    print(f"\n=== 4. Ultima lectura de cada aerogenerador del parque {parque_id} ===")

    filas = list(sesion.execute(con_nivel(CONSULTAR_ULTIMA_LECTURA, LEER_LECTURAS),
                                (parque_id,)))

    print(f"Total aerogeneradores: {len(filas)}")
    for fila in filas:
        print(
            f"  {fila.aeroxerador_id} | {fila.data_hora} | viento={fila.vento_ms} m/s | "
            f"pot={fila.potencia_kw} kW | temp={fila.temp_xerador_c} C | estado={fila.estado}"
        )


def iniciar():
    argumentos = leer_argumentos()

    # Validamos que la fecha tenga formato AAAA-MM-DD
    dia_consulta = date.fromisoformat(argumentos.dia)
    # Sacamos el identificador del parque a partir del aerogenerador (MB-01 -> MB)
    parque_id = argumentos.aeroxerador.split("-")[0]

    cluster, sesion = conectar_cassandra()
    try:
        consultar_lecturas_dia(sesion, argumentos.aeroxerador, dia_consulta, argumentos.limite)
        consultar_energia_dia(sesion, argumentos.aeroxerador, dia_consulta)
        consultar_alarmas_parque(sesion, parque_id, dia_consulta)
        consultar_ultima_lectura(sesion, parque_id)
    finally:
        # Cerramos siempre la conexion al terminar
        cluster.shutdown()


if __name__ == "__main__":
    iniciar()