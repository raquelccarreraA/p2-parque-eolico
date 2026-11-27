# Sentencias de insercion para carga.py

INSERTAR_LECTURA = """
    INSERT INTO lecturas_por_aeroxerador_dia (
        aeroxerador_id, dia, data_hora, vento_ms, direccion_graos,
        potencia_kw, rotor_rpm, temp_xerador_c, estado
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERTAR_ENERGIA = """
    INSERT INTO energia_por_aeroxerador_dia (
        aeroxerador_id, dia, data_hora, potencia_kw
    ) VALUES (?, ?, ?, ?)
"""

INSERTAR_ALARMA = """
    INSERT INTO alarmas_por_parque_dia (
        parque_id, dia, data_hora, aeroxerador_id, vento_ms,
        direccion_graos, potencia_kw, rotor_rpm, temp_xerador_c, estado
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERTAR_ULTIMA_LECTURA = """
    INSERT INTO ultima_lectura_por_parque (
        parque_id, aeroxerador_id, data_hora, vento_ms, direccion_graos,
        potencia_kw, rotor_rpm, temp_xerador_c, estado
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    USING TIMESTAMP ?
"""


# Sentencias de consulta para consultas.py

CONSULTAR_LECTURAS_DIA = """
    SELECT data_hora, vento_ms, direccion_graos, potencia_kw,
           rotor_rpm, temp_xerador_c, estado
    FROM lecturas_por_aeroxerador_dia
    WHERE aeroxerador_id = %s AND dia = %s
"""

CONSULTAR_LECTURAS_DIA_CON_LIMITE = """
    SELECT data_hora, vento_ms, direccion_graos, potencia_kw,
           rotor_rpm, temp_xerador_c, estado
    FROM lecturas_por_aeroxerador_dia
    WHERE aeroxerador_id = %s AND dia = %s
    LIMIT %s
"""

CONSULTAR_ENERGIA_DIA = """
    SELECT SUM(potencia_kw) AS suma_potencia
    FROM energia_por_aeroxerador_dia
    WHERE aeroxerador_id = %s AND dia = %s
"""

CONSULTAR_ALARMAS_PARQUE = """
    SELECT data_hora, aeroxerador_id, vento_ms, potencia_kw, temp_xerador_c
    FROM alarmas_por_parque_dia
    WHERE parque_id = %s AND dia = %s
"""

CONSULTAR_ULTIMA_LECTURA = """
    SELECT aeroxerador_id, data_hora, vento_ms, potencia_kw, temp_xerador_c, estado
    FROM ultima_lectura_por_parque
    WHERE parque_id = %s
"""