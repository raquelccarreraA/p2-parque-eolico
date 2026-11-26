import argparse
from conexiones import conectar_cassandra


def leer_argumentos():
    # Preparamos los parametros que recibira el script por consola
    parser = argparse.ArgumentParser(
        description="Carga las lecturas del parque eolico en Cassandra."
    )
    parser.add_argument(
        "--archivo",
        required=True,
        help="Ruta del archivo CSV con las lecturas generadas.",
    )
    return parser.parse_args()


def main():
    argumentos = leer_argumentos()
    cluster, sesion = conectar_cassandra()

    try:
        print(f"Conectado a Cassandra. Archivo pendiente de cargar: {argumentos.archivo}")
        # Aqui ira la lectura del CSV y los INSERT cuando este listo el esquema de tablas
    finally:
        # Cerramos siempre la conexion al terminar
        cluster.shutdown()


if __name__ == "__main__":
    main()