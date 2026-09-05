import re
from conexao_banco import buscar_acordao_fts, carregar_normas_memoria
from processador_pnl import formatar_numero_para_fts, processar_pnl

# Mapeamento de siglas para nomes por extenso das classes processuais
CLASSES_MAPEAMENTO = {
    "RSE": ["RSE", "RECURSO EM SENTIDO ESTRITO"],
    "APL": ["APL", "APELAÇÃO", "APELACAO"],
    "AC": ["AC", "APELAÇÃO CÍVEL", "APELACAO CIVEL"],
    "AGINT": ["AGINT", "AGRAVO INTERNO"],
    "AI": ["AI", "AGRAVO DE INSTRUMENTO"],
    "HC": ["HC", "HABEAS CORPUS"],
    "MS": ["MS", "MANDADO DE SEGURANÇA", "MANDADO DE SEGURANCA"],
    "RE": ["RE", "RECURSO EXTRAORDINÁRIO", "RECURSO EXTRAORDINARIO"],
    "RESP": ["RESP", "RECURSO ESPECIAL"],
}


def calcular_confianca(
    trecho: str,
    classificacao: str,
    tipo: str,
    match_exato: bool = False,
    teve_ocr: bool = False,
) -> float:
    """Calcula dinamicamente o score de confiança (0.00 a 1.00) combinando a

    integridade do formato extraído com a validação da base canônica.
    """
    if classificacao == "real":
        # Se houve necessidade de correção de OCR no trecho, penaliza levemente a confiança
        return 0.88 if teve_ocr else 0.98

    if classificacao == "inventada":
        # Formato CNJ perfeito que NÃO existe na base canônica -> alta probabilidade de ser forjada
        padrao_cnj_estrito = (
            r"^\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?:/[A-Z]{2})?$"
        )
        if re.search(padrao_cnj_estrito, trecho.strip()):
            return 0.95
        return 0.80

    if classificacao == "incompleta":
        # Expressões padrão de omissão identificadas via PNL
        if any(
            p in trecho.lower()
            for p in ["julgado do", "acórdão do", "decisão do"]
        ):
            return 0.90
        return 0.75

    return 0.50


def resolver_citacoes(
    texto: str, documento_id: str = "doc_0000"
) -> dict:
    """Orquestra a extração, cruzamento canônico e cálculo de confiança."""
    citacoes_brutas = processar_pnl(texto)
    normas_memoria = carregar_normas_memoria()
    lista_citacoes = []

    for idx, cit in enumerate(citacoes_brutas, 1):
        cit_id = f"c{idx}"
        trecho = cit["trecho"]
        tipo = cit["tipo"]
        inicio = cit["inicio"]
        fim = cit["fim"]

        # 1. Citações Incompletas
        if cit.get("classificacao_sugerida") == "incompleta":
            conf = calcular_confianca(trecho, "incompleta", tipo)
            lista_citacoes.append(
                {
                    "id": cit_id,
                    "inicio": inicio,
                    "fim": fim,
                    "trecho": trecho,
                    "tipo": tipo,
                    "classificacao": "incompleta",
                    "resolucao": None,
                    "confianca": conf,
                }
            )
            continue

        # 2. Leis e Súmulas (Consulta em Memória)
        if tipo == "lei" or "súmula" in trecho.lower():
            doc_id_encontrado = None
            for doc_id, dados in normas_memoria.items():
                if (
                    dados["texto_integral"].lower() in trecho.lower()
                    or trecho.lower() in dados["texto_integral"].lower()
                ):
                    doc_id_encontrado = dados["id_canonico"]
                    break

            if doc_id_encontrado:
                conf = calcular_confianca(trecho, "real", tipo, match_exato=True)
                lista_citacoes.append(
                    {
                        "id": cit_id,
                        "inicio": inicio,
                        "fim": fim,
                        "trecho": trecho,
                        "tipo": tipo,
                        "classificacao": "real",
                        "resolucao": {
                            "fonte": "jusbrasil",
                            "id_canonico": str(doc_id_encontrado),
                        },
                        "confianca": conf,
                    }
                )
            else:
                conf = calcular_confianca(trecho, "inventada", tipo)
                lista_citacoes.append(
                    {
                        "id": cit_id,
                        "inicio": inicio,
                        "fim": fim,
                        "trecho": trecho,
                        "tipo": tipo,
                        "classificacao": "inventada",
                        "resolucao": None,
                        "confianca": conf,
                    }
                )
            continue

