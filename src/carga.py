import argparse
import csv
import time
from datetime import datetime, timezone
from decimal import Decimal
from cassandra.concurrent import execute_concurrent_with_args
from conexiones import conectar_cassandra
from consistencia import ESCRIBIR_ALARMAS, ESCRIBIR_LECTURAS
from sentencias_cql import (
    INSERTAR_ALARMA,
    INSERTAR_ENERGIA,
    INSERTAR_LECTURA,
    INSERTAR_ULTIMA_LECTURA,
)


def leer_argumentos():
    # Preparamos los parametros que recibe el script por consola
    analizador = argparse.ArgumentParser(
        description="Carga las lecturas del parque eolico en las 4 tablas de Cassandra."
    )
    analizador.add_argument(
        "--archivo",
        required=True,
        help="Ruta del archivo CSV con las lecturas generadas.",
    )
    return analizador.parse_args()


def leer_datos_desde_csv(ruta_archivo):
    # Creamos una lista de filas para cada tabla de Cassandra
    datos_lecturas = []
    datos_energia = []
    datos_alarmas = []
    datos_ultima_lectura = []

    with open(ruta_archivo, mode="r", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            aeroxerador_id = fila["aeroxerador_id"]
            # Sacamos el identificador del parque cogiendo lo que va antes del guion (MB-07 -> MB)
            parque_id = aeroxerador_id.split("-")[0]

            # Convertimos el texto de fecha y hora a objeto datetime en UTC
            data_hora = datetime.strptime(
                fila["data_hora"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            # Sacamos solo la fecha (AAAA-MM-DD) para la columna dia
            dia = data_hora.date()
            # Pasamos la fecha a microsegundos para el USING TIMESTAMP de la tabla 4
            marca_tiempo_microsegundos = int(data_hora.timestamp() * 1_000_000)

            # Usamos Decimal en vez de float para no perder precision en los decimales
            vento_ms = Decimal(fila["vento_ms"])
            direccion_graos = int(fila["direccion_graos"])
            potencia_kw = Decimal(fila["potencia_kw"])
            rotor_rpm = Decimal(fila["rotor_rpm"])
            temp_xerador_c = Decimal(fila["temp_xerador_c"])
            estado = fila["estado"]

            # Tabla 1: todas las lecturas de un aerogenerador en un dia
            datos_lecturas.append((
                aeroxerador_id,
                dia,
                data_hora,
                vento_ms,
                direccion_graos,
                potencia_kw,
                rotor_rpm,
                temp_xerador_c,
                estado,
            ))

            # Tabla 2: solo la potencia para calcular luego la energia del dia
            datos_energia.append((
                aeroxerador_id,
                dia,
                data_hora,
                potencia_kw,
            ))

            # Tabla 3: solo guardamos la fila si el estado es alarma
            if estado == "alarma":
                datos_alarmas.append((
                    parque_id,
                    dia,
                    data_hora,
                    aeroxerador_id,
                    vento_ms,
                    direccion_graos,
                    potencia_kw,
                    rotor_rpm,
                    temp_xerador_c,
                    estado,
                ))

            # Tabla 4: ultima lectura de cada aerogenerador (el timestamp va al final)
            datos_ultima_lectura.append((
                parque_id,
                aeroxerador_id,
                data_hora,
                vento_ms,
                direccion_graos,
                potencia_kw,
                rotor_rpm,
                temp_xerador_c,
                estado,
                marca_tiempo_microsegundos,
            ))

    return datos_lecturas, datos_energia, datos_alarmas, datos_ultima_lectura


def insertar_en_paralelo(sesion, sentencia_cql, lista_datos, nombre_tabla, nivel):
    # Si no hay filas para esa tabla (por ejemplo, un dia sin alarmas), no hacemos nada
    if not lista_datos:
        print(f"Tabla {nombre_tabla}: 0 filas para insertar.")
        return

    # Preparamos la sentencia una sola vez para que Cassandra no la analice miles de veces
    sentencia_preparada = sesion.prepare(sentencia_cql)
    # Nivel de consistencia de esta escritura (ver consistencia.py)
    sentencia_preparada.consistency_level = nivel

    # Enviamos las inserciones en paralelo de 50 en 50 para ir rapido sin saturar Docker
    resultados = execute_concurrent_with_args(
        sesion,
        sentencia_preparada,
        lista_datos,
        concurrency=50,
    )

    # Comprobamos si alguna insercion ha fallado
    fallos = [resultado for exito, resultado in resultados if not exito]
    if fallos:
        raise RuntimeError(
            f"Fallaron {len(fallos)} inserciones en {nombre_tabla}. Primer error: {fallos[0]}"
        )

    print(f"Tabla {nombre_tabla}: {len(lista_datos)} inserciones completadas.")


def iniciar():
    argumentos = leer_argumentos()
    tiempo_inicio = time.perf_counter()

    print(f"Leyendo archivo: {argumentos.archivo}")
    (
        datos_lecturas,
        datos_energia,
        datos_alarmas,
        datos_ultima_lectura,
    ) = leer_datos_desde_csv(argumentos.archivo)

    cluster, sesion = conectar_cassandra()
    try:
        insertar_en_paralelo(
            sesion, INSERTAR_LECTURA, datos_lecturas, "lecturas_por_aeroxerador_dia",
            ESCRIBIR_LECTURAS,
        )
        insertar_en_paralelo(
            sesion, INSERTAR_ENERGIA, datos_energia, "energia_por_aeroxerador_dia",
            ESCRIBIR_LECTURAS,
        )
        insertar_en_paralelo(
            sesion, INSERTAR_ALARMA, datos_alarmas, "alarmas_por_parque_dia",
            ESCRIBIR_ALARMAS,
        )
        insertar_en_paralelo(
            sesion, INSERTAR_ULTIMA_LECTURA, datos_ultima_lectura, "ultima_lectura_por_parque",
            ESCRIBIR_LECTURAS,
        )

        tiempo_total = time.perf_counter() - tiempo_inicio
        print(f"Carga terminada en {tiempo_total:.2f} segundos.")
    finally:
        # Cerramos siempre la conexion al terminar
        cluster.shutdown()


if __name__ == "__main__":
    iniciar()