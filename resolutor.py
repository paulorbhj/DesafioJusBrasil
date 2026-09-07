import re
import unicodedata
from conexao_banco import buscar_acordao_fts, carregar_normas_memoria
from processador_pnl import formatar_numero_para_fts, processar_pnl



def remover_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )

# Mapeamento expandido de siglas, compostos e nomes por extenso das classes processuais
CLASSES_MAPEAMENTO = {
    # --- CLASSES COMPOSTAS E RECURSOS COMBINADOS (Buscados prioritariamente) ---
    "EDCL_AGINT_ARESP": [
        "EDCL NOS EDCL NO AGINT NO ARESP",
        "EDCL NO AGINT NO ARESP",
        "EMBARGOS DE DECLARAÇÃO NO AGRAVO INTERNO NO AGRAVO EM RECURSO ESPECIAL",
    ],
    "EDCL_AGINT_RESP": [
        "EDCL NO AGINT NO RESP",
        "EMBARGOS DE DECLARAÇÃO NO AGRAVO INTERNO NO RECURSO ESPECIAL",
    ],
    "AGINT_EDCL_RESP": [
        "AGINT NOS EDCL NO RESP",
        "AGRAVO INTERNO NOS EMBARGOS DE DECLARAÇÃO NO RECURSO ESPECIAL",
    ],
    "AGINT_ARESP": [
        "AGINT NO ARESP",
        "AGRAVO INTERNO NO AGRAVO EM RECURSO ESPECIAL",
        "AGRAVO INTERNO NO ARESP",
    ],
    "AGINT_RESP": [
        "AGINT NO RESP",
        "AGRAVO INTERNO NO RECURSO ESPECIAL",
        "AGINT NO RECURSO ESPECIAL",
    ],
    "AGRG_ARESP": [
        "AGRG NO ARESP",
        "AGRAVO REGIMENTAL NO AGRAVO EM RECURSO ESPECIAL",
    ],
    "AGRG_RESP": [
        "AGRG NO RESP",
        "AGRAVO REGIMENTAL NO RECURSO ESPECIAL",
        "AGRG NO REC. ESP.",
    ],
    "EDCL_RMS": [
        "EMBARGOS DE DECLARAÇÃO NO RECURSO EM MANDADO DE SEGURANÇA",
        "EDCL NO RMS",
        "ED NO RMS",
    ],
    "AGR_RESPE": [
        "AGR-RESPE",
        "AGRAVO REGIMENTAL NO RECURSO ESPECIAL ELEITORAL",
        "ED NO AGR-RESPE",
        "EDS NO AGR-RESPE",
    ],
    "AGR_AI": [
        "AGR-AI",
        "AGRAVO REGIMENTAL NO AGRAVO DE INSTRUMENTO",
        "AGRG NO AI",
    ],
    "AGRG_HC": [
        "AGRG NO HC",
        "AGRG NO H.C.",
        "AGRAVO REGIMENTAL NO HABEAS CORPUS",
    ],

    # --- JUSTIÇA DO TRABALHO (TST) E ELEITORAL (TSE) ---
    "ED_E_ED_RR": [
        "ED-E-ED-RR",
        "ED-E-ED-ARR",
        "EMBARGOS EM EMBARGOS DE DECLARAÇÃO EM RECURSO DE REVISTA",
    ],
    "ARR": [
        "ARR",
        "AGARR",
        "AGRAVO DE INSTRUMENTO E RECURSO DE REVISTA",
    ],
    "RR": ["RR", "RECURSO DE REVISTA"],
    "RESPE": ["RESPE", "RECURSO ESPECIAL ELEITORAL"],
    "ARESPEI": ["ARESPEI", "ARESPEL", "AGRAVO EM RECURSO ESPECIAL ELEITORAL"],
    "R_RP": ["R-RP", "RECURSO EM REPRESENTAÇÃO"],

    # --- SÚMULAS ---
    "SV": ["SÚMULA VINCULANTE", "SV"],
    "SUM": ["SÚMULA", "VERBETE SUMULAR", "SÚM."],

    # --- RECURSAIS PRINCIPAIS E AGRAVOS ---
    "RSE": ["RSE", "RECURSO EM SENTIDO ESTRITO"],
    "APL": ["APL", "APELAÇÃO", "APELAÇÃO CÍVEL", "AC"],
    "AGINT": ["AGINT", "AG. INT.", "AGRAVO INTERNO"],
    "AI": ["AI", "AGRAVO DE INSTRUMENTO"],
    "AGRG": ["AGRG", "AG.REG", "AGRAVO REGIMENTAL"],
    "ARE": ["ARE", "AGRAVO EM RECURSO EXTRAORDINÁRIO"],
    "ARESP": ["ARESP", "A.RESP", "AGRAVO EM RECURSO ESPECIAL", "AGRESP"],
    "RE": ["RE", "REC. EXT.", "RECURSO EXTRAORDINÁRIO"],
    "RESP": ["RESP", "R.ESP.", "REC. ESP.", "REC. ESP", "RECURSO ESPECIAL"],
    "RHC": ["RHC", "RECURSO EM HABEAS CORPUS"],
    "RMS": ["RMS", "RECURSO EM MANDADO DE SEGURANÇA"],
    "ED": ["ED", "EDCL", "EMBARGOS DE DECLARAÇÃO"],
    "EI": ["EI", "EMBARGOS INFRINGENTES"],
    "ERE": ["ERE", "EMBARGOS DE DIVERGÊNCIA EM RECURSO EXTRAORDINÁRIO"],
    "ERESP": ["ERESP", "EMBARGOS DE DIVERGÊNCIA EM RECURSO ESPECIAL"],

    # --- AÇÕES CONSTITUCIONAIS E GARANTIAS ---
    "HC": ["HC", "H.C.", "HABEAS CORPUS"],
    "MS": ["MS", "MANDADO DE SEGURANÇA"],
    "MI": ["MI", "MANDADO DE INJUNÇÃO"],
    "HD": ["HD", "HABEAS DATA"],
    "RCL": ["RCL", "RECLAMAÇÃO", "RECL."],

    # --- CONTROLE CONCENTRADO (STF) ---
    "ADI": ["ADI", "ADIN", "AÇÃO DIRETA DE INCONSTITUCIONALIDADE"],
    "ADC": ["ADC", "AÇÃO DECLARATÓRIA DE CONSTITUCIONALIDADE"],
    "ADPF": ["ADPF", "ARGUIÇÃO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL"],

    # --- AÇÕES ORIGINÁRIAS, SUSPENSÕES E INCIDENTES ---
    "AR": ["AR", "AÇÃO RESCISÓRIA"],
    "AP": ["AP", "AÇÃO PENAL"],
    "CC": ["CC", "CONFLITO DE COMPETÊNCIA"],
    "SL": ["SL", "SLS", "SUSPENSÃO DE LIMINAR", "SUSPENSÃO DE LIMINAR E DE SENTENÇA"],
    "STP": ["STP", "SUSPENSÃO DE TUTELA PROVISÓRIA"],
    "SS": ["SS", "SUSPENSÃO DE SEGURANÇA"],
    "PET": ["PET", "PETIÇÃO"],
}

