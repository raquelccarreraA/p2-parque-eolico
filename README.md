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

Esquema completo en [`cql/02_tablas.cql`](cql/02_tablas.cql). Se crea después del keyspace:

```bash
docker exec -i cass1 cqlsh < cql/02_tablas.cql
docker exec cass1 cqlsh -e "DESCRIBE TABLES" -k parque
```

### Por qué una tabla por consulta

En Cassandra no hay `JOIN` y solo se puede filtrar de forma eficiente por la **clave de partición**. Por eso se parte de las consultas, no de las entidades: cada tabla guarda los datos ya agrupados (partición) y ordenados (columnas de agrupación) como los pide su consulta, y así cada consulta lee **una sola partición** en un solo nodo. El precio es duplicar datos (cada lectura se escribe en varias tablas), que en Cassandra es barato: escribir es rápido y el disco es lo que sobra.

### Columnas derivadas

Además de los campos del contrato, `carga.py` calcula dos columnas para poder usarlas en las claves:

| Columna | Tipo CQL | Cómo se calcula | Para qué |
|---|---|---|---|
| `dia` | `date` | la fecha de `data_hora` (`"2026-11-01 00:10:00"[:10]`) | partir por día: las particiones no crecen sin límite |
| `parque_id` | `text` | prefijo de `aeroxerador_id` (`"MB-07"` → `"MB"`) | preparado para más parques (consultas 3 y 4) |

### Las cuatro tablas

| # | Consulta | Tabla | Clave de partición | Columnas de agrupación | Filas por partición |
|---|---|---|---|---|---|
| 1 | Lecturas de un aerogenerador en un día (recientes primero) | `lecturas_por_aeroxerador_dia` | `(aeroxerador_id, dia)` | `data_hora DESC` | 144 |
| 2 | Energía de un aerogenerador en un día | `energia_por_aeroxerador_dia` | `(aeroxerador_id, dia)` | `data_hora` | 144 |
| 3 | Alarmas de un día en todo el parque (orden horario) | `alarmas_por_parque_dia` | `(parque_id, dia)` | `data_hora ASC, aeroxerador_id ASC` | ~17 (máx. 1.728) |
| 4 | Última lectura de cada aerogenerador | `ultima_lectura_por_parque` | `parque_id` | `aeroxerador_id` | 12 |

**1. `lecturas_por_aeroxerador_dia`**
- *Partición `(aeroxerador_id, dia)`*: la consulta siempre da un aerogenerador y un día, así que todas sus lecturas están juntas en una partición. Si la partición fuese solo `aeroxerador_id`, crecería sin límite (52.560 filas al año, y sigue).
- *Agrupación `data_hora DESC`*: identifica cada lectura dentro del día (no hay dos con la misma hora, regla 1) y las guarda ya de la más reciente a la más antigua, sin ordenar al leer.

```sql
SELECT * FROM lecturas_por_aeroxerador_dia WHERE aeroxerador_id = 'MB-01' AND dia = '2026-11-01';
```

**2. `energia_por_aeroxerador_dia`**
- Guarda solo la potencia de cada intervalo de 10 minutos. La energía es `SUM(potencia_kw) × 10/60` kWh; Cassandra hace la suma dentro de una sola partición.
- *Partición `(aeroxerador_id, dia)`*: la que pide la consulta.
- *Agrupación `data_hora`*: una fila por intervalo. Si se carga dos veces el mismo CSV, cada `INSERT` sobrescribe la misma fila (upsert) y **la energía no se duplica**. Por eso se descartó una tabla `counter`: sumar dos veces la misma lectura daría una energía falsa, y además los contadores no admiten decimales.

```sql
SELECT SUM(potencia_kw) AS suma_kw FROM energia_por_aeroxerador_dia WHERE aeroxerador_id = 'MB-01' AND dia = '2026-11-01';
-- energía_kwh = suma_kw * 10 / 60   (se calcula en consultas.py)
```

**3. `alarmas_por_parque_dia`**
- Solo se insertan las lecturas con `estado = 'alarma'`.
- *Partición `(parque_id, dia)`*: la consulta pide un día de todo el parque, sin aerogenerador concreto. Con `parque_id`, cuando lleguen más parques cada uno tendrá sus propias particiones y no se mezclarán.
- *Agrupación `data_hora ASC, aeroxerador_id ASC`*: `data_hora` da el orden horario; `aeroxerador_id` hace falta porque dos aerogeneradores pueden dar alarma a la misma hora, y con solo `data_hora` la segunda sobrescribiría a la primera.

