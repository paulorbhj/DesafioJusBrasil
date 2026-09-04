import re
import unicodedata

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
    """Garante normalização Unicode NFC e remove caracteres invisíveis."""
    if not isinstance(texto_bruto, str):
        return ""
    return unicodedata.normalize("NFC", texto_bruto)


def identificar_inicio_corpo(texto: str) -> int:
    """Encontra o offset inicial do corpo do documento para ignorar o cabeçalho."""
    texto_lower = texto.lower()
    posicoes = []
    for pat in MARCADORES_CORPO:
        match = re.search(pat, texto_lower)
        if match:
            posicoes.append(match.start())
    return min(posicoes) if posicoes else 0


def formatar_numero_para_fts(numero_bruto: str) -> str:
    """Reconstrói pontuações de milhar para busca FTS5 (unicode61)."""
    mapa_ocr = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5"})
    numero_limpo = numero_bruto.translate(mapa_ocr)
    digitos = re.sub(r"\D", "", numero_limpo)

    if not digitos:
        return ""

    return f"{int(digitos):,}".replace(",", ".")


def extrair_citacoes_brutas(texto: str) -> list[dict]:
    texto_norm = limpar_e_normalizar_texto(texto)
    inicio_corpo = identificar_inicio_corpo(texto_norm)
    citacoes = []

    # 1. Jurisprudências completas
    padrao_jurisprudencia = (
        r"(?i)\b(?:"
        r"(?:AgRg\s+no\s+|AgInt\s+no\s+|AgInt\s+|no\s+)?(?:REsp|R\.?\s*Esp\.?|Recurso\s+Especial)|"
        r"(?:AREsp|Recurso\s+Especial\s+em\s+Agravo)|"
        r"(?:RHC|Recurso\s+em\s+Habeas\s+Corpus)|"
        r"(?:HC|Habeas\s+Corpus)|"
        r"(?:RSE)|"
        r"(?:Reclamação)|"
        r"(?:5[úu]mula|S[úu]mula)(?:\s+Vinculante)?"
        r")\b(?:\s+(?:nº?|n\.|Nº|No|n))?\s*[\d\.\s\-]+(?:/[A-Z]{2}|\([A-Z]{2}\)|-[A-Z]{2})?"
    )

    # 2. Formato CNJ
    padrao_cnj = r"(?i)\b(?:AgInt\s+)?\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?:/[A-Z]{2})?"

    # 3. Leis e Dispositivos Explícitos
    padrao_leis_explicitas = (
        r"(?i)\b(?:art(?:igo|\.)?)\s+\d+[\w\.\-]*"
        r"(?:\s*,\s*(?:inciso|I|II|III|IV|V|VI|VII|VIII|IX|X|\d+))*"
        r"(?:\s+d[ao]\s+(?:Código\s+Civil|CPC|CC|CLT|CF(?:/88)?|CPP|CPM|CDC|Código\s+Eleitoral|LC\s+64/1990))?"
    )

    # 4. Leis Incompletas / Menções Genéricas (Ex: "normas de regência da matéria")
    padrao_leis_incompletas = (
        r"(?i)\b(?:normas?|legislaçã[õ]es?|diplomas?|ordenamento)\s+de\s+regência(?:\s+da\s+matéria)?"
    )

    # 5. Jurisprudências Incompletas
    padrao_jurisprudencia_incompleta = (
        r"(?i)\b(?:julgado|acórdão|decisão)\s+do\s+(?:STF|STJ|STM|TST|TSE)"
        r"[^,\n.]+?relatoria\s+de\s+[A-Za-z\s]+"
    )

    # Executa as buscas
    for match in re.finditer(padrao_jurisprudencia, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append({"inicio": match.start(), "fim": match.end(), "trecho": match.group().strip(), "tipo": "jurisprudencia"})

    for match in re.finditer(padrao_cnj, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append({"inicio": match.start(), "fim": match.end(), "trecho": match.group().strip(), "tipo": "jurisprudencia"})

    for match in re.finditer(padrao_leis_explicitas, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append({"inicio": match.start(), "fim": match.end(), "trecho": match.group().strip(), "tipo": "lei"})

    for match in re.finditer(padrao_leis_incompletas, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append({
                "inicio": match.start(),
                "fim": match.end(),
                "trecho": match.group().strip(),
                "tipo": "lei",
                "classificacao_sugerida": "incompleta"
            })

    for match in re.finditer(padrao_jurisprudencia_incompleta, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append({
                "inicio": match.start(),
                "fim": match.end(),
                "trecho": match.group().strip(),
                "tipo": "jurisprudencia",
                "classificacao_sugerida": "incompleta"
            })

    # Ordenação e eliminação de sobreposições
    citacoes.sort(key=lambda x: (x["inicio"], -x["fim"]))
    citacoes_unicas = []
    for item in citacoes:
        if not any(c["inicio"] <= item["inicio"] and c["fim"] >= item["fim"] for c in citacoes_unicas):
            citacoes_unicas.append(item)

    citacoes_unicas.sort(key=lambda x: x["inicio"])
    return citacoes_unicas


def processar_pnl(texto: str) -> list[dict]:
    """Orquestra a normalização NFC e dispara a extração de citações."""
    texto_limpo = limpar_e_normalizar_texto(texto)
    return extrair_citacoes_brutas(texto_limpo)