# OCR PDF to Markdown

Công cụ CLI Python chuyển đổi file PDF sang Markdown bằng LLM-based OCR. Ứng dụng xử lý tất cả PDF trong thư mục `inputs/`, chuyển từng trang thành ảnh, gửi ảnh đến LLM API tương thích OpenAI để nhận dạng văn bản (tối ưu cho tiếng Việt), và tạo ra file Markdown cho từng trang cùng một file Markdown tổng hợp cuối cùng.

## Tính năng

- **Hỗ trợ nhiều LLM provider** — LM Studio, Ollama (local) và DeepSeek, OpenAI (cloud) qua API chuẩn OpenAI
- **Xử lý tiếng Việt** — Prompt OCR tối ưu để nhận dạng chính xác ký tự và dấu tiếng Việt
- **Resume** — Bỏ qua các trang đã xử lý khi chạy lại, tiết kiệm thời gian và API calls
- **Xử lý đồng thời** — Kiểm soát số lượng request song song qua `MAX_CONCURRENCY`
- **Retry tự động** — Exponential backoff khi API gặp lỗi tạm thời
- **Hai chế độ merge** — Simple (nối trang với separator) hoặc Smart (dùng LLM để dọn dẹp thông minh)
- **Xử lý batch** — Tự động xử lý tất cả PDF trong thư mục `inputs/`

---

## Cấu hình

Sao chép file `.env.example` thành `.env` và điền thông tin:

```bash
cp .env.example .env
```

| Biến | Bắt buộc | Mặc định | Mô tả |
|------|:--------:|----------|-------|
| `LLM_BASE_URL` | ✅ | — | Base URL của LLM API |
| `LLM_MODEL` | ✅ | — | Tên model (ví dụ: `deepseek-chat`, `gpt-4o`) |
| `LLM_API_KEY` | ❌ | _(trống)_ | API key — để trống nếu dùng server local |
| `MAX_CONCURRENCY` | ❌ | `1` | Số request OCR chạy song song tối đa |
| `MAX_RETRIES` | ❌ | `3` | Số lần retry khi request thất bại |
| `SMART_MERGE` | ❌ | `false` | Dùng LLM để merge thông minh |
| `IMAGE_DPI` | ❌ | `300` | Độ phân giải ảnh khi chuyển PDF (150–400) |

### Ví dụ cấu hình theo provider

<details>
<summary><b>LM Studio / Ollama (local)</b></summary>

```env
LLM_BASE_URL=http://localhost:1234
LLM_MODEL=llava
MAX_CONCURRENCY=1
```
</details>

<details>
<summary><b>DeepSeek (cloud)</b></summary>

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
MAX_CONCURRENCY=4
SMART_MERGE=true
```
</details>

<details>
<summary><b>OpenAI</b></summary>

```env
LLM_BASE_URL=https://api.openai.com
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
MAX_CONCURRENCY=5
```
</details>

---

## Chạy với Docker (khuyến nghị)

Không cần cài Python hay poppler trên máy host.

### Docker Compose

```bash
# 1. Cấu hình
cp .env.example .env
# Chỉnh sửa .env với thông tin LLM của bạn