```sql
SELECT * FROM alarmas_por_parque_dia WHERE parque_id = 'MB' AND dia = '2026-11-01';
```

**4. `ultima_lectura_por_parque`**
- *Partición `parque_id`*: el panel de control lee los 12 aerogeneradores de una vez, de una partición.
- *Agrupación `aeroxerador_id`*: una fila por aerogenerador que se **sobrescribe** con cada lectura nueva, así que nunca hay más de 12 filas.
- Se escribe con `USING TIMESTAMP` igual a `data_hora` en microsegundos. Cassandra se queda con la escritura de timestamp mayor, así que la fila guarda siempre la lectura más reciente **aunque los días se carguen desordenados** (por ejemplo, si se vuelve a cargar un día antiguo después del día del apartado 4.3.4).

```sql
SELECT * FROM ultima_lectura_por_parque WHERE parque_id = 'MB';
```

### Tamaño de las particiones al cabo de un año

Con 12 aerogeneradores, 144 lecturas por aerogenerador y día y ~1 % de alarmas:

| Tabla | Filas por partición | Particiones nuevas al año | Filas al año | ¿Crece la partición con el tiempo? |
|---|---|---|---|---|
| `lecturas_por_aeroxerador_dia` | 144 | 12 × 365 = 4.380 | 630.720 | No: cada día empieza una nueva |
| `energia_por_aeroxerador_dia` | 144 | 4.380 | 630.720 | No: cada día empieza una nueva |
| `alarmas_por_parque_dia` | ~17 (1 % de 1.728); máx. 1.728 | 365 por parque | ~6.200 | No: cada día empieza una nueva |
| `ultima_lectura_por_parque` | 12 | 1 por parque (siempre la misma) | 12 | No: las filas se sobrescriben |

Ninguna partición pasa de 1.728 filas (unos pocos cientos de KB como mucho), muy por debajo de lo que Cassandra maneja bien (~100 MB por partición). Lo que crece con los años es el **número** de particiones, y eso es justo lo que se reparte entre nodos: al añadir un nodo (4.4), se lleva parte de ellas.

### Del contrato de datos a CQL

| Campo | Contrato | Tipo CQL | Por qué |
|---|---|---|---|
| `aeroxerador_id` | texto, `MB-01`…`MB-12` | `text` | cadena corta; el prefijo identifica el parque |
| `data_hora` | fecha y hora, cada 10 min | `timestamp` | fecha y hora exactas (ms); se guarda en UTC y permite ordenar |
| `vento_ms` | decimal, 1 decimal, 0,0–30,0 | `decimal` | guarda el valor exacto (8.7 es 8.7); con `float` saldría 8.699999… |
| `direccion_graos` | entero, 0–359 | `int` | número entero |
| `potencia_kw` | decimal, 1 decimal, 0,0–3.000,0 | `decimal` | exacto; además `SUM` de la consulta 2 no acumula errores de redondeo |
| `rotor_rpm` | decimal, 1 decimal, 0,0–16,0 | `decimal` | exacto |
| `temp_xerador_c` | decimal, 1 decimal, 10,0–90,0 | `decimal` | exacto |
| `estado` | `ok`, `alarma` o `parado` | `text` | CQL no tiene `enum`; los valores los garantiza el generador, que valida el contrato antes de guardar |

CQL no tiene `NOT NULL` ni `CHECK`: que los campos sean obligatorios y estén en rango lo comprueba el generador (`xera_lecturas.py`), que valida el contrato antes de escribir el CSV. Las columnas de la clave primaria sí son obligatorias: Cassandra rechaza un `INSERT` sin ellas.

### Notas para la carga (issue 4)

- Por cada lectura del CSV: `INSERT` en `lecturas_por_aeroxerador_dia`, `energia_por_aeroxerador_dia` y `ultima_lectura_por_parque` (esta con `USING TIMESTAMP`), y en `alarmas_por_parque_dia` solo si `estado == 'alarma'`.
- Los decimales se pasan como `decimal.Decimal(texto_del_csv)` (no `float`) para que se guarden exactos.
- `data_hora` se trata como UTC: `datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)`; `dia` es su `.date()`; el `USING TIMESTAMP` es `int(data_hora.timestamp() * 1_000_000)`.

## Niveles de consistencia y pruebas de fallo (4.3)

## Crecimiento del clúster (4.4)
