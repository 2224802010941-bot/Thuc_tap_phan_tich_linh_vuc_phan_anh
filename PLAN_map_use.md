# Plan: Bật Map/GIS (Leaflet + marker + heatmap)

## Information Gathered
- `app.py` hiện chưa có route `/maps` và chưa có API trả điểm lat/lng.
- `templates/maps.html` đang ở trạng thái rollback (không hiển thị Leaflet).
- `TODO_maps_fix.md` và `TODO_maps_heat_gis.md` cho thấy dự kiến tích hợp GIS bằng Leaflet + heatmap + API points.
- DB table `phan_anh` có cột `lat`, `lng` (đã có migration một phần trong `init_db()`).
- `route /submit` hiện đã geocode dia_chi → lat/lng nhưng code chỉ insert `lat_val/lng_val` (chưa có endpoint để frontend dùng).

## Plan
### File: app.py
1. Thêm route `GET /maps` render `templates/maps.html`.
2. Thêm route `GET /api/phan_anh/points` trả JSON danh sách điểm:
   - Chỉ lấy các bản ghi có `lat IS NOT NULL AND lng IS NOT NULL`.
   - Filter qua query params (nếu có): `date_from`, `date_to`, `linh_vuc`, `phong_ban_id`.
   - Mỗi điểm: `{id, lat, lng, do_khan_cap, linh_vuc, dia_chi, noi_dung, ten_phong, sac_thai, ngay_gui}`.
3. (Nếu cần) Parse `date_from/date_to` giống logic dashboard để lọc theo `ngay_gui`.

### File: templates/maps.html
4. Thay nội dung rollback bằng trang Leaflet:
   - Import Leaflet CSS/JS (CDN).
   - Tải Heatmap plugin (ví dụ leaflet.heat) từ CDN.
   - Gọi fetch `/api/phan_anh/points` và vẽ marker + heatmap.
   - Weight heatmap theo `do_khan_cap` (ví dụ weight = do_khan_cap).
   - Popup marker hiển thị `noi_dung`, `linh_vuc`, `do_khan_cap`, `dia_chi`.

### File: templates/layout.html
5. Thêm link menu tới `/maps`.

## Dependent Files to be edited
- `app.py`
- `templates/maps.html`
- `templates/layout.html`

## Followup steps
- Chạy `python app.py` và mở `/maps`.
- Submit vài phản ánh có địa chỉ rõ → kiểm tra marker/heatmap.
- Kiểm tra filter trên `/api/phan_anh/points` (nếu có UI lọc).

<ask_followup_question>
Xác nhận trước khi mình bắt đầu edit: bạn muốn hiển thị heatmap luôn (không cần UI filter), hay thêm UI filter đơn giản trên trang /maps (date_from/date_to/linh_vuc/phòng ban)?
</ask_followup_question>

