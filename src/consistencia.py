"""
Niveles de consistencia de cada operación (apartado 4.3.2).

El keyspace tiene 3 réplicas (RF = 3), así que:
    ONE    -> responde 1 réplica
    QUORUM -> responden 2 réplicas (3 // 2 + 1)
    ALL    -> responden las 3 réplicas

Escribir y leer con QUORUM cumple  W + R > RF  (2 + 2 > 3): toda lectura
coincide al menos en una réplica con la última escritura confirmada, así que
siempre se lee el dato más reciente. Y con un nodo parado sigue funcionando
(quedan 2 réplicas, que son las que pide QUORUM).

La justificación completa está en el README, sección 4.3.
"""

from cassandra import ConsistencyLevel

# Lecturas del SCADA (tablas lecturas, energía y última lectura)
ESCRIBIR_LECTURAS = ConsistencyLevel.QUORUM
LEER_LECTURAS = ConsistencyLevel.QUORUM

# Alarmas (tabla alarmas_por_parque_dia)
ESCRIBIR_ALARMAS = ConsistencyLevel.QUORUM
LEER_ALARMAS = ConsistencyLevel.QUORUM
