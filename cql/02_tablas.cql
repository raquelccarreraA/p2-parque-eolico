-- Modelo de datos del parque eólico: una tabla por consulta (apartado 4.1).
-- Ejecutar después de 01_keyspace.cql:
--   docker exec -i cass1 cqlsh < cql/02_tablas.cql
--
-- Columnas derivadas que calcula carga.py a partir de cada lectura del CSV:
--   dia       = fecha de data_hora                    (data_hora[:10] -> '2026-11-01')
--   parque_id = prefijo de aeroxerador_id             ('MB-07' -> 'MB')

USE parque;

-- ---------------------------------------------------------------------------
-- Consulta 1: lecturas de un aerogenerador en un día, de la más reciente a la
-- más antigua.
--   Partición:  (aeroxerador_id, dia)  -> todas las lecturas pedidas juntas
--   Agrupación: data_hora DESC         -> ya salen ordenadas como se piden
--   Filas por partición: 144 (fijo). Por año: 12 x 365 = 4.380 particiones.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lecturas_por_aeroxerador_dia (
    aeroxerador_id  text,
    dia             date,
    data_hora       timestamp,
    vento_ms        decimal,
    direccion_graos int,
    potencia_kw     decimal,
    rotor_rpm       decimal,
    temp_xerador_c  decimal,
    estado          text,
    PRIMARY KEY ((aeroxerador_id, dia), data_hora)
) WITH CLUSTERING ORDER BY (data_hora DESC);

-- ---------------------------------------------------------------------------
-- Consulta 2: energía producida por un aerogenerador en un día.
--   energía (kWh) = SUM(potencia_kw) x 10/60 h
--   Solo guarda la potencia de cada intervalo de 10 minutos; Cassandra suma
--   una única partición con SUM(). Cada lectura es un upsert por data_hora,
--   así que volver a cargar el mismo CSV no duplica la energía.
--   Partición:  (aeroxerador_id, dia)
--   Agrupación: data_hora              -> una fila por intervalo, sin repetidos
--   Filas por partición: 144 (fijo). Por año: 4.380 particiones.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS energia_por_aeroxerador_dia (
    aeroxerador_id  text,
    dia             date,
    data_hora       timestamp,
    potencia_kw     decimal,
    PRIMARY KEY ((aeroxerador_id, dia), data_hora)
);

-- ---------------------------------------------------------------------------
-- Consulta 3: alarmas de un día en todo el parque, en orden horario.
--   Solo se insertan las lecturas con estado = 'alarma'.
--   Partición:  (parque_id, dia)               -> un día de un parque
--   Agrupación: data_hora ASC, aeroxerador_id  -> orden horario; el id
--               distingue dos alarmas a la misma hora en aerogeneradores
--               distintos (si no, una pisaría a la otra)
--   Filas por partición: ~17 esperadas (1 % de 1.728), 1.728 como máximo.
--   Por año: 365 particiones por parque.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alarmas_por_parque_dia (
    parque_id       text,
    dia             date,
    data_hora       timestamp,
    aeroxerador_id  text,
    vento_ms        decimal,
    direccion_graos int,
    potencia_kw     decimal,
    rotor_rpm       decimal,
    temp_xerador_c  decimal,
    estado          text,
    PRIMARY KEY ((parque_id, dia), data_hora, aeroxerador_id)
) WITH CLUSTERING ORDER BY (data_hora ASC, aeroxerador_id ASC);

-- ---------------------------------------------------------------------------
-- Consulta 4: última lectura de cada aerogenerador del parque (panel).
--   Partición:  parque_id       -> todo el panel en una sola lectura
--   Agrupación: aeroxerador_id  -> una fila por aerogenerador, se sobrescribe
--   Filas por partición: 12 (fijo), da igual cuántos años pasen.
--   carga.py escribe con USING TIMESTAMP = data_hora (en microsegundos):
--   así gana siempre la lectura más reciente aunque se carguen días antiguos
--   después de días nuevos.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ultima_lectura_por_parque (
    parque_id       text,
    aeroxerador_id  text,
    data_hora       timestamp,
    vento_ms        decimal,
    direccion_graos int,
    potencia_kw     decimal,
    rotor_rpm       decimal,
    temp_xerador_c  decimal,
    estado          text,
    PRIMARY KEY ((parque_id), aeroxerador_id)
);
