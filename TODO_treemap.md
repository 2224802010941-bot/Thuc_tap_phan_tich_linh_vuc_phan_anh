# TODO - Treemap (Bản đồ cây)

- [ ] 1. Backend: thêm route `GET /api/phan_anh/treemap` trả dữ liệu tổng hợp theo (phường/xã -> số lượng) + phân loại mức (rất cao/cao/trung bình) + màu
- [ ] 2. Backend: thêm route `GET /treemap` render template `templates/treemap.html`
- [ ] 3. Frontend: tạo `templates/treemap.html` vẽ Treemap bằng HTML/CSS/JS (không cần thư viện nặng)
- [ ] 4. Frontend Treemap: hover + click mở popup/side panel hiển thị danh sách phường/xã hoặc lọc theo mức
- [ ] 5. Điều hướng: cập nhật `templates/maps.html` (hoặc `layout.html`) để có UI “bấm chọn bản đồ” (Treemap ↔ GIS)
- [ ] 6. Chạy test: mở `/treemap`, thử filter theo `date_from/date_to/linh_vuc/phong_ban_id` (nếu có form)
- [ ] 7. Xử lý trường hợp không có dữ liệu: hiển thị trạng thái trống

