import json
import os
import re

from conexao_banco import buscar_acordao_fts, carregar_normas_memoria
from processador_pnl import formatar_numero_para_fts, processar_pnl

CLASSES_MAPEAMENTO = {
    "RSE": ["RSE", "RECURSO EM SENTIDO ESTRITO"],
    "APL": ["APL", "APELAÇÃO", "APELACAO"],
    "AC": ["AC", "APELAÇÃO CÍVEL", "APELACAO CIVEL"],
    "AGINT": ["AGINT", "AGRAVO INTERNO"],
    "AI": ["AI", "AGRAVO DE INSTRUMENTO"],
    "AGRG": ["AGRG", "AGRAVO REGIMENTAL"],
    "ARE": ["ARE", "AGRAVO EM RECURSO EXTRAORDINÁRIO", "AGRAVO EM RECURSO EXTRAORDINARIO"],
    "ARESP": ["ARESP", "AGRAVO EM RECURSO ESPECIAL"],
    "RE": ["RE", "RECURSO EXTRAORDINÁRIO", "RECURSO EXTRAORDINARIO"],
    "RESP": ["RESP", "RECURSO ESPECIAL"],
    "RHC": ["RHC", "RECURSO EM HABEAS CORPUS"],
    "RMS": ["RMS", "RECURSO EM MANDADO DE SEGURANÇA", "RECURSO EM MANDADO DE SEGURANCA"],
    "ED": ["ED", "EMBARGOS DE DECLARAÇÃO", "EMBARGOS DE DECLARACAO"],
    "EI": ["EI", "EMBARGOS INFRINGENTES"],
    "ERE": ["ERE", "EMBARGOS DE DIVERGÊNCIA EM RECURSO EXTRAORDINÁRIO", "EMBARGOS DE DIVERGENCIA EM RECURSO EXTRAORDINARIO"],
    "ERESP": ["ERESP", "EMBARGOS DE DIVERGÊNCIA EM RECURSO ESPECIAL", "EMBARGOS DE DIVERGENCIA EM RECURSO ESPECIAL"],
    "HC": ["HC", "HABEAS CORPUS"],
    "MS": ["MS", "MANDADO DE SEGURANÇA", "MANDADO DE SEGURANCA"],
    "MI": ["MI", "MANDADO DE INJUNÇÃO", "MANDADO DE INJUNCAO"],
    "HD": ["HD", "HABEAS DATA"],
    "RCL": ["RCL", "RECLAMAÇÃO", "RECLAMACAO"],
    "ADI": ["ADI", "ADIN", "AÇÃO DIRETA DE INCONSTITUCIONALIDADE", "ACAO DIRETA DE INCONSTITUCIONALIDADE"],
    "ADC": ["ADC", "AÇÃO DECLARATÓRIA DE CONSTITUCIONALIDADE", "ACAO DECLARATORIA DE CONSTITUCIONALIDADE"],
    "ADPF": ["ADPF", "ARGUIÇÃO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL", "ARGUICAO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL"],
    "AR": ["AR", "AÇÃO RESCISÓRIA", "ACAO RESCISORIA"],
    "AP": ["AP", "AÇÃO PENAL", "ACAO PENAL"],
    "CC": ["CC", "CONFLITO DE COMPETÊNCIA", "CONFLITO DE COMPETENCIA"],
    "SL": ["SL", "SUSPENSÃO DE LIMINAR", "SUSPENSAO DE LIMINAR"],
    "STP": ["STP", "SUSPENSÃO DE TUTELA PROVISÓRIA", "SUSPENSAO DE TUTELA PROVISORIA"],
    "SS": ["SS", "SUSPENSÃO DE SEGURANÇA", "SUSPENSAO DE SEGURANCA"],
    "PET": ["PET", "PETIÇÃO", "PETICAO"],
}


def extrair_numero_principal_documento(texto_doc: str) -> str | None:
    """Extrai o primeiro número CNJ encontrado no início do documento."""
    if not texto_doc:
        return None
    inicio = str(texto_doc)[:3000]
    padrao_cnj = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
    match = padrao_cnj.search(inicio)
    if match:
        return re.sub(r"\D", "", match.group(0))
    return None


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
        padrao_cnj_estrito = r"^\d{7}\-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?:/[A-Z]{2})?$"
        if re.search(padrao_cnj_estrito, trecho.strip()):
            return 0.95
        return 0.80

    if classificacao == "incompleta":
        if any(p in trecho.lower() for p in ["julgado do", "acórdão do", "decisão do"]):
            return 0.90
        return 0.75

    return 0.50


def resolver_citacoes(texto: str, documento_id: str = "doc_0000") -> dict:
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
                    or (len(trecho) > 5 and trecho.lower() in dados["texto_integral"].lower())
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

        # Correção da detecção de OCR
        teve_ocr = any(char in trecho for char in ["O", "l", "I", "S"]) and re.search(r"\d", trecho)

        if not numero_fts:
            match_num = re.search(
                r"(\d{1,7}(?:\.\d{3})*(?:-\d+)?|\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})",
                trecho,
            )
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

        # Fallback para remoção de sufixo de UF
        if not matches and numero_fts:
            numero_limpo = re.sub(r"/[A-Z]{2}", "", numero_fts.replace('"', "")).strip()
            if numero_limpo and numero_limpo != numero_fts.replace('"', ""):
                matches = buscar_acordao_fts(f'"{numero_limpo}"')

        if matches:
            cnj_limpo = re.sub(r"/[A-Z]{2}", "", numero_fts.replace('"', "")).strip()
            cnj_apenas_digitos = re.sub(r"\D", "", cnj_limpo)
            id_canonico_escolhido = None

            for doc in matches:
                texto_doc = doc[5]
                id_canonico = doc[1]
                numero_principal = extrair_numero_principal_documento(texto_doc)

                if numero_principal == cnj_apenas_digitos:
                    id_canonico_escolhido = id_canonico
                    break

            if id_canonico_escolhido is not None:
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
                conf = calcular_confianca(trecho, "inventada", tipo, teve_ocr=teve_ocr)
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

    # Montagem e persistência em /resultados/
    resultado = {
        "schema_version": "1.2",
        "documento_id": documento_id,
        "citacoes": lista_citacoes,
    }

    pasta_saida = "resultados"
    os.makedirs(pasta_saida, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_saida, f"{documento_id}.json")

    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=4)

    return resultado