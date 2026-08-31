# 1. Define a imagem oficial do Python (versão estável e leve)
FROM python:3.11-slim

# 2. Define a pasta dentro do container onde o projeto vai rodar
WORKDIR /app

# 3. Copia o arquivo de dependências para dentro do container
COPY requirements.txt .

# 4. Instala as bibliotecas listadas no requirements.txt sem salvar cache (deixa mais leve)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o restante dos arquivos do seu projeto para o container
COPY . .

# 6. Comando para executar o seu arquivo principal Python
CMD ["python", "main.py"]
