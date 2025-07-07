# Python 3.12 resmi imajı
FROM python:3.12-slim

# Çalışma dizinini oluştur
WORKDIR /app

# Gerekli dosyaları kopyala
COPY . .

# pip güncelle ve bağımlılıkları yükle
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Ortam değişkenlerini .env'den okuyabilmek için dotenv yükle
RUN pip install python-dotenv

# Botu çalıştır
CMD ["python", "itiraf_bot.py"]
