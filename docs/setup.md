# Hướng Dẫn Cài Đặt và Chạy Dự Án

Tài liệu này hướng dẫn cách thiết lập và chạy dự án AI CSKH trên môi trường local và Docker.

## Cài đặt trên Local

### 1. Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
copy .env.example .env
uvicorn app.main:app --reload
```
Backend sẽ chạy tại [http://localhost:8000](http://localhost:8000).

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```
Frontend sẽ chạy tại [http://localhost:3000](http://localhost:3000).

## Biến Môi Trường (Environment Variables)

### Backend
Xem file mẫu [`backend/.env.example`](../backend/.env.example).
Các giá trị quan trọng:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `EMBEDDING_MODEL`
- `ALLOWED_ORIGINS`
- `DATABASE_URL`
- `DISCORD_WEBHOOK_URL`

*Lưu ý: Nếu không có `OPENAI_API_KEY`, ứng dụng sẽ tự động chuyển sang chế độ demo cho các câu trả lời LLM chung chung.*

### Frontend
Xem file mẫu [`frontend/.env.example`](../frontend/.env.example).
Giá trị quan trọng:
- `BACKEND_URL`

## Chạy Bằng Docker

Trước khi khởi động container, hãy tạo các file env:

```bash
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env.local
```

Sau đó chạy lệnh:

```bash
docker compose up --build
```

Lệnh này sử dụng:
- [`docker-compose.yml`](../docker-compose.yml)
- [`backend/Dockerfile`](../backend/Dockerfile)
- [`frontend/Dockerfile`](../frontend/Dockerfile)

Dịch vụ:
- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)

**Ghi chú:**
- Container frontend hiện tại chạy `next dev` để tiện cho việc demo, không phải là server Next.js tối ưu cho production.
- Backend sử dụng đường dẫn file SQLite cục bộ được cấu hình trong `backend/.env`.
- `OPENAI_API_KEY` là tùy chọn cho luồng demo local, nhưng bắt buộc nếu muốn LLM sinh ra phản hồi thực tế.

## Chạy Test

### Test Backend

```bash
pytest backend/tests -q
```

### Type-check Frontend

```bash
cd frontend
npx tsc --noEmit
```
