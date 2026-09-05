import sqlite3
from pathlib import Path

DB_PATH = Path("data/desafio1_bracis.db")

def conectar_banco():
    """Retorna uma conexão ativa com o banco SQLite."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Banco de dados não encontrado em: {DB_PATH.resolve()}"
        )
    return sqlite3.connect(DB_PATH)


def testar_conexao() -> tuple[bool, list]:
    """Valida se o banco de dados está acessível e retorna todos os registros."""
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT documento_id FROM documentos")
        registros = cursor.fetchall()
        conn.close()
        return True, registros
    except Exception as e:
        print(f"Erro ao conectar no banco: {e}")
        return False, []


def carregar_normas_memoria() -> dict:
    """Carrega as 18 leis e súmulas em memória para cruzamento direto."""
    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, natureza, tipo, texto FROM documentos WHERE natureza IN ('sumula', 'dispositivo')"
    )
    registros = cursor.fetchall()
    conn.close()

    normas = {}
    for doc_id, natureza, tipo, texto in registros:
        normas[doc_id] = {
            "id_canonico": doc_id,
            "natureza": natureza,
            "tipo": tipo,
            "texto_integral": texto,
        }
    return normas


def buscar_acordao_fts(numero_formatado: str) -> list[tuple]:
    """Consulta o índice FTS5 por frase exata para acórdãos."""
    conn = conectar_banco()
    cursor = conn.cursor()

    query = """
        SELECT d.documento_id, d.id, d.tribunal, d.ano, d.tipo, d.texto
        FROM documentos_fts JOIN documentos d ON d.rowid = documentos_fts.rowid
        WHERE d.natureza = 'acordao' AND documentos_fts MATCH ?
    """
    cursor.execute(query, (numero_formatado,))
    resultados = cursor.fetchall()
    conn.close()

    return resultados

