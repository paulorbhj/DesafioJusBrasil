
import argparse
import json
from pathlib import Path
import sys

from conexao_banco import testar_conexao
from resolutor import resolver_citacoes


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de extração e classificação - Desafio Jusbrasil"
    )
    parser.add_argument(
        "arquivo",
        nargs="?",
        type=str,
        help="Caminho do arquivo .txt a ser analisado",
    )
    parser.add_argument(
        "--saida",
        "-o",
        type=str,
        help="Caminho opcional para salvar o JSON resultante",
    )

    args = parser.parse_args()

    sucesso, _ = testar_conexao()
    if not sucesso:
        print(" Erro ao conectar ao banco de dados.", file=sys.stderr)
        sys.exit(1)

    # 1. Define o arquivo a ser processado
    if not args.arquivo:
        # Tenta localizar o arquivo de 10 citações na pasta data/ ou na raiz
        caminho_padrao = Path("data/gen_n1_001.txt")
        if not caminho_padrao.exists():
            caminho_padrao = Path("gen_n1_001.txt")

        if caminho_padrao.exists():
            caminho_input = caminho_padrao
        else:
            # Fallback de segurança se o arquivo não for encontrado na imagem
            texto_demo = """DEFENSORIA PÚBLICA DA UNIÃO
            MEMORIAL
            Excelentíssimos Senhores Ministros...
            Invoca-se, ainda, o julgado do STF proferido em 2024 pela relatoria de Dias Toffoli.
            Invoca-se, ainda, a Reclamação nº 66.516/RO.
            Aplica-se o art. 186 do Código Civil.
            """
            resultado = resolver_citacoes(texto_demo, documento_id="doc_demo")
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
            return
    else:
        caminho_input = Path(args.arquivo)

    # 2. Valida se o arquivo existe
    if not caminho_input.exists():
        print(
            f" Arquivo não encontrado: {caminho_input.resolve()}",
            file=sys.stderr,
        )
        sys.exit(1)

    doc_id = caminho_input.stem  # Extrai o ID do documento dinamicamente (ex: "gen_n1_001")

    # 3. Lê o conteúdo e executa a resolução
    with open(caminho_input, "r", encoding="utf-8") as f:
        texto = f.read()

    resultado = resolver_citacoes(texto, documento_id=doc_id)
    json_str = json.dumps(resultado, indent=2, ensure_ascii=False)

    print(json_str)

    if args.saida:
        caminho_saida = Path(args.saida)
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_saida, "w", encoding="utf-8") as f:
            f.write(json_str)


if __name__ == "__main__":
    main()

