import os
from datetime import datetime
import oracledb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TIPOS_ALERTA_VALIDOS = {
    "PH_CRITICO", "PH_ALTO", "PH_BAIXO",
    "TEMPERATURA_ALTA", "TEMPERATURA_BAIXA",
    "TURBIDEZ_FORA_PADRAO", "LUMINOSIDADE_BAIXA",
}
SEVERIDADES_VALIDAS = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}


def get_conexao():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER", "system"),
        password=os.getenv("ORACLE_PASSWORD", "oracle"),
        dsn=os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1"),
    )


def salvar_previsao(
    tanque_id: int,
    id_dado_orbital: int,
    biomassa: float,
    data_pico,
    confianca: float,
    modelo: str = "RandomForest_v1",
) -> None:
    if biomassa <= 0:
        raise ValueError(f"biomassa deve ser > 0, recebido: {biomassa}")
    if not (0 <= confianca <= 100):
        raise ValueError(f"confianca deve estar entre 0 e 100, recebido: {confianca}")

    sql = """
        INSERT INTO TB_PREVISOES_IA
            (id_previsao, id_tanque, id_dado_orbital, dt_previsao,
             biomassa_g_l, dt_pico_previsto, confianca_pct, modelo_utilizado)
        VALUES
            (SQ_PREVISOES_IA.NEXTVAL, :tanque_id, :id_dado_orbital,
             :dt_previsao, :biomassa, :data_pico, :confianca, :modelo)
    """
    try:
        with get_conexao() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, {
                    "tanque_id":       tanque_id,
                    "id_dado_orbital": id_dado_orbital,
                    "dt_previsao":     datetime.now(),
                    "biomassa":        round(biomassa, 4),
                    "data_pico":       data_pico,
                    "confianca":       round(confianca, 2),
                    "modelo":          modelo,
                })
            conn.commit()
    except Exception as e:
        print(f"rro ao salvar previsão: {e}")


def salvar_alerta(
    tanque_id: int,
    id_metrica: int,
    tipo_alerta: str,
    mensagem: str,
    severidade: str = "ALTA",
) -> None:
    tipo_alerta = tipo_alerta.upper()
    severidade = severidade.upper()

    if tipo_alerta not in TIPOS_ALERTA_VALIDOS:
        print(f"ipo_alerta inválido '{tipo_alerta}'. Válidos: {TIPOS_ALERTA_VALIDOS}")
        return
    if severidade not in SEVERIDADES_VALIDAS:
        print(f"everidade inválida '{severidade}'. Válidas: {SEVERIDADES_VALIDAS}")
        return

    sql = """
        INSERT INTO TB_ALERTA_CRITICO
            (id_alerta, id_metrica, id_tanque, tipo_alerta,
             severidade, mensagem, status, dt_alerta)
        VALUES
            (SQ_ALERTA_CRITICO.NEXTVAL, :id_metrica, :tanque_id, :tipo_alerta,
             :severidade, :mensagem, 'ABERTO', CURRENT_TIMESTAMP)
    """
    try:
        with get_conexao() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, {
                    "id_metrica":  id_metrica,
                    "tanque_id":   tanque_id,
                    "tipo_alerta": tipo_alerta,
                    "severidade":  severidade,
                    "mensagem":    mensagem[:500],
                })
            conn.commit()
    except Exception as e:
        print(f"rro ao salvar alerta: {e}")


def carregar_dados_treino() -> pd.DataFrame:
    query = """
        SELECT
            m.ph,
            m.temperatura,
            m.turbidez,
            m.luminosidade,
            d.irradiancia_par   AS "radiacaoPar",
            p.biomassa_g_l      AS "biomassa"
        FROM
            TB_METRICAS_TANQUE  m
            JOIN TB_TANQUE       t  ON t.id_tanque    = m.id_tanque
            JOIN TB_DADO_ORBITAL d  ON d.id_fazenda   = t.id_fazenda
                                    AND d.dt_coleta BETWEEN
                                        TRUNC(CAST(m.dt_leitura AS DATE)) - 1
                                        AND TRUNC(CAST(m.dt_leitura AS DATE)) + 1
            JOIN TB_PREVISOES_IA p  ON p.id_tanque        = m.id_tanque
                                    AND p.id_dado_orbital  = d.id_dado_orbital
        WHERE
            m.ph               IS NOT NULL
            AND m.temperatura   IS NOT NULL
            AND m.turbidez      IS NOT NULL
            AND m.luminosidade  IS NOT NULL
            AND d.irradiancia_par IS NOT NULL
            AND p.biomassa_g_l  IS NOT NULL
            AND p.biomassa_g_l  > 0
        ORDER BY
            m.dt_leitura
    """
    try:
        with get_conexao() as conn:
            df = pd.read_sql(query, con=conn)
        print(f"🗄️  Oracle: {len(df)} registros carregados para treino")
        return df
    except Exception as e:
        print(f"Erro ao carregar dados de treino: {e}")
        raise


def contar_registros_novos(desde: datetime) -> int:
    query = """
        SELECT COUNT(*) AS total
        FROM TB_METRICAS_TANQUE
        WHERE dt_leitura > :desde
    """
    try:
        with get_conexao() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, {"desde": desde})
                row = cursor.fetchone()
                return int(row[0]) if row else 0
    except Exception as e:
        print(f"rro ao contar registros novos: {e}")
        return 0


def buscar_ultimo_dado_orbital(tanque_id: int) -> int | None:
    query = """
        SELECT d.id_dado_orbital
        FROM TB_DADO_ORBITAL d
        JOIN TB_TANQUE t ON t.id_fazenda = d.id_fazenda
        WHERE t.id_tanque = :tanque_id
        ORDER BY d.dt_coleta DESC
        FETCH FIRST 1 ROWS ONLY
    """
    try:
        with get_conexao() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, {"tanque_id": tanque_id})
                row = cursor.fetchone()
                return int(row[0]) if row else None
    except Exception as e:
        print(f"rro ao buscar dado orbital: {e}")
        return None
