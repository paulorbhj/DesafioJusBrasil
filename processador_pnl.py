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


def formatar_numero_para_fts(trecho: str) -> str:
    match = re.search(r"(\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})", trecho)
    if match:
        cnj = match.group(1)
        # Garante aspas duplas em volta do CNJ
        return f'"{cnj}"'
    return ""


def extrair_citacoes_brutas(texto: str) -> list[dict]:
    texto_norm = limpar_e_normalizar_texto(texto)
    inicio_corpo = min(identificar_inicio_corpo(texto_norm), 250)
    citacoes = []

    # Captura classes processuais simples ou compostas seguidas de número e UF/CNJ
    # Inclui preposições "no", "nos", "na", "nas" para suportar recursos como "AgInt no AREsp"
    padrao_jurisprudencia_com_classe = (
        r"\b[A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý]{0,15}"
        r"(?:[\s\n]+(?:em|de|do|da|dos|das|no|nos|na|nas|e|[A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý]{0,15})){0,4}"
        r"(?:\s+[Vv]inculante)?"
        r"(?:[\s\n]+(?:[nN]º?|[nN]\.|[nN]o))?[\s\n]*"
        r"(?:\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?:/[A-Z]{2})?|[\d\.\s\-]{3,15}(?:/[A-Z]{2}|\([A-Z]{2}\)|-[A-Z]{2}))"
    )

    # CNJ isolado sem prefixo de classe
    padrao_cnj_isolado = (
        r"(?i)\b\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?:/[A-Z]{2})?"
    )

    # Leis e Dispositivos Explícitos
    padrao_leis_explicitas = (
        r"(?i)\b(?:art(?:igo|\.)?)\s+\d+[\w\.\-]*"
        r"(?:\s*,\s*(?:inciso|I|II|III|IV|V|VI|VII|VIII|IX|X|\d+))*"
        r"(?:\s+d[ao]\s+(?:Código\s+Civil|CPC|CC|CLT|CF(?:/88)?|CPP|CPM|CDC|Código\s+Eleitoral|LC\s+64/1990))?"
    )

    # Leis Incompletas e Menções Genéricas
    padrao_leis_incompletas = (
        r"(?i)\b(?:"
        r"(?:normas?|legislação|legislações|diplomas?|ordenamentos?)\s+de\s+regência(?:\s+da\s+matéria)?|"
        r"(?:dispositivos?|normas?|preceitos?|artigos?|textos?|disposição|disposições|diplomas?)\s+"
        r"(?:constitucionais|constitucional|infraconstitucionais|infraconstitucional|legais|legal|normatizadores|normatizador)"
        r"(?:\s+invocados?|\s+invocadas?|\s+invocado)?"
        r"(?:\s+na\s+origem)?"
        r")\b"
    )

    # Permite quebras de linha intermediárias (\s+), mas limita a busca do nome para não engolir o texto seguinte
    padrao_jurisprudencia_incompleta = (
        r"(?i)\b(?:julgado|acórdão|decisão|precedente|reclamação|habeas\s+corpus|súmula|agravo|recurso|Rcl|HC|MS)s?[\s\n]+"
        r"d[eo][\s\n]+(?:STF|STJ|STM|TST|TSE|TJ[A-Z]{2}|TRF\d+)"
        r"(?:[\s\n]*,?[\s\n]*(?:de[\s\n]+\d{4}|proferid[oa][\s\n]+em[\s\n]+\d{4}))?"
        r"(?:[\s\n]*,?[\s\n]*(?:(?:d[ao]|sob\s+a|pel[ao])[\s\n]+relatoria[\s\n]+d[eo]|Rel(?:\.|ator(?:a)?)?[\s\n]*(?:d[eo])?))"
        r"[\s\n]*(?:Min(?:istro|\.)?[\s\n]+|Des(?:embargador|\.)?[\s\n]+|Juiz(?:a)?[\s\n]+)*"
        r"([A-ZÀ-ÿ][A-Za-zÀ-ÿ]+(?:[\s\n]+(?:de|da|do|dos|das)?[\s\n]*[A-ZÀ-ÿ][A-Za-zÀ-ÿ]+){1,3})"
    )

    for match in re.finditer(padrao_jurisprudencia_com_classe, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append(
                {
                    "inicio": match.start(),
                    "fim": match.end(),
                    "trecho": " ".join(match.group().split()),
                    "tipo": "jurisprudencia",
                }
            )

    for match in re.finditer(padrao_cnj_isolado, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append(
                {
                    "inicio": match.start(),
                    "fim": match.end(),
                    "trecho": " ".join(match.group().split()),
                    "tipo": "jurisprudencia",
                }
            )

    for match in re.finditer(padrao_leis_explicitas, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append(
                {
                    "inicio": match.start(),
                    "fim": match.end(),
                    "trecho": " ".join(match.group().split()),
                    "tipo": "lei",
                }
            )

    for match in re.finditer(padrao_leis_incompletas, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append(
                {
                    "inicio": match.start(),
                    "fim": match.end(),
                    "trecho": " ".join(match.group().split()),
                    "tipo": "lei",
                    "classificacao_sugerida": "incompleta",
                }
            )

    for match in re.finditer(padrao_jurisprudencia_incompleta, texto_norm):
        if match.start() >= inicio_corpo:
            citacoes.append(
                {
                    "inicio": match.start(),
                    "fim": match.end(),
                    "trecho": " ".join(match.group().split()),
                    "tipo": "jurisprudencia",
                    "classificacao_sugerida": "incompleta",
                }
            )

    # Ordenação e eliminação de sobreposições (prioriza o match mais longo)
    citacoes.sort(key=lambda x: (x["inicio"], -x["fim"]))
    citacoes_unicas = []
    for item in citacoes:
        if not any(
            c["inicio"] <= item["inicio"] and c["fim"] >= item["fim"]
            for c in citacoes_unicas
        ):
            citacoes_unicas.append(item)

    citacoes_unicas.sort(key=lambda x: x["inicio"])
    return citacoes_unicas


def processar_pnl(texto: str) -> list[dict]:
    """Orquestra a normalização NFC e dispara a extração de citações."""
    texto_limpo = limpar_e_normalizar_texto(texto)
    return extrair_citacoes_brutas(texto_limpo)