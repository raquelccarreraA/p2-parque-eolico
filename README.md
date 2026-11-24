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

### 4. Generador de lecturas (`src/xera_lecturas.py`)        

Como no tenemos acceso al SCADA, las lecturas se generan con un script que cumple siempre el contrato de datos (apartado 2).

```bash
python3 src/xera_lecturas.py --dias 7 --inicio 2026-11-01 --semilla 42 --salida lecturas.csv
```

| Parámetro | Por defecto | Para qué |
|---|---|---|
| `--dias` | 7 | número de días (mínimo 7) |
| `--inicio` | 2026-11-01 | primer día |
| `--semilla` | 42 | misma semilla = mismos datos |
| `--salida` | lecturas.csv | fichero CSV |

Con 7 días salen 12 × 144 × 7 = **12.096 lecturas**. El CSV no se sube al repo: se puede volver a generar con la semilla.

Cómo cumple las reglas:
- **Regla 1:** una lectura cada 10 minutos para cada aerogenerador, 144 al día, sin huecos ni repeticiones.
- **Regla 2:** potencia 0 con viento < 3 o > 25 m/s; sube entre 3 y 12; unos 3.000 kW entre 12 y 25.
- **Regla 3:** `parado` con 0 kW y 0 rpm; `alarma` en un 1 % de las lecturas (temperatura alta); `ok` el resto.
- **Regla 4:** hay un viento general del parque que cambia poco cada 10 minutos, y cada aerogenerador tiene un viento parecido a él.

Antes de guardar, el script **comprueba el contrato** (rangos, 144 lecturas por aerogenerador y día, sin duplicados, parados con 0 kW y 0 rpm). Si algo falla, no guarda nada y muestra el error.

## Modelo de datos (4.1)

## Niveles de consistencia y pruebas de fallo (4.3)

## Crecimiento del clúster (4.4)
