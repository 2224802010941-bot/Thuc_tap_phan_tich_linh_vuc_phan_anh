# TODO - Fix bản đồ chưa có dữ liệu (GIS)

## Bước 1: Thêm geocode khi submit
- [ ] Cập nhật `init_db()` bảo đảm cột `lat/lng` tồn tại (đã có migration một phần trong code hiện tại).
- [ ] Cập nhật route `/submit`: gọi Nominatim để geocode `dia_chi` → `(lat,lng)`.
- [ ] Update `phan_anh.lat/lng` sau khi insert.
- [ ] Thêm timeout + fallback: nếu geocode thất bại thì để NULL.

## Bước 2: Kiểm tra /api_points
- [ ] Mở `/maps`, kiểm tra API trả về điểm.
- [ ] Submit 1 hồ sơ mới có địa chỉ rõ ràng → kiểm tra DB `lat/lng` khác NULL.

## Bước 3: Bảo vệ hệ thống
- [ ] Thêm cơ chế throttle cơ bản (tuỳ chọn) để tránh gọi Nominatim quá dồn.
- [ ] Thêm header User-Agent phù hợp khi gọi Nominatim.

