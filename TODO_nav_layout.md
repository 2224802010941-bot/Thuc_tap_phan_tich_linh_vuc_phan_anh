# TODO - Căn chỉnh Nav trong `templates/layout.html`

- [ ] Mở `templates/layout.html` và xác định phần `<nav>` hiện tại.
- [ ] Thay cụm menu `space-x-6` bằng `gap-*` + padding/hight thống nhất để căn đẹp hơn.
- [ ] Thêm `whitespace-nowrap` cho các link để tránh xuống dòng lộn xộn.
- [ ] (Desktop) thêm style `active` dựa trên `request.path` để nhìn rõ trang đang mở.
- [ ] Giữ nguyên responsive mặc định (không dùng hamburger), chỉ tối ưu desktop alignment.
- [ ] Test nhanh bằng cách mở các trang: /submit, /monitor, dashboard, /maps, /admin để kiểm tra active state và spacing.
