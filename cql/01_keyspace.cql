-- Keyspace del parque eólico: 3 réplicas en el datacenter dc1
-- (el nombre debe coincidir con CASSANDRA_DC de compose.yaml).
CREATE KEYSPACE IF NOT EXISTS parque
  WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3}
  AND durable_writes = true;
