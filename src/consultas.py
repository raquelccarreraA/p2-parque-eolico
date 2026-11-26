import argparse
from conexiones import conectar_cassandra


def leer_argumentos():
    # Preparamos los parametros para consultar un aerogenerador y un dia concretos
    parser = argparse.ArgumentParser(
        description="Ejecuta las cuatro consultas del parque eolico en Cassandra."
    )
    parser.add_argument(
        "--aeroxerador",
        default="MB-01",
        help="Identificador del aerogenerador (ejemplo: MB-01).",
    )
    parser.add_argument(
        "--dia",
        required=True,
        help="Dia a consultar en formato AAAA-MM-DD.",
    )
    return parser.parse_args()


def main():
    argumentos = leer_argumentos()
    cluster, sesion = conectar_cassandra()

    try:
        print(
            f"Conectado a Cassandra. Consultas pendientes para "
            f"{argumentos.aeroxerador} en el dia {argumentos.dia}."
        )
        # Aqui iran las 4 consultas cuando este listo el esquema de tablas
    finally:
        # Cerramos siempre la conexion al terminar
        cluster.shutdown()


if __name__ == "__main__":
    main()