VARIACOES_ORDENADAS = []
for sigla, variacoes in CLASSES_MAPEAMENTO.items():
    for v in variacoes:
        VARIACOES_ORDENADAS.append((remover_acentos(v.upper()), variacoes))

# Ordena os termos do maior para o menor para evitar matches parciais
VARIACOES_ORDENADAS.sort(key=lambda item: len(item[0]), reverse=True)

def obter_termos_classe(trecho: str) -> list:
    trecho_norm = remover_acentos(trecho.strip().upper())

    for var_norm, lista_original in VARIACOES_ORDENADAS:
        padrao = r"(?<!\w)" + re.escape(var_norm) + r"(?!\w)"
        if re.search(padrao, trecho_norm):
            return lista_original

    match_classe = re.search(r"^([A-Za-z]+)", trecho.strip())
    classe_fallback = match_classe.group(1).upper() if match_classe else ""
    return [classe_fallback] if classe_fallback else []


def calcular_confianca(
    trecho: str,
    classificacao: str,
    tipo: str,
    match_exato: bool = False,
    teve_ocr: bool = False,
) -> float:
    """Calcula dinamicamente o score de confiança (0.00 a 1.00)."""
    if classificacao == "real":
        return 0.88 if teve_ocr else 0.98

    if classificacao == "inventada":
        padrao_cnj_estrito = (
            r"^\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?:/[A-Z]{2})?$"
        )
        if re.search(padrao_cnj_estrito, trecho.strip()):
            return 0.95
        return 0.80

    if classificacao == "incompleta":
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

        # Se formatar_numero_para_fts falhar, extrai a sequência numérica do trecho
        if not numero_fts:
            match_num = re.search(r"(\d{1,7}(?:\.\d{3})*(?:-\d+)?|\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})", trecho)
            if match_num:
                numero_fts = f'"{match_num.group(1)}"'

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

        # Fallback: Se a busca exata falhar devido a sufixos como "/PR", busca apenas o número limpo
        if not matches and numero_fts:
            numero_limpo = re.sub(r"/[A-Z]{2}", "", numero_fts.replace('"', "")).strip()
            if numero_limpo and numero_limpo != numero_fts.replace('"', ""):
                matches = buscar_acordao_fts(f'"{numero_limpo}"')

        if matches:
            termos_classe = obter_termos_classe(trecho)

            match_uf = re.search(r"/([A-Z]{2})\b", trecho)
            uf_trecho = match_uf.group(1).upper() if match_uf else ""

            cnj_limpo = re.sub(r"/[A-Z]{2}", "", numero_fts.replace('"', "")).strip()
            id_canonico_escolhido = None

            if len(matches) == 1:
                id_canonico_escolhido = matches[0][1]
            else:
                melhor_doc_id = None
                maior_pontuacao = -999

                for doc_id, id_canonico, tribunal, ano, tipo_doc, texto_doc in matches:
                    texto_upper = str(texto_doc).upper()
                    pos_cnj = texto_upper.find(cnj_limpo)
                    if pos_cnj == -1 and "." in cnj_limpo:
                        pos_cnj = texto_upper.find(cnj_limpo.replace(".", ""))

                    if pos_cnj != -1:
                        pontos = 0
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

                        # 4. Penalidade se for citação incidental (-10)
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