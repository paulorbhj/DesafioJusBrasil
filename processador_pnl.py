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


#correção
def extrair_citacoes_brutas(texto: str) -> list[dict]:
    """Extrai citações via GLiNER e preserva referências processuais completas."""

    texto_norm = limpar_e_normalizar_texto(texto)
    inicio_corpo = min(identificar_inicio_corpo(texto_norm), 250)

    citacoes = []

    # ============================================================
    # 1. GLiNER continua sendo usado para localizar citações
    # ============================================================

    for match in re.finditer(r"[^\r\n]+", texto_norm):

        bloco = match.group(0)
        offset_bloco = match.start()

        if not bloco.strip():
            continue

        entidades = MODELO_GLINER.predict_entities(
            bloco,
            ROTULOS_BUSCA,
            threshold=0.25
        )


        for ent in entidades:
            start_global = offset_bloco + ent["start"]
            end_global = offset_bloco + ent["end"]

            if start_global < inicio_corpo:
                continue

            label = ent["label"]
            trecho_bruto = texto_norm[start_global:end_global]

            # Amplia citações genéricas de jurisprudência para capturar
            # informações de ano e relatoria que fazem parte da mesma referência.
            if (
                "julgado do" in trecho_bruto.lower()
                and re.search(r"\b(?:STF|STM|STJ|TST|TSE)\b", trecho_bruto)
            ):
                fim_ampliado = start_global

                padrao_ampliacao = re.compile(
                    r".{0,120}?"
                    r"(?:proferido|da relatoria|pela relatoria|relatoria)"
                    r".{0,120}",
                    re.IGNORECASE | re.DOTALL
                )

                trecho_restante = texto_norm[start_global:start_global + 250]
                candidatos = list(padrao_ampliacao.finditer(trecho_restante))

                if candidatos:
                    ultimo = candidatos[-1]
                    fim_ampliado = start_global + ultimo.end()

                    # Não ultrapassa uma nova frase.
                    trecho_ampliado = texto_norm[start_global:fim_ampliado]
                    ponto = re.search(r"[.!?](?:\s|$)", trecho_ampliado)

                    if ponto:
                        fim_ampliado = start_global + ponto.start()

                    end_global = fim_ampliado

            trecho_limpo = " ".join(
                texto_norm[start_global:end_global].split()
            )

            # Remove falsos positivos evidentes do GLiNER
            if trecho_limpo.lower() in {
                "memorial",
                "presente memorial",
                "sentença",
                "laudo pericial",
                "doutrina especializada",
            }:
                continue

            classificacao_sugerida = None

            if "lei" in label.lower():
                tipo = "lei"

                if (
                    any(
                        kw in trecho_limpo.lower()
                        for kw in [
                            "normas",
                            "legislação",
                            "dispositivos",
                            "preceitos"
                        ]
                    )
                    and not re.search(r"\d+", trecho_limpo)
                ):
                    classificacao_sugerida = "incompleta"

            else:
                tipo = "jurisprudencia"

                if (
                    "sem número" in label.lower()
                    or (
                        any(
                            kw in trecho_limpo.lower()
                            for kw in [
                                "julgado do",
                                "acórdão do",
                                "relatoria"
                            ]
                        )
                        and not re.search(r"\d+", trecho_limpo)
                    )
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
    # ============================================================
    # 2. CORREÇÃO:
    #    procura referências processuais completas diretamente
    #    no texto original.
    #
    #    Isso evita que GLiNER separe:
    #
    #       APL
    #       7000449-40
    #
    #    em duas citações.
    # ============================================================

    padrao_processual = re.compile(
        r"\b(?:"
        r"APL|"
        r"RSE|"
        r"REsp|"
        r"AREsp|"
        r"AgInt|"
        r"AgRg|"
        r"RHC|"
        r"HC|"
        r"Rcl|"
        r"RE|"
        r"MS|"
        r"ADI|"
        r"ADPF|"
        r"ADC|"
        r"AC"
        r")"
        r"(?:\s+nos?|\s+na|\s+no)?"
        r"(?:\s+EDcl)?"
        r"(?:\s+em\s+)?"
        r"(?:\s+Recurso\s+Especial)?"
        r"(?:\s+Habeas\s+Corpus)?"
        r"(?:\s+n[ºo°]?)?"
        r"\s*"
        r"\d{1,7}(?:\.\d{1,3})?"
        r"(?:-\d{1,2}\.\d{4}\.\d\.\d{2}\.\d{4})?"
        r"(?:/[A-Z]{2})?"
    )

    citacoes_processuais = []

    for match in padrao_processual.finditer(texto_norm):

        start_global = match.start()
        end_global = match.end()

        if start_global < inicio_corpo:
            continue

        trecho = " ".join(
            texto_norm[start_global:end_global].split()
        )

        # Só aceita como referência processual quando existe
        # uma numeração suficientemente característica.
        if not re.search(
            r"\d{1,7}(?:\.\d{1,3})?(?:-\d{1,2}\.\d{4}\.\d\.\d{2}\.\d{4})?",
            trecho
        ):
            continue

        citacoes_processuais.append(
            {
                "inicio": start_global,
                "fim": end_global,
                "trecho": trecho,
                "tipo": "jurisprudencia",
            }
        )

    # ============================================================
    # 3. Substitui entidades fragmentadas do GLiNER pelas
    #    referências processuais completas.
    # ============================================================

    for proc in citacoes_processuais:

        citacoes = [
            c
            for c in citacoes
            if not (
                c["inicio"] >= proc["inicio"]
                and c["fim"] <= proc["fim"]
            )
        ]

        citacoes.append(proc)

    # ============================================================
    # 4. Remove sobreposições
    # ============================================================

    citacoes.sort(
        key=lambda x: (x["inicio"], -x["fim"])
    )

    citacoes_unicas = []

    for item in citacoes:

        sobreposta = False

        for c in citacoes_unicas:

            if (
                c["inicio"] <= item["inicio"]
                and c["fim"] >= item["fim"]
            ):
                sobreposta = True
                break

        if not sobreposta:
            citacoes_unicas.append(item)

    citacoes_unicas.sort(
        key=lambda x: x["inicio"]
    )

    return citacoes_unicas


def processar_pnl(texto: str) -> list[dict]:
    """Orquestra a normalização NFC e dispara a extração de citações via GLiNER."""
    texto_limpo = limpar_e_normalizar_texto(texto)
    return extrair_citacoes_brutas(texto_limpo)