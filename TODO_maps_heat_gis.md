# TODO - Bản đồ nhiệt & GIS (Heatmap + Leaflet + API điểm)

## Phase A - Chuẩn bị data (DB + geocode)
- [ ] A1: Update `init_db()` thêm migration cột `lat`, `lng` cho table `phan_anh`.
- [ ] A2: Update route `/submit` gọi Nominatim geocode `dia_chi` → lưu `lat/lng` (timeout + User-Agent). Nếu lỗi → NULL.

## Phase B - Backend API + trang `/maps`
- [ ] B1: Tạo route `GET /api/phan_anh/points` trả JSON điểm (chỉ lat/lng != NULL) + filter (date_from/date_to/linh_vuc/phong_ban_id).
- [ ] B2: Tạo route `GET /maps` render template `templates/maps.html`.

## Phase C - Frontend Leaflet
- [ ] C1: Sửa `templates/maps.html` hiển thị Leaflet map + marker + heatmap.
- [ ] C2: Thêm popup cho marker, weight heatmap theo `do_khan_cap`.

## Phase D - Điều hướng
- [ ] D1: Update `templates/layout.html` thêm link menu tới `/maps`.

## Phase E - Test
- [ ] E1: Chạy server, submit 3 phản ánh có địa chỉ rõ → kiểm tra marker + heatmap.
- [ ] E2: Kiểm tra filter API qua query string trên `/maps` (nếu có UI lọc).

