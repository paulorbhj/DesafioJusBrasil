import re
from conexao_banco import buscar_acordao_fts, carregar_normas_memoria
from processador_pnl import formatar_numero_para_fts, processar_pnl


def resolver_citacoes(texto: str) -> list[dict]:
    """
    Recebe o documento bruto, extrai citações via PNL e cruza com a
    base canônica para determinar a classificação ('real', 'inventada', 'incompleta').
    """
    citacoes_brutas = processar_pnl(texto)
    normas_memoria = carregar_normas_memoria()
    resultado_final = []

    for cit in citacoes_brutas:
        # 1. Trata citações incompletas identificadas pelo PNL
        if cit.get("classificacao_sugerida") == "incompleta":
            resultado_final.append(
                {
                    "span": [cit["inicio"], cit["fim"]],
                    "tipo": cit["tipo"],
                    "classificacao": "incompleta",
                    "id": None,
                }
            )
            continue

        trecho = cit["trecho"]
        tipo = cit["tipo"]

        # 2. Trata Leis e Súmulas (Consulta em Memória)
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
                resultado_final.append(
                    {
                        "span": [cit["inicio"], cit["fim"]],
                        "tipo": tipo,
                        "classificacao": "real",
                        "id": str(doc_id_encontrado),
                    }
                )
            else:
                resultado_final.append(
                    {
                        "span": [cit["inicio"], cit["fim"]],
                        "tipo": tipo,
                        "classificacao": "inventada",
                        "id": None,
                    }
                )
            continue

        # 3. Trata Acórdãos / Jurisprudências (Consulta FTS5 no SQLite)
        numero_fts = formatar_numero_para_fts(trecho)
        if not numero_fts:
            resultado_final.append(
                {
                    "span": [cit["inicio"], cit["fim"]],
                    "tipo": tipo,
                    "classificacao": "inventada",
                    "id": None,
                }
            )
            continue

        matches = buscar_acordao_fts(numero_fts)

        if matches:
            # matches[0] retorna: (documento_id, id_canonico, tribunal, ano)
            _, id_canonico, _, _ = matches[0]
            resultado_final.append(
                {
                    "span": [cit["inicio"], cit["fim"]],
                    "tipo": tipo,
                    "classificacao": "real",
                    "id": str(id_canonico),
                }
            )
        else:
            resultado_final.append(
                {
                    "span": [cit["inicio"], cit["fim"]],
                    "tipo": tipo,
                    "classificacao": "inventada",
                    "id": None,
                }
            )

    return resultado_final