# 2. Đặt PDF vào inputs/
mkdir -p inputs
cp /path/to/your/files/*.pdf inputs/

# 3. Build và chạy
docker compose up --build
```

Chạy lại lần sau (không cần build lại):

```bash
docker compose up
```

### Chạy lệnh Python tùy ý trong container

Dùng `docker compose run` để chạy một lệnh bất kỳ trong cùng môi trường (volumes và env đã được mount):

```bash
# Chạy pipeline thủ công
docker compose run --rm ocr python -m src.main

# Mở shell để debug
docker compose run --rm ocr bash

# Kiểm tra phiên bản Python và packages
docker compose run --rm ocr python --version
docker compose run --rm ocr pip list

# Chạy một script Python tùy ý
docker compose run --rm ocr python -c "from src.config import load_config; print(load_config())"
```

> **`docker compose exec`** chỉ dùng được khi container đang chạy. Vì đây là batch job (thoát sau khi xử lý xong), hãy dùng **`docker compose run --rm`** thay thế — nó tạo container mới, chạy lệnh, rồi tự xóa.

### Docker CLI

```bash
# Build image
docker build -t ocr-pdf-to-markdown .

# Chạy
docker run --rm \
  --env-file .env \
  -v "$(pwd)/inputs:/app/inputs" \
  -v "$(pwd)/images:/app/images" \
  -v "$(pwd)/markdowns:/app/markdowns" \
  ocr-pdf-to-markdown
```

### Volumes

| Host | Container | Mô tả |
|------|-----------|-------|
| `./inputs` | `/app/inputs` | Đặt PDF vào đây |
| `./images` | `/app/images` | Ảnh PNG trung gian (tự tạo) |
| `./markdowns` | `/app/markdowns` | Kết quả Markdown (tự tạo) |
| `./prompt.txt` | `/app/prompt.txt` | Override prompt OCR không cần rebuild |
| `./merge_prompt.txt` | `/app/merge_prompt.txt` | Override merge prompt không cần rebuild |

---

## Chạy thủ công (không dùng Docker)

### Yêu cầu

- Python 3.11+
- [poppler](https://poppler.freedesktop.org/)

```bash
# macOS
brew install poppler

# Ubuntu / Debian
sudo apt-get install poppler-utils
```

### Cài đặt

```bash
git clone <repo-url>
cd ocr-pdf-to-markdown

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Chạy

```bash
# Đặt PDF vào inputs/
mkdir -p inputs && cp *.pdf inputs/

# Chạy pipeline
python -m src.main
```

---

## Kết quả đầu ra

```
markdowns/
├── document1/
│   ├── page_001.md
│   ├── page_002.md
│   └── final.md      ← file tổng hợp
└── document2/
    ├── page_001.md
    └── final.md
```

Ảnh trung gian được lưu trong `images/` (có thể xóa sau khi xử lý xong).

---

## Cấu trúc thư mục

```
ocr-pdf-to-markdown/
├── .env                    # Cấu hình (tạo từ .env.example)
├── .env.example            # Template cấu hình
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── prompt.txt              # Prompt OCR cho LLM
├── merge_prompt.txt        # Prompt merge thông minh (SMART_MERGE=true)
├── requirements.txt
├── inputs/                 # Đặt PDF vào đây
├── images/                 # Ảnh PNG trung gian (tự tạo)
├── markdowns/              # Kết quả Markdown (tự tạo)
├── src/
│   ├── __init__.py
│   ├── __main__.py         # Cho phép chạy bằng `python -m src`
│   ├── main.py             # CLI orchestration
│   ├── config.py           # Đọc và validate cấu hình từ .env
│   ├── pdf_to_images.py    # Chuyển PDF sang ảnh PNG
│   ├── ocr.py              # Gửi ảnh đến LLM API, nhận Markdown
│   └── merger.py           # Gộp các trang Markdown thành file cuối
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_pdf_to_images.py
    ├── test_ocr.py
    ├── test_merger.py
    ├── test_main.py
    └── test_smoke.py
```

---

## Tùy chỉnh prompt

**`prompt.txt`** — Hướng dẫn cho LLM khi nhận dạng văn bản từ ảnh. Mặc định tối ưu cho tiếng Việt. Chỉnh sửa để phù hợp với loại tài liệu cụ thể.

**`merge_prompt.txt`** — Chỉ dùng khi `SMART_MERGE=true`. LLM sẽ:
- Xóa các separator `<!-- Page X -->`
- Nối câu/đoạn bị cắt giữa các trang
- Loại bỏ nội dung trùng lặp (header/footer lặp lại)
- Giữ nguyên cấu trúc và ngôn ngữ gốc

Cả hai file đều được mount vào container dưới dạng volume, nên có thể chỉnh sửa mà không cần rebuild image.

---

## Xử lý lỗi & Resume

**Xử lý lỗi:**
- **Lỗi cấu hình** — Dừng ngay, thông báo rõ biến nào bị thiếu (exit code 1)
- **PDF lỗi** — Bỏ qua file đó, tiếp tục xử lý các file còn lại (exit code 1 khi kết thúc)
- **Lỗi API** — Retry với exponential backoff (`2^attempt` giây), bỏ qua trang nếu hết retry
- **Smart merge thất bại** — Tự động fallback về simple merge, ghi log cảnh báo

**Resume:** Nếu quá trình bị gián đoạn, chạy lại sẽ tự động bỏ qua các trang PNG và Markdown đã có. Chỉ xử lý những trang còn thiếu.

---

## Chạy tests

```bash
# Cài dependencies (bao gồm hypothesis cho property-based tests)
pip install -r requirements.txt
pip install pytest

# Chạy toàn bộ test suite (47 tests)
python -m pytest tests/ -v

# Chạy test của một module cụ thể
python -m pytest tests/test_ocr.py -v
```

> Tests không chạy trong Docker image (hypothesis bị loại khỏi runtime image). Chạy tests trên môi trường local.
