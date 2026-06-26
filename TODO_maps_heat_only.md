# TODO - Heatmap-only theo yêu cầu (linh_vuc sort desc)

## Step 1: app.py (Backend)
- [ ] 1.1 Thêm endpoint `GET /api/phan_anh/stats-by-area`
      - Lấy `linh_vuc`, `COUNT(*)`
      - Sort giảm dần theo count
      - Filter theo `date_from`, `date_to`, `linh_vuc`, `phong_ban_id` (giống `/api/phan_anh/points`)

## Step 2: templates/maps.html (Frontend)
- [ ] 2.1 Thêm UI toggle 2 nút: `Bản đồ nhiệt` và `GIS`
- [ ] 2.2 Mode `Bản đồ nhiệt`:
      - Tắt marker (không render/clear marker)
      - Chỉ giữ `heatLayer`
- [ ] 2.3 Hiển thị legend/bảng nhỏ `Khu vực theo số lượng phản ánh`
      - Fetch từ `/api/phan_anh/stats-by-area`
      - Render list sorted desc

## Step 3: Verify
- [ ] 3.1 Mở `/maps`, bấm “Bản đồ nhiệt” thấy heatmap + legend sorted đúng
- [ ] 3.2 Bấm “GIS” chuyển chế độ hiển thị marker như cũ

