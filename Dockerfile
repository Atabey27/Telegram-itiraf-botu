# Python 3.12 slim imajını kullan
FROM python:3.12-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Kodları konteynıra kopyala
COPY . .

# Sisteme gcc ve build-essential kur (tgcrypto vs. için şart)
RUN apt-get update && apt-get install -y gcc build-essential

# Pip'i güncelle ve bağımlılıkları yükle
RUN pip install --upgrade pip && pip install -r requirements.txt

# Botu çalıştır
CMD ["python3", "itiraf_bot.py"]
