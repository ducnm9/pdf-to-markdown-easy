# Base image có sẵn Python 3.12 + poppler — không cần apt-get gì thêm
FROM python:3.12-bookworm

WORKDIR /app

# Cài poppler-utils (bookworm có cache tốt hơn, chỉ chạy 1 lần rồi cache)
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Cài Python dependencies (không có hypothesis — test only)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    $(grep -v '^hypothesis' requirements.txt | tr '\n' ' ')

# Copy source code
COPY src/             ./src/
COPY prompt.txt       ./prompt.txt
COPY merge_prompt.txt ./merge_prompt.txt

VOLUME ["/app/inputs", "/app/images", "/app/markdowns"]

RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python", "-m", "src.main"]
