FROM python:3.12-slim

WORKDIR /app

# 한글 폰트 설치 (matplotlib 그래프용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-nanum fontconfig && \
    rm -rf /var/lib/apt/lists/* && \
    fc-cache -fv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# matplotlib 폰트 캐시 초기화
RUN python -c "import matplotlib.font_manager as fm; fm._load_fontmanager()" 2>/dev/null || true

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