# 3. Acórdãos e Jurisprudências (Consulta FTS5 no SQLite)
        numero_fts = formatar_numero_para_fts(trecho)
        teve_ocr = any(
            char in trecho for char in ["O", "o", "l", "I", "S"]
        ) and not re.search(r"\d", trecho)

        if not numero_fts:
            conf = calcular_confianca(trecho, "inventada", tipo)
            lista_citacoes.append(
                {
                    "id": cit_id,
                    "inicio": inicio,
                    "fim": fim,
                    "trecho": trecho,
                    "tipo": tipo,
                    "classificacao": "inventada",
                    "resolucao": None,
                    "confianca": conf,
                }
            )
            continue

        matches = buscar_acordao_fts(numero_fts)

        if matches:
            # Extrai classe (ex: "RSE") e UF (ex: "DF") da citação
            match_classe = re.search(r"^([A-Za-z]+)", trecho.strip())
            classe_trecho = match_classe.group(1).upper() if match_classe else ""
            termos_classe = CLASSES_MAPEAMENTO.get(classe_trecho, [classe_trecho])

            match_uf = re.search(r"/([A-Z]{2})\b", trecho)
            uf_trecho = match_uf.group(1).upper() if match_uf else ""

            cnj_limpo = numero_fts.replace('"', "")
            id_canonico_escolhido = None

            if len(matches) == 1:
                id_canonico_escolhido = matches[0][1]
            else:
                melhor_doc_id = None
                maior_pontuacao = -999

                for doc_id, id_canonico, tribunal, ano, tipo_doc, texto_doc in matches:
                    texto_upper = str(texto_doc).upper()
                    pos_cnj = texto_upper.find(cnj_limpo)

                    if pos_cnj != -1:
                        pontos = 0
                        
                        # Janelas de contexto ao redor do CNJ
                        antes_cnj = texto_upper[max(0, pos_cnj - 80) : pos_cnj]
                        depois_cnj = texto_upper[pos_cnj + len(cnj_limpo) : pos_cnj + len(cnj_limpo) + 80]

                        # 1. Presença da classe antes do CNJ (+3)
                        if any(termo in antes_cnj for termo in termos_classe if termo):
                            pontos += 3

                        # 2. Presença da UF igual à citação logo após o CNJ (+5)
                        if uf_trecho and f"/{uf_trecho}" in depois_cnj:
                            pontos += 5

                        # 3. Indicação de processo principal/relator (+4)
                        if "RELATOR" in depois_cnj:
                            pontos += 4

                        # 4. Penalidade se for citação incidental/prevenção (-10)
                        if any(term in antes_cnj for term in ["PREVENTO", "APENSO", "ENVOLVENDO"]):
                            pontos -= 10

                        if pontos > maior_pontuacao:
                            maior_pontuacao = pontos
                            melhor_doc_id = id_canonico

                id_canonico_escolhido = melhor_doc_id if melhor_doc_id else matches[0][1]

            conf = calcular_confianca(
                trecho, "real", tipo, match_exato=True, teve_ocr=teve_ocr
            )
            lista_citacoes.append(
                {
                    "id": cit_id,
                    "inicio": inicio,
                    "fim": fim,
                    "trecho": trecho,
                    "tipo": tipo,
                    "classificacao": "real",
                    "resolucao": {
                        "fonte": "jusbrasil",
                        "id_canonico": str(id_canonico_escolhido),
                    },
                    "confianca": conf,
                }
            )
        else:
            conf = calcular_confianca(trecho, "inventada", tipo)
            lista_citacoes.append(
                {
                    "id": cit_id,
                    "inicio": inicio,
                    "fim": fim,
                    "trecho": trecho,
                    "tipo": tipo,
                    "classificacao": "inventada",
                    "resolucao": None,
                    "confianca": conf,
                }
            )
            
    return {
        "schema_version": "1.2",
        "documento_id": documento_id,
        "citacoes": lista_citacoes,
    }