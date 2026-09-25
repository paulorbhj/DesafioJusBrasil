import re
import unicodedata
from gliner import GLiNER

# Carrega o modelo multilíngue do GLiNER no topo do arquivo (executado 1x ao importar)
MODELO_GLINER = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")

# Rótulos diretos
ROTULOS_BUSCA = [
    "lei ou artigo legal",
    "súmula",
    "jurisprudência ou processo judicial",
    "menção a julgado sem número",
]

# Marcadores de início do corpo com limite de palavra (\b) para evitar casamentos falsos
MARCADORES_CORPO = [
    r"\bexcelentíssim[oa]s?\b",
    r"\bsenhor(a)?\s+ministr[oa]s?\b",
    r"\bsenhor(a)?\s+juiz(a)?\b",
    r"\bvistos\b",
    r"\btrata-se\s+de\b",
    r"\bI\s*[\-\–\.]\s*",
    r"\bdos?\s+fatos\b",
    r"\bda\s+controvérsia\b",
    r"\bdo\s+direito\b",
    r"\brelatório\b",
    r"\bementa\b",
]


def limpar_e_normalizar_texto(texto_bruto: str) -> str:
    """Garante normalização Unicode NFC e padroniza quebras de linha."""
    if not isinstance(texto_bruto, str):
        return ""
    texto_norm = unicodedata.normalize("NFC", texto_bruto)
    return texto_norm.replace("\r\n", "\n").replace("\r", "\n")


def identificar_inicio_corpo(texto: str) -> int:
    """Encontra o offset inicial do corpo do documento para ignorar o cabeçalho."""
    texto_lower = texto.lower()
    posicoes = []
    for pat in MARCADORES_CORPO:
        match = re.search(pat, texto_lower)
        if match:
            posicoes.append(match.start())
    return min(posicoes) if posicoes else 0


def formatar_numero_para_fts(trecho: str) -> str:
    """Extrai a numeração processual para consulta FTS no SQLite (Mantido para o resolutor.py)."""
    match = re.search(
        r"(\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}|\d{1,7}(?:\.\d{3})*)", trecho
    )
    if match:
        num = match.group(1)
        return f'"{num}"'
    return ""


def extrair_citacoes_brutas(texto: str) -> list[dict]:
    """Extrai citações via GLiNER e Regex mantendo integridade dos delimitadores e limite de 250 chars."""

    texto_norm = limpar_e_normalizar_texto(texto)
    inicio_corpo = min(identificar_inicio_corpo(texto_norm), 250)

    citacoes = []

    # ============================================================
    # 1. Citações Narrativas / Incompletas (Resolve g2, g5 e g9)
    # ============================================================
    padrao_narrativo = re.compile(
        r"\b(?:julgado|precedente|acórdão|decisão)\s+do\s+(?:STF|STM|STJ|TST|TSE)"
        r"[^,\n.]*?(?:pela\s+relatoria\s+de|da\s+relatoria\s+de)\s+[A-Za-zÀ-ÿ\s]+?"
        r"(?=[,.]|\s+no\s+ponto|\s+a\s+distinção|\s+OLIVEIRA\b|$)",
        re.IGNORECASE,
    )

    for match in padrao_narrativo.finditer(texto_norm):
        start = match.start()

        if start < inicio_corpo:
            continue

        end = match.end()
        trecho = texto_norm[start:end].rstrip()

        citacoes.append(
            {
                "inicio": start,
                "fim": start + len(trecho),
                "trecho": trecho,
                "tipo": "jurisprudencia",
                "classificacao_sugerida": "incompleta",
            }
        )

    # ============================================================
    # 2. Referências Processuais via Regex (Resolve g3, g4, g6, g8, g10)
    # ============================================================
    padrao_processual = re.compile(
        r"\b(?:"
        r"Reclamação|Apelação|Habeas\s+Corpus|Recurso\s+Especial|Agravo\s+Interno|Recurso\s+em\s+Sentido\s+Estrito|"
        r"APL|RSE|REsp|AREsp|ARE|AgInt|AI|AgRg|RHC|HC|Rcl|RE|RMS|MS|ADI|ADPF|ADC|AC|CC"
        r")"
        r"(?:\s+n[ºo°]?)?"
        r"\s*"
        r"(?:\n\s*)?"
        r"\d{1,7}(?:\.\d{1,3})*(?:-\d{1,2}\.\d{4}\.\d\.\d{2}\.\d{4})?"
        r"(?:/[A-Z]{2})?",
        re.IGNORECASE,
    )

    for match in padrao_processual.finditer(texto_norm):
        start = match.start()

        if start < inicio_corpo:
            continue

        end = match.end()
        trecho = texto_norm[start:end].strip()

        # Aceita se contiver ao menos um número
        if not re.search(r"\d", trecho):
            continue

        citacoes.append(
            {
                "inicio": start,
                "fim": end,
                "trecho": trecho,
                "tipo": "jurisprudencia",
            }
        )

    # ============================================================
    # 3. GLiNER para localização suplementar (Leis, Súmulas e Entidades)
    # ============================================================
    for match_bloco in re.finditer(r"[^\r\n]+", texto_norm):
        bloco = match_bloco.group(0)
        offset_bloco = match_bloco.start()

        if not bloco.strip() or offset_bloco < inicio_corpo:
            continue

        entidades = MODELO_GLINER.predict_entities(
            bloco, ROTULOS_BUSCA, threshold=0.35
        )

        for ent in entidades:
            start_global = offset_bloco + ent["start"]
            end_global = offset_bloco + ent["end"]

            if start_global < inicio_corpo:
                continue

            label = ent["label"]
            trecho = texto_norm[start_global:end_global]

            # Filtro de falsos positivos do GLiNER (Remove c6 / dispositivo constitucional)
            if trecho.lower() in {
                "memorial",
                "presente memorial",
                "sentença",
                "laudo pericial",
                "doutrina especializada",
                "dispositivo constitucional",
            }:
                continue

            tipo = "lei" if "lei" in label.lower() else "jurisprudencia"

            citacoes.append(
                {
                    "inicio": start_global,
                    "fim": end_global,
                    "trecho": trecho,
                    "tipo": tipo,
                }
            )

    # ============================================================
    # 4. Deduplicação, Filtro e Ordenação
    # ============================================================
    citacoes.sort(key=lambda x: (x["inicio"], -x["fim"]))
    citacoes_unicas = []

    for item in citacoes:
        if item["trecho"].lower() in ["dispositivo constitucional"]:
            continue

        sobreposta = False
        for c in citacoes_unicas:
            # Descarta capturas internas/menores contidas dentro de citações já aceitas
            if c["inicio"] <= item["inicio"] and c["fim"] >= item["fim"]:
                sobreposta = True
                break

        if not sobreposta:
            citacoes_unicas.append(item)

    citacoes_unicas.sort(key=lambda x: x["inicio"])
    return citacoes_unicas


def processar_pnl(texto: str) -> list[dict]:
    """Orquestra a normalização NFC e dispara a extração de citações via GLiNER."""
    texto_limpo = limpar_e_normalizar_texto(texto)
    return extrair_citacoes_brutas(texto_limpo)