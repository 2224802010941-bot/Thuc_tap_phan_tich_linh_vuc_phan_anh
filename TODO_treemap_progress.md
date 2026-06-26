# TODO Treemap - Progress

- [x] Nắm cấu trúc treemap hiện tại (`templates/treemap.html`) và endpoint (`/api/phan_anh/treemap`).
- [x] Xác định nhu cầu bổ sung: gom theo **huyện/quận/thành phố cấp huyện** để giảm trùng lặp phường/xã.
- [x] Xác nhận cấu trúc hiển thị: **2 cấp** (District -> Nhóm mức độ -> Unit) (mức độ theo district).
- [x] B1: Backend `app.py`: thêm hàm trích xuất district từ `dia_chi`.




- [ ] B2: Backend `app.py`: sửa `/api/phan_anh/treemap` trả về `districts` + `units` + phân loại mức theo district.
- [ ] B3: Frontend `templates/treemap.html`: cập nhật render treemap theo 2 cấp mới.
- [ ] B4: Cập nhật panel “Chi tiết” hiển thị thêm district + mức độ.
- [ ] B5: Chạy thử `/treemap` với vài bộ lọc và kiểm tra trường hợp `Chưa xác định`.


