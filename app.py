import os
import time
import random
import threading
import duckdb
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="E-Commerce Live Dashboard (All-in-One)",
    page_icon="⚡",
    layout="wide"
)

# Khóa cứng đường dẫn file database ngay tại thư mục hiện tại
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "ecommerce_merged.duckdb")

# --- DANH MỤC DỮ LIỆU GIẢ LẬP ---
PRODUCT_CATALOG = [
    ("Audio Interface USB-C", "Audio Gear", 120.0),
    ("Studio Monitor Pair", "Audio Gear", 150.0),
    ("Electric Guitar Strings", "Audio Gear", 12.5),
    ("NVMe SSD 1TB", "PC Hardware", 85.0),
    ("Mechanical Keyboard", "Peripherals", 95.0),
    ("Gaming Mouse Wireless", "Peripherals", 65.0),
]
PAYMENT_METHODS = ["Credit Card", "E-Wallet", "Bank Transfer", "COD"]
CITIES = ["Hanoi", "Ho Chi Minh", "Da Nang", "Hai Phong", "Can Tho"]

def init_and_run_generator():
    """Hàm chạy ngầm liên tục để sinh dữ liệu và ghi vào DuckDB"""
    # Đảm bảo kết nối và tạo bảng nếu chưa có
    with duckdb.connect(DB_FILE) as con:
        con.execute("""
            CREATE SEQUENCE IF NOT EXISTS order_id_seq START 1001;
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER DEFAULT nextval('order_id_seq'),
                timestamp TIMESTAMP,
                product_name VARCHAR,
                category VARCHAR,
                price DOUBLE,
                quantity INTEGER,
                total_amount DOUBLE,
                city VARCHAR,
                payment_method VARCHAR
            );
        """)
        
        # Tạo sẵn 30 dòng dữ liệu lịch sử nếu bảng đang trống
        count = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count == 0:
            now = datetime.now()
            for i in range(30, 0, -1):
                past_time = now - timedelta(minutes=i)
                prod, cat, price = random.choice(PRODUCT_CATALOG)
                qty = random.randint(1, 4)
                con.execute("""
                    INSERT INTO orders (timestamp, product_name, category, price, quantity, total_amount, city, payment_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (past_time, prod, cat, price, qty, round(price * qty, 2), random.choice(CITIES), random.choice(PAYMENT_METHODS)))

    # Vòng lặp ngầm bơm dữ liệu mỗi 2 giây
    while True:
        try:
            with duckdb.connect(DB_FILE) as con:
                prod, cat, price = random.choice(PRODUCT_CATALOG)
                qty = random.randint(1, 4)
                total = round(price * qty, 2)
                con.execute("""
                    INSERT INTO orders (timestamp, product_name, category, price, quantity, total_amount, city, payment_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (datetime.now(), prod, cat, price, qty, total, random.choice(CITIES), random.choice(PAYMENT_METHODS)))
        except Exception:
            pass
        time.sleep(2)

# --- KHỞI ĐỘNG LUỒNG NGẦM (CHỈ CHẠY 1 LẦN DUY NHẤT) ---
if "data_thread_started" not in st.session_state:
    st.session_state["data_thread_started"] = True
    t = threading.Thread(target=init_and_run_generator, daemon=True)
    t.start()


def load_data():
    """Đọc dữ liệu an toàn từ DuckDB"""
    for _ in range(5):
        try:
            with duckdb.connect(DB_FILE, read_only=True) as con:
                kpi_df = con.execute("""
                    SELECT 
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(total_amount), 0) AS total_revenue,
                        COALESCE(AVG(total_amount), 0) AS avg_order_value
                    FROM orders
                """).df()

                cat_df = con.execute("""
                    SELECT category, SUM(total_amount) AS revenue
                    FROM orders GROUP BY category ORDER BY revenue DESC
                """).df()

                city_df = con.execute("""
                    SELECT city, SUM(total_amount) AS revenue
                    FROM orders GROUP BY city ORDER BY revenue DESC
                """).df()

                trend_df = con.execute("""
                    SELECT strftime(timestamp, '%H:%M:%S') AS time_str, total_amount
                    FROM orders ORDER BY order_id DESC LIMIT 30
                """).df()

                recent_df = con.execute("""
                    SELECT 
                        order_id AS "Mã ĐH",
                        strftime(timestamp, '%Y-%m-%d %H:%M:%S') AS "Thời gian",
                        product_name AS "Sản phẩm",
                        category AS "Danh mục",
                        quantity AS "SL",
                        total_amount AS "Tổng ($)",
                        city AS "Thành phố",
                        payment_method AS "Thanh toán"
                    FROM orders ORDER BY order_id DESC LIMIT 10
                """).df()

                return kpi_df, cat_df, city_df, trend_df, recent_df
        except Exception:
            time.sleep(0.1)
    return None, None, None, None, None


# --- GIAO DIỆN STREAMLIT ---
st.title("Real-Time E-Commerce Dashboard")
st.caption(f"Tự động sinh dữ liệu ngầm và cập nhật mỗi 2 giây | Database: `{DB_FILE}`")

kpi_df, cat_df, city_df, trend_df, recent_df = load_data()

if kpi_df is not None:
    # 1. Chỉ số KPI
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Tổng Doanh Thu", f"${kpi_df['total_revenue'].iloc[0]:,.2f}")
    c2.metric("📦 Tổng Số Đơn Hàng", f"{kpi_df['total_orders'].iloc[0]:,}")
    c3.metric("💳 Giá Trị Trung Bình", f"${kpi_df['avg_order_value'].iloc[0]:,.2f}")

    st.divider()

    # 2. Biểu đồ trực quan
    ch1, ch2 = st.columns(2)
    with ch1:
        st.subheader("📈 Biến động 30 đơn hàng gần nhất ($)")
        if not trend_df.empty:
            st.line_chart(trend_df.iloc[::-1].set_index("time_str")["total_amount"])

    with ch2:
        st.subheader("🏆 Doanh thu theo Danh mục ($)")
        if not cat_df.empty:
            st.bar_chart(cat_df.set_index("category")["revenue"])

    # 3. Bảng dữ liệu chi tiết
    b1, b2 = st.columns([1, 2])
    with b1:
        st.subheader("🌆 Theo Thành phố")
        if not city_df.empty:
            st.bar_chart(city_df.set_index("city")["revenue"])
    with b2:
        st.subheader("🕒 10 Giao dịch mới nhất (Live)")
        st.dataframe(recent_df, use_container_width=True, hide_index=True)

# Tự động làm mới trang sau 2 giây để thấy data nhảy số realtime
time.sleep(2)
st.rerun()