# Desafio JusBrasil - Pipeline PNL


Aplicação containerizada em Python para extração automatizada, normalização de OCR e classificação de citações jurídicas (leis e jurisprudências) no formato JSON (schema v1.2).

**Tecnologias Utilizadas**
* Python 3.11
* GLiNER (Zero-Shot Named Entity Recognition)
* PyTorch / Hugging Face Transformers
* SQLite3 (Base canônica e busca textual FTS5)
* Docker
* Git / GitHub

**Requisitos do Sistema**
* **Memória RAM:** Recomenda-se ao menos 4 GB de RAM no sistema (o modelo do GLiNER consome cerca de 1 GB de RAM ao ser carregado).
* **Espaço em Disco:** ~1 GB livre para armazenamento do modelo multilíngue (`urchade/gliner_multi-v2.1`).
* **Conexão com a Internet:** Necessária apenas no primeiro *build* do Docker (ou primeira execução local) para o download automático dos pesos do modelo.

**Estrutura do Projeto**

* `data/desafio1_bracis.db`: Base canônica congelada em SQLite com suporte a buscas textuais FTS5.
* `conexao_banco.py`: Módulo de comunicação com o SQLite, buscas por frase via FTS5 e carregamento de normas em memória.
* `processador_pnl.py`: Módulo de PNL, normalização Unicode NFC, filtro dinâmico de cabeçalhos e extração contextual via aprendizado de máquina (GLiNER).
* `resolutor.py`: Módulo resolutor responsável por cruzar as extrações de PNL com a base canônica para definir os rótulos (`real`, `inventada`, `incompleta`) e atribuir IDs.
* `main.py`: Ponto de entrada e orquestrador do pipeline de execução.

**Como Executar o Projeto**

1. Certifique-se de que o Docker Desktop está em execução.

2. Compile a imagem Docker no terminal:
   docker build -t desafio-jusbrasil .

3. Execute o container:
   docker run desafio-jusbrasil


### 1. Execução via Linha de Comando (CLI Local)

```bash
# 1. Instalar as dependências do projeto
pip install -r requirements.txt

# 2. Processar um documento e exibir o JSON no stdout
python main.py caminho/do/documento.txt

# 3. Processar um documento e salvar a saída em um arquivo .json
python main.py caminho/do/documento.txt --saida resultado.json

# 4. Para executar no Docker 
Os arquivos para análise(.txt) devem ficar na mesma pasta do projeto. Só assim poderão usar as linhas de código logo abaixo.

docker build -t desafio-jus .
docker run --rm desafio-jus python main.py txt/nome_do_arquivo.txt

