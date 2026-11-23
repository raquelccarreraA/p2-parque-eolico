# P2. Parque eólico de Monte Brañas

Big Data Aplicado · UD1 · Proyecto en grupo

## Equipo

| Persona | Issues | Perfil |
|---|---|---|
| A | 1 y 7 | Infraestructura |
| B | 2 y 6 | Datos |
| C | 3 y 5 | Modelo y consistencia |
| D | 4 y 8 | Aplicación y presentación |

## Cómo arrancar y ejecutar

### 1. Clúster de Cassandra (3 nodos)

```bash
docker compose up -d          # arranca cass1 (semilla), cass2 y cass3, uno tras otro
docker compose ps             # esperar a que los tres estén "healthy" (2-4 min)
```

Cada nodo tiene su volumen (`cass1_data`, `cass2_data`, `cass3_data`), así que los datos sobreviven a `docker compose down`. Para empezar de cero: `docker compose down -v`.

Comprobar que los tres nodos están `UN` (Up/Normal):

```bash
docker exec cass1 nodetool status
```

### 2. Keyspace (3 réplicas, `NetworkTopologyStrategy`)

```bash
docker exec -i cass1 cqlsh < cql/01_keyspace.cql
docker exec cass1 cqlsh -e "DESCRIBE KEYSPACE parque"
```

### 3. Contenedor `app` (Python + cassandra-driver)

Desde Windows el driver no ve las IP internas de Docker, por eso los scripts se ejecutan en un contenedor de la misma red. El servicio tiene el perfil `app`:

```bash
docker compose --profile app up -d --build app
docker compose exec app python src/<script>.py
docker compose exec app bash        # shell interactivo
```

Dentro del contenedor, los nodos son accesibles como `cass1`, `cass2` y `cass3` (también en la variable `CASSANDRA_HOSTS`).

## Modelo de datos (4.1)

## Niveles de consistencia y pruebas de fallo (4.3)

## Crecimiento del clúster (4.4)
