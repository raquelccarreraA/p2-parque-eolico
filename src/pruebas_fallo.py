"""
pruebas_fallo.py
Pruebas de fallo desde Python (apartado 4.3.3): ejecuta una operación con un
nivel de consistencia y muestra si funciona o falla según los nodos parados.

Uso (con algún nodo parado antes con "docker stop cass3"):
    python src/pruebas_fallo.py --operacion escribir --nivel QUORUM
    python src/pruebas_fallo.py --operacion leer --nivel ALL --aeroxerador MB-01 --dia 2026-11-01

La escritura guarda una lectura de prueba del aerogenerador "PROBA-01": no
toca los datos de MB-01..MB-12, así que no cambia el resultado de consultas.py.
"""

import argparse
import logging
import os
import socket
import sys
from datetime import date, datetime, timezone
from decimal import Decimal

from cassandra import ConsistencyLevel, ReadTimeout, Unavailable, WriteTimeout
from cassandra.cluster import NoHostAvailable
from conexiones import conectar_cassandra

KEYSPACE = "parque"
AEROXERADOR_PROBA = "PROBA-01"

NIVELES = {
    "ONE": ConsistencyLevel.ONE,
    "QUORUM": ConsistencyLevel.QUORUM,
    "ALL": ConsistencyLevel.ALL,
}

INSERTAR_PROBA = """
    INSERT INTO lecturas_por_aeroxerador_dia (
        aeroxerador_id, dia, data_hora, vento_ms, direccion_graos,
        potencia_kw, rotor_rpm, temp_xerador_c, estado
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

CONTAR_LECTURAS = """
    SELECT COUNT(*) AS n FROM lecturas_por_aeroxerador_dia
    WHERE aeroxerador_id = ? AND dia = ?
"""


def leer_argumentos():
    analizador = argparse.ArgumentParser(
        description="Prueba una operación con un nivel de consistencia y nodos parados."
    )
    analizador.add_argument("--operacion", choices=["escribir", "leer"], required=True)
    analizador.add_argument("--nivel", choices=list(NIVELES), required=True)
    analizador.add_argument("--aeroxerador", default="MB-01",
                            help="aerogenerador que se lee (solo para --operacion leer)")
    analizador.add_argument("--dia", default="2026-11-01",
                            help="día que se lee, AAAA-MM-DD (solo para --operacion leer)")
    return analizador.parse_args()


def ip_de(nombre):
    # Un contenedor parado desaparece del DNS de Docker: si su nombre no se
    # resuelve, ese nodo está parado.
    try:
        return socket.gethostbyname(nombre)
    except socket.gaierror:
        return None


def nodos_parados():
    nombres = [n.strip() for n in os.getenv("CASSANDRA_HOSTS", "cass1,cass2,cass3").split(",")]
    return [n for n in nombres if ip_de(n) is None]


def ips_vivas():
    # IP de los nodos en marcha (cass4 solo existe en el apartado 4.4)
    return {ip for ip in (ip_de(f"cass{i}") for i in range(1, 5)) if ip}


def replicas_necesarias(nivel, rf):
    return {"ONE": 1, "QUORUM": rf // 2 + 1, "ALL": rf}[nivel]


def iniciar():
    argumentos = leer_argumentos()
    nivel = argumentos.nivel

    # Sin esto, el driver llena la pantalla de avisos por los nodos parados
    logging.getLogger("cassandra").setLevel(logging.CRITICAL)

    parados = nodos_parados()
    cluster, sesion = conectar_cassandra(KEYSPACE)
    try:
        if argumentos.operacion == "escribir":
            ahora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            ahora = ahora.replace(minute=ahora.minute - ahora.minute % 10)
            sentencia = sesion.prepare(INSERTAR_PROBA)
            valores = (AEROXERADOR_PROBA, ahora.date(), ahora, Decimal("0.0"), 0,
                       Decimal("0.0"), Decimal("0.0"), Decimal("15.0"), "parado")
            descripcion = f"escribir una lectura ({AEROXERADOR_PROBA}, {ahora:%Y-%m-%d %H:%M})"
        else:
            dia = date.fromisoformat(argumentos.dia)
            sentencia = sesion.prepare(CONTAR_LECTURAS)
            valores = (argumentos.aeroxerador, dia)
            descripcion = f"leer las lecturas de {argumentos.aeroxerador} el {dia}"

        sentencia.consistency_level = NIVELES[nivel]
        consulta = sentencia.bind(valores)

        # Réplicas de la partición que se toca, y cuántas de ellas están vivas
        replicas = cluster.metadata.get_replicas(KEYSPACE, consulta.routing_key)
        vivas = [h for h in replicas if h.address in ips_vivas()]
        rf = len(replicas)
        necesarias = replicas_necesarias(nivel, rf)

        print("=== Prueba de fallo ===")
        print(f"Nodos parados:          {', '.join(parados) if parados else 'ninguno'}")
        print(f"Operación:              {descripcion}")
        print(f"Nivel de consistencia:  {nivel}")
        print(f"Réplicas de la partición: {rf}, vivas: {len(vivas)}")
        print(f"Réplicas que pide {nivel}: {necesarias}")
        print("--- Resultado ---")

        try:
            try:
                resultado = sesion.execute(consulta)
            except NoHostAvailable as error:
                # El driver reintenta en otro nodo; si los demás están parados,
                # envuelve el error real (Unavailable) en un NoHostAvailable.
                reales = [e for e in error.errors.values() if isinstance(e, Unavailable)]
                if reales:
                    raise reales[0]
                raise
        except Unavailable as error:
            print(f"ERROR Unavailable: {nivel} necesita {error.required_replicas} réplicas "
                  f"y solo hay {error.alive_replicas} vivas. Cassandra no lo intenta.")
            print(f"  Mensaje: {error}")
            sys.exit(1)
        except (WriteTimeout, ReadTimeout) as error:
            print(f"ERROR {type(error).__name__}: no respondieron a tiempo las réplicas necesarias.")
            print(f"  Mensaje: {error}")
            sys.exit(1)
        except NoHostAvailable as error:
            print(f"ERROR NoHostAvailable: ningún nodo pudo coordinar la operación.")
            print(f"  Mensaje: {error}")
            sys.exit(1)

        if argumentos.operacion == "escribir":
            print(f"OK: escritura confirmada por al menos {necesarias} réplica(s).")
        else:
            print(f"OK: {resultado.one().n} lecturas leídas con {nivel}.")
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    iniciar()
