print("Sistema em Python rodando com sucesso no Docker!")

import unicodedata

def limpar_e_normalizar_texto(texto_bruto: str) -> str:
    """Garante que o texto use estritamente o padrão Unicode NFC."""
    if not isinstance(texto_bruto, str):
        return ""
    # Força a normalização rígida para NFC
    return unicodedata.normalize('NFC', texto_bruto)

def processar_pnl(texto):
    # Aqui entra o seu código de PNL, Scikit-Learn, Spacy, etc.
    print(f"Processando com PNL: {texto}")

if __name__ == "__main__":
    # Exemplo 1: Tratando um input direto
    dados_entrada = "Processo Judicial do Vovô"
    texto_limpo = limpar_e_normalizar_texto(dados_entrada)
    
    # Exemplo 2: Se você estivesse lendo um arquivo de texto
    # with open("dados.txt", "r", encoding="utf-8") as f:
    #     texto_limpo = limpar_e_normalizar_texto(f.read())

    # Dispara o pipeline de Machine Learning / PNL com o dado garantido em NFC
    processar_pnl(texto_limpo)
