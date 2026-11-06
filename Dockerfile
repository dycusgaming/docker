# Sử dụng Python phiên bản gọn nhẹ (slim)
FROM python:3.10-slim

# Thiết lập thư mục làm việc bên trong container
WORKDIR /app

# Copy danh sách thư viện và cài đặt trước
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container (bao gồm app_merged.py và entrypoint.sh)
COPY . .

# Cấp quyền chạy file script khởi động
RUN chmod +x entrypoint.sh

# Mở cổng 8501 để truy cập giao diện web từ bên ngoài
EXPOSE 8501

# Lệnh sẽ chạy khi container khởi động
CMD ["./entrypoint.sh"]