import os
from cassandra.cluster import Cluster


def conectar_cassandra(nombre_keyspace="parque"):
    # Leemos los servidores desde la variable de entorno de Docker Compose
    # Si no existe, usamos los tres nodos por defecto
    texto_servidores = os.getenv("CASSANDRA_HOSTS", "cass1,cass2,cass3")
    lista_servidores = [
        servidor.strip() for servidor in texto_servidores.split(",") if servidor.strip()
    ]

    # Creamos el objeto cluster con la lista de nodos
    cluster = Cluster(lista_servidores)

    # Abrimos la sesion apuntando directamente al keyspace del proyecto
    sesion = cluster.connect(nombre_keyspace)

    # Devolvemos el cluster y la sesion para poder cerrarlo bien al acabar
    return cluster, sesion


if __name__ == "__main__":
    # Prueba rapida si ejecutamos este archivo directamente
    cluster, sesion = conectar_cassandra()
    try:
        # Pedimos a Cassandra el nombre del cluster para comprobar que responde
        fila = sesion.execute("SELECT cluster_name FROM system.local").one()
        print(f"Conexion correcta con el cluster: {fila.cluster_name}")
        print(f"Keyspace activo: {sesion.keyspace}")
    finally:
        # Cerramos siempre la conexion al terminar
        cluster.shutdown()