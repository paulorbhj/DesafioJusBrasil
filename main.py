
import json
from conexao_banco import testar_conexao
from resolutor import resolver_citacoes

TEXTO_EXEMPLO = """DEFENSORIA PÚBLICA DA UNIÃO
OFÍCIO JUNTO AO SUPERIOR TRIBUNAL MILITAR

Processo nº 1292746-27.2020.7.13.1173
Assistido: TRANSPORTES MARAJÓ EIRELI
Memorial nº 255/2021

MEMORIAL

Excelentíssimos Senhores Ministros, a Defensoria Pública da União apresenta o presente memorial...

Invoca-se, ainda, o julgado do STF proferido em 2024 pela relatoria de Dias Toffoli.
Invoca-se, ainda, a Reclamação nº 66.516/RO, no ponto em que afasta a exigência combatida.
Invoca-se, ainda, o AgInt 7557430-50.2018.7.00.0000/DF.
Aplica-se o art. 186 do Código Civil.
"""


def main():
    print(" Inicializando pipeline do Desafio Jusbrasil...")

    # 1. Validação simples de ambiente e banco
    sucesso, _ = testar_conexao()
    if not sucesso:
        print(" Falha na conexão com o banco de dados.")
        return

    # 2. Processamento completo: Extração + Cruzamento Canônico + Classificação
    resultado = resolver_citacoes(TEXTO_EXEMPLO)

    # 3. Exibição do JSON estruturado (Schema v1.2)
    print("\n--- Resultado Final (Schema v1.2) ---")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

