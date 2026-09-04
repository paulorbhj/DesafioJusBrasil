# Meu Sistema Docker
Este é um sistema rodando em container Docker e integrado ao GitHub.
# Desafio JusBrasil - Pipeline PNL

Aplicação containerizada em Python para extração automatizada, normalização de OCR e classificação de citações jurídicas (leis e jurisprudências) no formato JSON (schema v1.2).

**Tecnologias Utilizadas**
* Python 3.11
* SQLite3 (Base canônica e busca textual FTS5)
* Docker
* Git / GitHub

**Estrutura do Projeto**

* `data/desafio1_bracis.db`: Base canônica congelada em SQLite com suporte a buscas textuais FTS5.
* `conexao_banco.py`: Módulo de comunicação com o SQLite, buscas por frase via FTS5 e carregamento de normas em memória.
* `processador_pnl.py`: Módulo de PNL, normalização Unicode NFC, filtro dinâmico de cabeçalhos e extração via RegEx.
* `resolutor.py`: Módulo resolutor responsável por cruzar as extrações de PNL com a base canônica para definir os rótulos (`real`, `inventada`, `incompleta`) e atribuir IDs.
* `main.py`: Ponto de entrada e orquestrador do pipeline de execução.

**Como Executar o Projeto**

1. Certifique-se de que o Docker Desktop está em execução.

2. Compile a imagem Docker no terminal:
   docker build -t desafio-jusbrasil .

3. Execute o container:
   docker run desafio-jusbrasil

   ### 1. Execução via Linha de Comando (CLI)
```bash
# Processar um documento e exibir o JSON no stdout
python main.py caminho/do/documento.txt

# Processar um documento e salvar a saída em um arquivo .json
python main.py caminho/do/documento.txt --saida resultado.json

