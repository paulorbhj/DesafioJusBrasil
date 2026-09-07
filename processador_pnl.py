import re
import unicodedata
from gliner import GLiNER

# Carrega o modelo multilíngue do GLiNER no topo do arquivo (executado 1x ao importar)
MODELO_GLINER = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")

# Rótulos diretos (modelos Zero-Shot funcionam melhor com frases curtas e objetivas)
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
    """Extrai a numeração processual para consulta FTS no SQLite (Mantido para o resolutor.py)."""
    match = re.search(
        r"(\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}|\d{1,7}(?:\.\d{3})*)", trecho
    )
    if match:
        num = match.group(1)
        return f'"{num}"'
    return ""


def extrair_citacoes_brutas(texto: str) -> list[dict]:
    """Extrai citações analisando o texto em parágrafos sem estourar o limite de tokens do GLiNER."""
    texto_norm = limpar_e_normalizar_texto(texto)
    inicio_corpo = min(identificar_inicio_corpo(texto_norm), 250)

    citacoes = []

    # Iteração por parágrafos/linhas para não truncar o texto e manter os offsets globais
    for match in re.finditer(r"[^\r\n]+", texto_norm):
        bloco = match.group(0)
        offset_bloco = match.start()

        if not bloco.strip():
            continue

        # predict_entities por bloco com threshold de 0.25 para maior sensibilidade
        entidades = MODELO_GLINER.predict_entities(
            bloco, ROTULOS_BUSCA, threshold=0.25
        )

        for ent in entidades:
            start_global = offset_bloco + ent["start"]
            end_global = offset_bloco + ent["end"]

            # Ignora citações localizadas no cabeçalho inicial do documento
            if start_global < inicio_corpo:
                continue

            label = ent["label"]
            trecho_bruto = texto_norm[start_global:end_global]
            trecho_limpo = " ".join(trecho_bruto.split())

            # Categorização do tipo e identificação de citações incompletas
            classificacao_sugerida = None

            if "lei" in label.lower():
                tipo = "lei"
                if any(
                    kw in trecho_limpo.lower()
                    for kw in ["normas", "legislação", "dispositivos", "preceitos"]
                ) and not re.search(r"\d+", trecho_limpo):
                    classificacao_sugerida = "incompleta"
            else:
                tipo = "jurisprudencia"
                if "sem número" in label.lower() or (
                    any(
                        kw in trecho_limpo.lower()
                        for kw in ["julgado do", "acórdão do", "relatoria"]
                    )
                    and not re.search(r"\d+", trecho_limpo)
                ):
                    classificacao_sugerida = "incompleta"

            item = {
                "inicio": start_global,
                "fim": end_global,
                "trecho": trecho_limpo,
                "tipo": tipo,
            }

            if classificacao_sugerida:
                item["classificacao_sugerida"] = classificacao_sugerida

            citacoes.append(item)

    # Ordenação e eliminação de sobreposições contidas
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
    """Orquestra a normalização NFC e dispara a extração de citações via GLiNER."""
    texto_limpo = limpar_e_normalizar_texto(texto)
    return extrair_citacoes_brutas(texto_limpo)