# Python 3.11 kullan
FROM python:3.11-slim

# Çalışma dizini oluştur ve ayarla
WORKDIR /app

# Gereken sistem paketleri (sqlite için)
RUN apt-get update && apt-get install -y gcc libsqlite3-dev && rm -rf /var/lib/apt/lists/*

# Gereken python paketlerini kopyala ve yükle
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Bot kodunu kopyala
COPY itiraf.py .

# .env dosyasını kopyala (build sırasında değil, runtime’da volume olarak kullanmak daha iyi)
# COPY .env .

# Botu çalıştır
CMD ["python", "itiraf.py"]
