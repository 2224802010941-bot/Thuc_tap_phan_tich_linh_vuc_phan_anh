import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import sqlite3
import json
from google import genai
from dotenv import load_dotenv
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_socketio import join_room
from urllib.parse import quote_plus

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("Không tìm thấy GEMINI_API_KEY trong file .env")

client = genai.Client(api_key=API_KEY)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_he_thong_dvc!'
socketio = SocketIO(app)


DB_FILE = "hethong_dichvucong.db"
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'doc', 'docx', 'pdf', 'png', 'jpg', 'jpeg', 'mp4'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---- KHỞI TẠO CƠ SỞ DỮ LIỆU ----
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Bảng cấu hình phòng ban
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_phong_ban (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ten_phong TEXT,
                        linh_vuc_phu_trach TEXT UNIQUE)''')
    
    # 2. Bảng lưu phản ánh
    cursor.execute('''CREATE TABLE IF NOT EXISTS phan_anh (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        noi_dung TEXT,
                        file_dinh_kem TEXT,
                        dia_chi TEXT,
                        ten_nguoi_gui TEXT,
                        sdt TEXT,
                        linh_vuc TEXT,
                        tu_khoa TEXT,
                        sac_thai TEXT,
                        do_khan_cap INTEGER,
                        phong_ban_id INTEGER,
                        trang_thai TEXT,
                        ngay_gui TEXT,
                        lat REAL,
                        lng REAL,
                        trang_thai_duyet TEXT DEFAULT 'Cho_tiep_nhan')''')

    cursor.execute("PRAGMA table_info(phan_anh)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # migration backward-compatibility: thêm cột nếu DB cũ chưa có
    if 'ly_do_xoa' not in existing_columns:
        cursor.execute("ALTER TABLE phan_anh ADD COLUMN ly_do_xoa TEXT")
    if 'giai_thich_xoa' not in existing_columns:
        cursor.execute("ALTER TABLE phan_anh ADD COLUMN giai_thich_xoa TEXT")
    if 'ngay_xoa' not in existing_columns:
        cursor.execute("ALTER TABLE phan_anh ADD COLUMN ngay_xoa TEXT")
    if 'lat' not in existing_columns:
        cursor.execute("ALTER TABLE phan_anh ADD COLUMN lat REAL")
    if 'lng' not in existing_columns:
        cursor.execute("ALTER TABLE phan_anh ADD COLUMN lng REAL")

    # Nạp cấu hình danh mục phòng ban cố định
    cursor.execute("SELECT COUNT(*) FROM config_phong_ban")
    if cursor.fetchone()[0] == 0:
        data = [
            ("Phòng Tài nguyên và Môi trường", "Tiếng ồn"),
            ("Phòng Quản lý Đô thị", "Hạ tầng đô thị"),
            ("Đội Quản lý Trật tự Đô thị", "Trật tự đô thị"),
            ("Trung tâm Quản lý Giao thông công cộng", "Xe buýt"),
            ("Phòng Kế hoạch - Tài chính", "Kinh tế, hạ tầng và đô thị"),
            ("Phòng Văn hóa và Thông tin", "Văn hóa xã hội"),
            ("Phòng Giáo dục và Đào tạo", "Giáo dục"),
            ("Văn phòng Tiếp dân (Mặc định)", "Lĩnh vực khác")
        ]
        cursor.executemany("INSERT INTO config_phong_ban (ten_phong, linh_vuc_phu_trach) VALUES (?, ?)", data)
    conn.commit()
    conn.close()


# ---- ROUTER CHÍNH ----

@app.route('/')
def index():
    return redirect(url_for('page_submit'))

# TRANG 1: Người dân gửi phản ánh kiến nghị

@app.route('/submit', methods=['GET', 'POST'])
def page_submit():
    if request.method == 'POST':
        noi_dung = request.form['noi_dung']
        dia_chi = request.form['dia_chi']

        ten_nguoi_gui = request.form['ten_nguoi_gui']
        sdt = request.form['sdt']
        
        thoi_gian_hien_tai = datetime.now().strftime("%H:%M %d/%m/%Y")
        
        filename_saved = None
        if 'file_dinh_kem' in request.files:
            file = request.files['file_dinh_kem']
            if file and file.filename != '' and allowed_file(file.filename):
                filename_saved = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_saved))

        # 🔥 PROMPT LOẠI TRỪ NGHIÊM NGẶT - ÉP AI ĐOÁN ĐÚNG CÂY XANH VÀO HẠ TẦNG ĐÔ THỊ
# SYSTEM PROMPT LAI (HYBRID): Ép AI chọn trong danh sách, nếu lạ thì chọn "Lĩnh vực khác"
        system_prompt = """Bạn là trợ lý AI chuyên gia phân loại phản ánh dịch vụ công của công dân. 
Bạn phải tuân thủ QUY TẮC PHÂN LOẠI ƯU TIÊN sau đây:  
  
       QUY TẮC ƯU TIÊN (Phải kiểm tra theo thứ tự này):
1. NẾU nội dung phản ánh về [Nắp cống, hố ga, mặt đường, ổ gà, đèn đường, sụt lún] -> BẮT BUỘC chọn "Hạ tầng đô thị" (Dù có từ khóa tiếng ồn cũng KHÔNG chọn Tiếng ồn).
2. NẾU nội dung phản ánh về [Trạm sạc, trạm đổi pin, hàng rong, lấn chiếm vỉa hè, vật cản] -> BẮT BUỘC chọn "Trật tự đô thị".
3. CHỈ chọn "Tiếng ồn" khi nguồn gốc tiếng ồn là từ [Karaoke, quán bar, loa kéo, máy móc thi công] và KHÔNG liên quan đến hư hỏng hạ tầng.
4. NẾU phản ánh liên quan đến quy hoạch đô thị, dự án đầu tư công, quản lý đất đai, khu dân cư, khu công nghiệp, giá cả thị trường hoặc chính sách phát triển kinh tế đô thị -> chọn "Kinh tế, hạ tầng và đô thị".
DANH MỤC LĨNH VỰC (Chỉ được chọn 1):
- "Hạ tầng đô thị": Ổ gà, ngập nước, đèn đường hỏng, nắp cống, sụt lún.
- "Trật tự đô thị": Lấn chiếm lòng lề đường, đậu xe sai quy định, bán hàng rong, lắp đặt vật cản trái phép.
- "Tiếng ồn": Karaoke, loa kéo, công trường thi công đêm, tiếng máy móc dân dụng.
- "Xe buýt": Tài xế bỏ trạm, thái độ nhân viên, xe buýt phóng nhanh vượt ẩu.
- "Kinh tế, hạ tầng và đô thị": Quy hoạch vĩ mô, vấn đề thị trường đô thị.
- "Văn hóa xã hội": Lối sống, an sinh, tệ nạn, tranh chấp hàng xóm.
- "Giáo dục": Trường lớp, lạm thu, bạo lực học đường.
- "Môi trường": Rác thải, Ô nhiễm không khí, Ô nhiễm nguồn nước, Mùi hôi, Chó mèo phóng uế, Động vật hoang dã, Chất thải công nghiệp, Sự cố môi trường,tiếng ồn vượt ngưỡng (từ cơ sở sản xuất).


YÊU CẦU ĐẦU RA:
- Trích xuất mảng từ khóa tại 'tu_khoa'.
- Phân tích sắc thái (Bức xúc, Tiêu cực, Trung tính) tại 'sac_thai'.
- Đánh giá độ khẩn cấp (1-5) tại 'do_khan_cap'.
- BẮT BUỘC trả về duy nhất chuỗi JSON thuần túy, không giải thích, không kèm markdown.
        {"linh_vuc": "Tên nhãn chọn ở trên", "tu_khoa": [], "sac_thai": "...", "do_khan_cap": 1}"""
        
        # ---- VALIDATE/normalize AI output ----
        ALLOWED_LINH_VUC = {
            "Hạ tầng đô thị",
            "Trật tự đô thị",
            "Tiếng ồn",
            "Xe buýt",
            "Kinh tế, hạ tầng và đô thị",
            "Văn hóa xã hội",
            "Giáo dục",
            "Môi trường",
            "Lĩnh vực khác",
        }

        def normalize_ai_data(raw_ai_data):
            # fallback
            data = raw_ai_data if isinstance(raw_ai_data, dict) else {}

            linh_vuc = data.get('linh_vuc', 'Lĩnh vực khác')
            if not isinstance(linh_vuc, str):
                linh_vuc = 'Lĩnh vực khác'
            linh_vuc = linh_vuc.strip() or 'Lĩnh vực khác'
            if linh_vuc not in ALLOWED_LINH_VUC:
                linh_vuc = 'Lĩnh vực khác'

            tu_khoa = data.get('tu_khoa', [])
            if isinstance(tu_khoa, str):
                tu_khoa = [tu_khoa]
            if not isinstance(tu_khoa, list):
                tu_khoa = []
            tu_khoa_norm = []
            for x in tu_khoa:
                if x is None:
                    continue
                xs = str(x).strip()
                if xs:
                    tu_khoa_norm.append(xs)

            sac_thai = data.get('sac_thai', 'Trung tính')
            if not isinstance(sac_thai, str):
                sac_thai = 'Trung tính'
            sac_thai = sac_thai.strip() or 'Trung tính'
            if sac_thai not in {'Bức xúc', 'Tiêu cực', 'Trung tính'}:
                sac_thai = 'Trung tính'

            do_khan_cap = data.get('do_khan_cap', 1)
            try:
                do_khan_cap_int = int(do_khan_cap)
            except Exception:
                do_khan_cap_int = 1
            # clamp 1..5
            if do_khan_cap_int < 1:
                do_khan_cap_int = 1
            if do_khan_cap_int > 5:
                do_khan_cap_int = 5

            return {
                'linh_vuc': linh_vuc,
                'tu_khoa': tu_khoa_norm,
                'sac_thai': sac_thai,
                'do_khan_cap': do_khan_cap_int,
            }

        try:
            prompt = f"""
            {system_prompt}
            Nội dung phản ánh:
            {noi_dung}
           """
            response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)
            print("========== GEMINI RESPONSE ==========")
            print(response.text)
            print("=====================================")
            raw_content = response.text.strip()        
            ai_data = normalize_ai_data(json.loads(raw_content))
        except Exception:
            ai_data = normalize_ai_data({})


        # LUỒNG HYBRID: Khớp nhãn AI chọn với DB phòng ban
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # 1. Lấy giá trị linh vực an toàn, mặc định là "Lĩnh vực khác"

        cursor.execute("SELECT id, ten_phong FROM config_phong_ban WHERE linh_vuc_phu_trach = ?", (ai_data['linh_vuc'],))
        row = cursor.fetchone()
        
        if row:
            assigned_phong_id = row[0]
            ten_phong_nhan = row[1]
        else:
            cursor.execute("SELECT id, ten_phong FROM config_phong_ban WHERE linh_vuc_phu_trach = 'Lĩnh vực khác'")
            default_row = cursor.fetchone()
            assigned_phong_id = default_row[0] if default_row else None
            ten_phong_nhan = default_row[1] if default_row else "Văn phòng Tiếp dân (Mặc định)"
        
        # Geocode dia_chi -> (lat, lng) (tối đa 1 lần/submit; thất bại -> NULL)
        lat_val = None
        lng_val = None
        try:
            import requests
            from urllib.parse import quote_plus

            query = dia_chi.strip()
            if query:
                url = (
                    "https://nominatim.openstreetmap.org/search?"
                    f"q={quote_plus(query)}&format=json&limit=1"
                )
                headers = {
                    "User-Agent": "bosung_dash/1.0 (contact: unknown)"
                }
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        lat_val = float(data[0].get("lat")) if data[0].get("lat") else None
                        lng_val = float(data[0].get("lon")) if data[0].get("lon") else None
        except Exception:
            lat_val = None
            lng_val = None

        cursor.execute(
            """INSERT INTO phan_anh (
                noi_dung, file_dinh_kem, dia_chi, ten_nguoi_gui, sdt,
                linh_vuc, tu_khoa, sac_thai, do_khan_cap,
                phong_ban_id, trang_thai_duyet, ngay_gui, lat, lng
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                noi_dung,
                filename_saved,
                dia_chi,
                ten_nguoi_gui,
                sdt,
                ai_data['linh_vuc'],
                json.dumps(ai_data['tu_khoa'], ensure_ascii=False),
                ai_data['sac_thai'],
                ai_data['do_khan_cap'],
                assigned_phong_id,
                "Cho_tiep_nhan",
                thoi_gian_hien_tai,
                lat_val,
                lng_val,
            )
        )


        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Phát Socket.io Real-time
        # Phát Socket.io Real-time
        try:
            # Gán giá trị an toàn: nếu ID phòng bị None thì lấy 0, nếu là số thì ép kiểu int
            safe_phong_id = int(assigned_phong_id) if assigned_phong_id is not None else 0
            
            payload = {
                'id': int(new_id),
                'phong_ban_id': safe_phong_id,
                'ten_phong': str(ten_phong_nhan),
                'noi_dung': str(noi_dung),
                'linh_vuc': str(ai_data.get('linh_vuc', 'Lĩnh vực khác')),
                'do_khan_cap': int(ai_data.get('do_khan_cap', 1)),
                'ngay_gui': str(thoi_gian_hien_tai)
            }

            
            # Gửi thông báo
            # Gửi đến room của phòng đó
            # Gửi thêm cho Admin tổng (nếu cần)
            print(f"DEBUG: Đã phát thông báo thành công cho đơn ID: {new_id}")
            
        except Exception as e:
            # In lỗi ra Terminal để bạn biết tại sao thông báo không chạy
            print(f"LỖI PHÁT SOCKET: {e}")

        return render_template('submit.html', success=True)
        
    return render_template('submit.html', success=False)

# TRANG 2: Bảng giám sát dành cho công dân (Đồng bộ chuẩn xác cấu trúc unpack của monitor.html)
@app.route('/monitor')
def page_monitor():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Lấy đủ 13 cột để khớp với vòng lặp trong monitor.html
    cursor.execute("""
        SELECT pa.id, pa.noi_dung, pa.file_dinh_kem, pa.dia_chi, pa.ten_nguoi_gui, pa.sdt, 
               pa.linh_vuc, pa.sac_thai, pa.do_khan_cap, pa.trang_thai, pa.phong_ban_id, 
               pa.ngay_gui, pb.ten_phong, pa.ly_do_xoa, pa.giai_thich_xoa
        FROM phan_anh pa 
        LEFT JOIN config_phong_ban pb ON pa.phong_ban_id = pb.id 
        WHERE trang_thai_duyet != 'Cho_tiep_nhan'
        ORDER BY pa.id DESC
    """)
    list_phan_anh = cursor.fetchall()
    conn.close()
    return render_template('monitor.html', list_phan_anh=list_phan_anh)


# TRANG DASHBOARD: Tổng quan cho lãnh đạo
@app.route('/dashboard')
def page_dashboard():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # ---- FILTERS ----
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    phong_ban_id = request.args.get('phong_ban_id', '').strip()
    linh_vuc = request.args.get('linh_vuc', '').strip()

    # Parse date_from/date_to as YYYY-MM-DD (input type=date)
    def parse_ymd(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except Exception:
            return None

    d_from = parse_ymd(date_from)
    d_to = parse_ymd(date_to)
    if d_from and d_to and d_from > d_to:
        d_from, d_to = d_to, d_from

    # Build filtered id list based on ngay_gui (TEXT: "%H:%M %d/%m/%Y")
    filtered_ids = None
    if d_from or d_to:
        filtered_ids = []
        cursor.execute("SELECT id, ngay_gui FROM phan_anh WHERE ngay_gui IS NOT NULL AND TRIM(ngay_gui) != ''")
        for pa_id, ngay_gui in cursor.fetchall():
            try:
                parsed_date = datetime.strptime(str(ngay_gui).strip(), "%H:%M %d/%m/%Y").date()
            except Exception:
                continue
            if d_from and parsed_date < d_from:
                continue
            if d_to and parsed_date > d_to:
                continue
            filtered_ids.append(int(pa_id))

        # If no records in range, keep empty list => all aggregates become 0/empty

    # list dropdowns
    cursor.execute("SELECT id, ten_phong FROM config_phong_ban ORDER BY ten_phong")
    list_phong_ban = cursor.fetchall()

    cursor.execute("""SELECT DISTINCT COALESCE(NULLIF(TRIM(linh_vuc), ''), 'Chưa xác định') AS lv
                      FROM phan_anh
                      ORDER BY lv""")
    list_linh_vuc = [row[0] for row in cursor.fetchall()]

    # Helper to add common WHERE filters
    where_clauses = []
    params = []

    if phong_ban_id:
        try:
            where_clauses.append('pa.phong_ban_id = ?')
            params.append(int(phong_ban_id))
        except Exception:
            pass

    if linh_vuc:
        where_clauses.append('pa.linh_vuc = ?')
        params.append(linh_vuc)

    if filtered_ids is not None:
        # SQLite IN clause with dynamic placeholders
        if len(filtered_ids) == 0:
            where_clauses.append('1=0')
        else:
            placeholders = ','.join(['?'] * len(filtered_ids))
            where_clauses.append(f'pa.id IN ({placeholders})')
            params.extend(filtered_ids)

    common_where = ''
    if where_clauses:
        common_where = ' AND ' + ' AND '.join(where_clauses)

    # ---- KPI ----
    cursor.execute("SELECT COUNT(*) FROM phan_anh pa WHERE 1=1" + common_where, params)
    total_phan_anh = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh pa WHERE pa.trang_thai_duyet = 'Da_duyet'" + common_where, params)
    total_da_duyet = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh pa WHERE pa.trang_thai_duyet = 'Cho_tiep_nhan'" + common_where, params)
    total_cho_tiep_nhan = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh pa WHERE pa.trang_thai_duyet = 'Da_xoa'" + common_where, params)
    total_da_xoa = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh pa WHERE pa.do_khan_cap >= 4" + common_where, params)
    total_khan_cap_cao = cursor.fetchone()[0] or 0

    cursor.execute("SELECT AVG(pa.do_khan_cap) FROM phan_anh pa WHERE pa.do_khan_cap IS NOT NULL" + common_where, params)
    avg_do_khan_cap_raw = cursor.fetchone()[0]
    avg_do_khan_cap = round(avg_do_khan_cap_raw or 0, 1)

    # ---- Stats for charts ----
    cursor.execute("""
        SELECT COALESCE(NULLIF(TRIM(pa.sac_thai), ''), 'Chưa xác định') AS label, COUNT(*) AS count
        FROM phan_anh pa
        WHERE 1=1""" + common_where + """
        GROUP BY label
        ORDER BY count DESC
    """, params)
    sac_thai_stats = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(NULLIF(TRIM(pa.linh_vuc), ''), 'Chưa xác định') AS label, COUNT(*) AS count
        FROM phan_anh pa
        WHERE 1=1""" + common_where + """
        GROUP BY label
        ORDER BY count DESC
        LIMIT 8
    """, params)
    linh_vuc_stats = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(pb.ten_phong, 'Văn phòng tiếp dân') AS label, COUNT(*) AS count
        FROM phan_anh pa
        LEFT JOIN config_phong_ban pb ON pa.phong_ban_id = pb.id
        WHERE 1=1""" + common_where + """
        GROUP BY label
        ORDER BY count DESC
        LIMIT 8
    """, params)
    phong_ban_stats = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(NULLIF(TRIM(pa.trang_thai), ''), pa.trang_thai_duyet, 'Chưa xác định') AS label,
               COUNT(*) AS count
        FROM phan_anh pa
        WHERE 1=1""" + common_where + """
        GROUP BY label
        ORDER BY count DESC
    """, params)
    trang_thai_stats = cursor.fetchall()

    cursor.execute("""
        SELECT pa.id, pa.noi_dung, pa.linh_vuc, pa.do_khan_cap, pa.sac_thai, pa.ngay_gui
        FROM phan_anh pa
        WHERE pa.do_khan_cap >= 4""" + common_where + """
        ORDER BY pa.id DESC
        LIMIT 6
    """, params)
    phan_anh_khan_cap = cursor.fetchall()

    # Trend by date (use filtered_ids logic already applied by common_where, but we need labels)
    cursor.execute("""SELECT pa.ngay_gui
                      FROM phan_anh pa
                      WHERE 1=1""" + common_where + """
                      AND pa.ngay_gui IS NOT NULL AND TRIM(pa.ngay_gui) != ''""", params)
    trend_counts = {}
    for (ngay_gui,) in cursor.fetchall():
        try:
            parsed_date = datetime.strptime(str(ngay_gui).strip(), "%H:%M %d/%m/%Y")
            label = parsed_date.strftime("%d/%m")
        except Exception:
            label = str(ngay_gui)[-10:] if ngay_gui and len(str(ngay_gui)) >= 10 else ngay_gui
        trend_counts[label] = trend_counts.get(label, 0) + 1

    trend_stats = list(trend_counts.items())[-10:]

    conn.close()

    # KPI cards
    kpi_cards = [
        {"label": "Tổng phản ánh", "value": total_phan_anh, "tone": "blue"},
        {"label": "Đã duyệt", "value": total_da_duyet, "tone": "emerald"},
        {"label": "Chờ tiếp nhận", "value": total_cho_tiep_nhan, "tone": "amber"},
        {"label": "Khẩn cấp cao", "value": total_khan_cap_cao, "tone": "red"},
        {"label": "Đã xóa", "value": total_da_xoa, "tone": "slate"},
        {"label": "Độ khẩn TB", "value": avg_do_khan_cap, "tone": "indigo"},
    ]

    return render_template(
        'dashboard.html',
        kpi_cards=kpi_cards,
        sac_thai_stats=sac_thai_stats,
        linh_vuc_stats=linh_vuc_stats,
        phong_ban_stats=phong_ban_stats,
        trang_thai_stats=trang_thai_stats,
        trend_stats=trend_stats,
        phan_anh_khan_cap=phan_anh_khan_cap,
        list_phong_ban=list_phong_ban,
        list_linh_vuc=list_linh_vuc,
    )

    


    cursor.execute("SELECT COUNT(*) FROM phan_anh")
    total_phan_anh = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh WHERE trang_thai_duyet = 'Da_duyet'")
    total_da_duyet = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh WHERE trang_thai_duyet = 'Cho_tiep_nhan'")
    total_cho_tiep_nhan = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh WHERE trang_thai_duyet = 'Da_xoa'")
    total_da_xoa = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM phan_anh WHERE do_khan_cap >= 4")
    total_khan_cap_cao = cursor.fetchone()[0] or 0

    cursor.execute("SELECT AVG(do_khan_cap) FROM phan_anh WHERE do_khan_cap IS NOT NULL")
    avg_do_khan_cap_raw = cursor.fetchone()[0]
    avg_do_khan_cap = round(avg_do_khan_cap_raw or 0, 1)

    cursor.execute("""
        SELECT COALESCE(NULLIF(TRIM(sac_thai), ''), 'Chưa xác định') AS label, COUNT(*) AS count
        FROM phan_anh
        GROUP BY label
        ORDER BY count DESC
    """)
    sac_thai_stats = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(NULLIF(TRIM(linh_vuc), ''), 'Chưa xác định') AS label, COUNT(*) AS count
        FROM phan_anh
        GROUP BY label
        ORDER BY count DESC
        LIMIT 8
    """)
    linh_vuc_stats = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(pb.ten_phong, 'Văn phòng tiếp dân') AS label, COUNT(*) AS count
        FROM phan_anh pa
        LEFT JOIN config_phong_ban pb ON pa.phong_ban_id = pb.id
        GROUP BY label
        ORDER BY count DESC
        LIMIT 8
    """)
    phong_ban_stats = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(NULLIF(TRIM(trang_thai), ''), trang_thai_duyet, 'Chưa xác định') AS label,
               COUNT(*) AS count
        FROM phan_anh
        GROUP BY label
        ORDER BY count DESC
    """)
    trang_thai_stats = cursor.fetchall()

    cursor.execute("""
        SELECT id, noi_dung, linh_vuc, do_khan_cap, sac_thai, ngay_gui
        FROM phan_anh
        WHERE do_khan_cap >= 4
        ORDER BY id DESC
        LIMIT 6
    """)
    phan_anh_khan_cap = cursor.fetchall()

    cursor.execute("SELECT ngay_gui FROM phan_anh WHERE ngay_gui IS NOT NULL AND TRIM(ngay_gui) != ''")
    trend_counts = {}
    for (ngay_gui,) in cursor.fetchall():
        try:
            parsed_date = datetime.strptime(ngay_gui.strip(), "%H:%M %d/%m/%Y")
            label = parsed_date.strftime("%d/%m")
        except Exception:
            label = ngay_gui[-10:] if len(ngay_gui) >= 10 else ngay_gui
        trend_counts[label] = trend_counts.get(label, 0) + 1

    trend_stats = list(trend_counts.items())[-10:]

    conn.close()

    kpi_cards = [
        {"label": "Tổng phản ánh", "value": total_phan_anh, "tone": "blue"},
        {"label": "Đã duyệt", "value": total_da_duyet, "tone": "emerald"},
        {"label": "Chờ tiếp nhận", "value": total_cho_tiep_nhan, "tone": "amber"},
        {"label": "Khẩn cấp cao", "value": total_khan_cap_cao, "tone": "red"},
        {"label": "Đã xóa", "value": total_da_xoa, "tone": "slate"},
        {"label": "Độ khẩn TB", "value": avg_do_khan_cap, "tone": "indigo"},
    ]

    return render_template(
        'dashboard.html',
        kpi_cards=kpi_cards,
        sac_thai_stats=sac_thai_stats,
        linh_vuc_stats=linh_vuc_stats,
        phong_ban_stats=phong_ban_stats,
        trang_thai_stats=trang_thai_stats,
        trend_stats=trend_stats,
        phan_anh_khan_cap=phan_anh_khan_cap
    )

# TRANG 3: Trang quản trị điều phối (Đồng bộ chuẩn xác cấu trúc unpack của admin.html)
@app.route('/admin', methods=['GET', 'POST'])
def page_admin():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    message = None
    msg_type = None  # 'success' | 'error'

    allowed_trang_thai = {'Chờ xử lý', 'Đang xử lý', 'Đã hoàn thành', 'Chuyển cấp', 'Trả về'}
    allowed_ly_do_xoa = {'Phản ánh bị trùng', 'Không thuộc phạm vi giải quyết'}

    if request.method == 'POST':
        try:
            action = request.form.get('action', 'update')
            pa_id = request.form['pa_id']

            if action == 'delete':
                ly_do_xoa = request.form.get('ly_do_xoa', '').strip()
                giai_thich_xoa = request.form.get('giai_thich_xoa', '').strip()

                if ly_do_xoa not in allowed_ly_do_xoa:
                    raise ValueError('Lý do xóa không hợp lệ')
                if not giai_thich_xoa:
                    raise ValueError('Vui lòng nhập giải thích khi xóa phản ánh')

                ngay_xoa = datetime.now().strftime("%H:%M %d/%m/%Y")
                cursor.execute(
                    """
                    UPDATE phan_anh
                    SET trang_thai_duyet = 'Da_xoa',
                        trang_thai = ?,
                        ly_do_xoa = ?,
                        giai_thich_xoa = ?,
                        ngay_xoa = ?
                    WHERE id = ?
                    """,
                    (ly_do_xoa, ly_do_xoa, giai_thich_xoa, ngay_xoa, pa_id)
                )
                conn.commit()

                message = 'Đã xóa phản ánh khỏi danh sách xử lý và lưu giải thích.'
                msg_type = 'success'
            else:
                phong_ban_moi = request.form.get('phong_ban_id', '')
                trang_thai_moi = request.form.get('trang_thai', '')

                if not trang_thai_moi or trang_thai_moi not in allowed_trang_thai:
                    raise ValueError('Trạng thái không hợp lệ')

                p_ban_value = None if phong_ban_moi == "" else int(phong_ban_moi)

                cursor.execute(
                    "UPDATE phan_anh SET phong_ban_id = ?, trang_thai = ? WHERE id = ?",
                    (p_ban_value, trang_thai_moi, pa_id)
                )
                conn.commit()

                message = 'Cập nhật thành công.'
                msg_type = 'success'
        except Exception as e:
            message = f'Không thể cập nhật: {e}'
            msg_type = 'error'

    selected_phong_id = request.args.get('phong_id', type=int)


    # 🔥 ĐỒNG BỘ FIX LỖI VALUEERROR UNPACK: SELECT ra đúng thứ tự các cột mà file admin.html đang dùng lặp
# Sửa lại câu lệnh SQL chuẩn
    sql_query = """
        SELECT pa.id, pa.noi_dung, pa.file_dinh_kem, pa.dia_chi, pa.ten_nguoi_gui, 
               pa.sdt, pa.linh_vuc, pa.sac_thai, pa.do_khan_cap, pa.trang_thai, 
               pa.phong_ban_id, pa.ngay_gui
        FROM phan_anh pa
        LEFT JOIN config_phong_ban pb ON pa.phong_ban_id = pb.id
        WHERE pa.trang_thai_duyet NOT IN ('Cho_tiep_nhan', 'Da_xoa')
    """
                   
    if selected_phong_id:
        cursor.execute(sql_query + " AND phong_ban_id = ? ORDER BY pa.id DESC", (selected_phong_id,))
    else:
        cursor.execute(sql_query + " ORDER BY pa.id DESC")
        
    list_phan_anh = cursor.fetchall()
    
    cursor.execute("SELECT id, ten_phong FROM config_phong_ban")
    list_phong_ban = cursor.fetchall()
    conn.close()
    
    return render_template('admin.html', list_phan_anh=list_phan_anh, list_phong_ban=list_phong_ban, selected_phong_id=selected_phong_id, message=message, msg_type=msg_type)

from flask_socketio import join_room


def _emit_badge_counts():
    """Gửi lại số lượng 'Cho_tiep_nhan' theo từng phòng để tránh bị lệch/bỏ lỡ event."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""SELECT phong_ban_id, COUNT(*) AS cnt
                          FROM phan_anh
                          WHERE trang_thai_duyet = '__admin_badge_disabled__'
                          GROUP BY phong_ban_id""")
        rows = cursor.fetchall()

        counts_by_phong = {}
        for phong_ban_id, cnt in rows:
            pid = int(phong_ban_id) if phong_ban_id is not None else 0
            counts_by_phong[str(pid)] = int(cnt)

        pass
    finally:
        conn.close()


@socketio.on('join_room')
def handle_join_room(data):
    phong_id = data.get('phong_id')

    # 1. Nếu là Admin (phong_id là 'admin' hoặc không có) -> Vào room tổng
    if phong_id == 'admin' or phong_id is None:
        join_room('admin_tong')
        print("Đã gia nhập room: admin_tong")

        # Đồng bộ badge cho admin tổng khi vừa join
        try:
            pass
        except Exception as e:
            print(f"LỖI SYNC BADGE TRONG join_room(admin_tong): {e}")

    # 2. Nếu là Cán bộ phòng (phong_id là số) -> Vào room phòng đó
    else:
        join_room(f'phong_{phong_id}')
        print(f"Cán bộ đã vào phòng: phong_{phong_id}")


@app.route('/maps')
def page_maps():
    return render_template('maps.html')


@app.route('/treemap')
def page_treemap():
    return render_template('treemap.html')


@app.route('/api/phan_anh/treemap')
def api_treemap():
    """Trả về dữ liệu treemap theo grid-based district (parent) và dia_chi (child).

    Quy ước:
    - parent: district_id (ô grid theo lat/lng) nhưng được ánh xạ sang nhóm mức màu
    - child: dia_chi (khu vực cụ thể) trong từng district

    Query params hỗ trợ: date_from, date_to (YYYY-MM-DD), linh_vuc, phong_ban_id
    """

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    linh_vuc = request.args.get('linh_vuc', '').strip()
    phong_ban_id = request.args.get('phong_ban_id', '').strip()

    def parse_ymd(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except Exception:
            return None

    d_from = parse_ymd(date_from)
    d_to = parse_ymd(date_to)
    if d_from and d_to and d_from > d_to:
        d_from, d_to = d_to, d_from

    where = []
    params = []

    if linh_vuc:
        where.append('linh_vuc = ?')
        params.append(linh_vuc)

    if phong_ban_id:
        try:
            where.append('phong_ban_id = ?')
            params.append(int(phong_ban_id))
        except Exception:
            pass

    filtered_ids = None
    if d_from or d_to:
        filtered_ids = []
        cursor.execute("SELECT id, ngay_gui FROM phan_anh WHERE ngay_gui IS NOT NULL AND TRIM(ngay_gui) != ''")
        for pa_id, ngay_gui in cursor.fetchall():
            try:
                parsed_date = datetime.strptime(str(ngay_gui).strip(), "%H:%M %d/%m/%Y").date()
            except Exception:
                continue
            if d_from and parsed_date < d_from:
                continue
            if d_to and parsed_date > d_to:
                continue
            filtered_ids.append(int(pa_id))

        if len(filtered_ids) == 0:
            where.append('1=0')
        else:
            placeholders = ','.join(['?'] * len(filtered_ids))
            where.append(f'id IN ({placeholders})')
            params.extend(filtered_ids)

    common_where = ' AND '.join(where) if where else '1=1'

    GRID_SIZE = 0.1  # ~1km theo dữ liệu vĩ độ hiện tại

    cursor.execute(f"""
        SELECT id, TRIM(dia_chi) AS dia_chi, lat, lng
        FROM phan_anh
        WHERE {common_where}
          AND dia_chi IS NOT NULL
          AND TRIM(dia_chi) != ''
          AND lat IS NOT NULL
          AND lng IS NOT NULL
    """, params)
    rows = cursor.fetchall()
    conn.close()

    def make_district_id(lat_f: float, lng_f: float) -> str:
        try:
            lat_i = int((lat_f // GRID_SIZE))
            lng_i = int((lng_f // GRID_SIZE))
        except Exception:
            return 'Chưa xác định'
        return f"grid_{lat_i}_{lng_i}"

    counts_by_district = {}  # district_id -> total count
    counts_by_unit_in_district = {}  # district_id -> {dia_chi: count}

    for _, dia_chi, lat, lng in rows:
        unit = (dia_chi or '').strip()
        if not unit:
            continue
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except Exception:
            continue

        district_id = make_district_id(lat_f, lng_f)

        counts_by_district[district_id] = counts_by_district.get(district_id, 0) + 1
        if district_id not in counts_by_unit_in_district:
            counts_by_unit_in_district[district_id] = {}
        counts_by_unit_in_district[district_id][unit] = (
            counts_by_unit_in_district[district_id].get(unit, 0) + 1
        )

    items_district = sorted(counts_by_district.items(), key=lambda x: x[1], reverse=True)
    total_districts = len(items_district)

    if total_districts == 0:
        result = {'parents': [], 'children': [], 'raw': {'total_units': 0}}
        return app.response_class(
            response=json.dumps(result, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )

    # Phân loại mức theo percentile dựa trên số lượng district
    idx_top20 = max(0, int(total_districts * 0.20) - 1)
    idx_top50 = max(idx_top20 + 1, int(total_districts * 0.50) - 1)

    threshold_very = items_district[idx_top20][1] if idx_top20 < total_districts else items_district[-1][1]
    threshold_high = items_district[idx_top50][1] if idx_top50 < total_districts else items_district[-1][1]

    def classify(n: int) -> str:
        if n >= threshold_very:
            return 'Số lượng PAKN rất cao'
        if n >= threshold_high:
            return 'Số lượng PAKN cao'
        return 'Số lượng PAKN trung bình'

    color_map = {
        'Số lượng PAKN rất cao': '#ef4444',
        'Số lượng PAKN cao': '#f59e0b',
        'Số lượng PAKN trung bình': '#22c55e',
    }

    # Treemap hiện có yêu cầu: parents là 3 nhóm mức độ; children có parent = name nhóm mức độ
    parents = {}
    children = []

    for district_id, district_count in items_district:
        level = classify(district_count)
        if level not in parents:
            parents[level] = {
                'name': level,
                'value': 0,
                'color': color_map.get(level, '#2563eb')
            }
        parents[level]['value'] += district_count

        unit_map = counts_by_unit_in_district.get(district_id, {})
        for unit_name, unit_count in sorted(unit_map.items(), key=lambda x: x[1], reverse=True):
            children.append({
                'name': unit_name,
                'value': unit_count,
                'parent': level,
                'color': color_map.get(level, '#2563eb'),
            })

    result = {
        'parents': list(parents.values()),
        'children': children,
        'raw': {
            'total_units': sum(counts_by_district.values()),
            'total_districts': total_districts,
            'top_threshold_very': threshold_very,
            'top_threshold_high': threshold_high,
            'grid_size': GRID_SIZE,
        }
    }

    return app.response_class(
        response=json.dumps(result, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )



@app.route('/api/phan_anh/points')
def api_points():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    linh_vuc = request.args.get('linh_vuc', '').strip()
    phong_ban_id = request.args.get('phong_ban_id', '').strip()

    def parse_ymd(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except Exception:
            return None

    d_from = parse_ymd(date_from)
    d_to = parse_ymd(date_to)
    if d_from and d_to and d_from > d_to:
        d_from, d_to = d_to, d_from

    where = ['lat IS NOT NULL', 'lng IS NOT NULL']
    params = []

    if linh_vuc:
        where.append('linh_vuc = ?')
        params.append(linh_vuc)

    if phong_ban_id:
        try:
            where.append('phong_ban_id = ?')
            params.append(int(phong_ban_id))
        except Exception:
            pass

    filtered_ids = None
    if d_from or d_to:
        filtered_ids = []
        cursor.execute("SELECT id, ngay_gui FROM phan_anh WHERE ngay_gui IS NOT NULL AND TRIM(ngay_gui) != ''")
        for pa_id, ngay_gui in cursor.fetchall():
            try:
                parsed_date = datetime.strptime(str(ngay_gui).strip(), "%H:%M %d/%m/%Y").date()
            except Exception:
                continue
            if d_from and parsed_date < d_from:
                continue
            if d_to and parsed_date > d_to:
                continue
            filtered_ids.append(int(pa_id))

        if filtered_ids is not None:
            if len(filtered_ids) == 0:
                where.append('1=0')
            else:
                placeholders = ','.join(['?'] * len(filtered_ids))
                where.append(f'id IN ({placeholders})')
                params.extend(filtered_ids)

    common_where = ' AND '.join(where) if where else '1=1'

    # Giới hạn bbox Việt Nam để tránh vẽ điểm từ ngoài nước
    # (lat: ~8..24.5, lng: ~102..110)
    vn_bbox_where = "(pa.lat BETWEEN 8 AND 24.5 AND pa.lng BETWEEN 102 AND 110)"

    cursor.execute(f"""
        SELECT pa.id, pa.noi_dung, pa.dia_chi, pa.linh_vuc, pa.sac_thai, pa.do_khan_cap,
               pa.ngay_gui, pa.lat, pa.lng,
               pa.phong_ban_id, pb.ten_phong
        FROM phan_anh pa
        LEFT JOIN config_phong_ban pb ON pa.phong_ban_id = pb.id
        WHERE {common_where} AND {vn_bbox_where}
        ORDER BY pa.id DESC
    """, params)


    rows = cursor.fetchall()
    conn.close()

    points = []
    for (pa_id, noi_dung, dia_chi, lv, sac_thai, do_khan_cap, ngay_gui, lat, lng, pb_id, ten_phong) in rows:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except Exception:
            continue

        points.append({
            'id': pa_id,
            'noi_dung': noi_dung or '',
            'dia_chi': dia_chi or '',
            'linh_vuc': lv or '',
            'sac_thai': sac_thai or '',
            'do_khan_cap': int(do_khan_cap) if do_khan_cap is not None else 1,
            'ngay_gui': ngay_gui or '',
            'lat': lat_f,
            'lng': lng_f,
            'phong_ban_id': pb_id if pb_id is not None else 0,
            'ten_phong': ten_phong or ''
        })

    return app.response_class(
        response=json.dumps(points, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )


@app.route('/tiep_nhan')
def page_tiep_nhan():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Dùng LEFT JOIN để tự động lấy tên phòng ban dựa trên linh_vuc AI đã phân tích
    cursor.execute("""
        SELECT p.id, p.noi_dung, p.linh_vuc, p.do_khan_cap, p.trang_thai_duyet, pb.ten_phong, pb.id 
        FROM phan_anh p
        LEFT JOIN config_phong_ban pb ON p.linh_vuc = pb.linh_vuc_phu_trach
        WHERE p.trang_thai_duyet = 'Cho_tiep_nhan' 
        ORDER BY p.id DESC
    """)
    list_cho_tiep_nhan = cursor.fetchall()
    
    conn.close()
    
    # Không cần list_phong_ban nữa vì AI đã tự chọn xong!
    return render_template('tiep_nhan.html', list_cho_tiep_nhan=list_cho_tiep_nhan)
@app.route('/duyet_ho_so', methods=['POST'])
def duyet_ho_so():
    pa_id = request.form.get('pa_id')
    phong_ban_duyet = request.form.get('phong_ban_duyet')
    linh_vuc_duyet = request.form.get('linh_vuc_duyet')
    do_khan_duyet = request.form.get('do_khan_duyet')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Cập nhật kết quả cuối cùng do con người quyết định
    cursor.execute("""
        UPDATE phan_anh 
        SET phong_ban_id = ?, linh_vuc = ?, do_khan_cap = ?, 
            trang_thai_duyet = 'Da_duyet'
        WHERE id = ?
    """, (phong_ban_duyet, linh_vuc_duyet, do_khan_duyet, pa_id))

    cursor.execute("""
        SELECT pa.id, pa.noi_dung, pa.linh_vuc, pa.do_khan_cap, pa.phong_ban_id,
               pa.ngay_gui, pb.ten_phong
        FROM phan_anh pa
        LEFT JOIN config_phong_ban pb ON pa.phong_ban_id = pb.id
        WHERE pa.id = ?
    """, (pa_id,))
    approved_row = cursor.fetchone()
    
    # ---- Socket update badge cho trang admin ----
    # Sau khi duyệt, cần re-sync số lượng đơn CHỜ theo từng phòng để badge không bị lệch/mất.
    try:
        # Đếm số đơn đang ở trạng thái "Cho_tiep_nhan" theo từng phòng ban
        cursor.execute("""SELECT phong_ban_id, COUNT(*) AS cnt
                          FROM phan_anh
                          WHERE trang_thai_duyet = '__admin_badge_disabled__'
                          GROUP BY phong_ban_id""")
        rows = cursor.fetchall()

        counts_by_phong = {}
        for phong_ban_id, cnt in rows:
            # phòng_ban_id có thể null -> map về 0
            pid = int(phong_ban_id) if phong_ban_id is not None else 0
            counts_by_phong[str(pid)] = int(cnt)

    # Gửi cho tất cả admin đang mở (room tổng)
        socketio.emit('badge_update_from_db', {'counts_by_phong': counts_by_phong}, room='admin_tong')
    except Exception as e:
        print(f"LỖI SYNC BADGE: {e}")

    conn.commit()
    conn.close()

    if approved_row:
        don_id, noi_dung, linh_vuc, do_khan_cap, phong_ban_id, ngay_gui, ten_phong = approved_row
        # Kiểm tra nếu là None (kiểu dữ liệu) HOẶC là chuỗi "None"
        if phong_ban_id is None or phong_ban_id == 'None' or phong_ban_id == '':
           safe_phong_id = 0
        else:
           safe_phong_id = int(phong_ban_id)    
        payload = {
            'id': int(don_id),
            'phong_ban_id': safe_phong_id,
            'ten_phong': str(ten_phong or ''),
            'noi_dung': str(noi_dung or ''),
            'linh_vuc': str(linh_vuc or ''),
            'do_khan_cap': int(do_khan_cap or 1),
            'ngay_gui': str(ngay_gui or '')
        }
        socketio.emit('thong_bao_don_moi', payload, room=f'phong_{safe_phong_id}')
        socketio.emit('thong_bao_don_moi', payload, room='admin_tong')

    return redirect(url_for('page_tiep_nhan'))




if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)





