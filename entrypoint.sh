#!/bin/sh
set -e

# Xóa stale lock/socket của Xvfb còn sót từ lần chạy trước.
# Docker --restart giữ nguyên filesystem container nên các file này tích lũy.
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# Khởi động Xvfb virtual display
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp &

# Chờ Xvfb bind socket (tăng lên 2s để đảm bảo trên máy chậm)
sleep 2

# exec thay thế shell process bằng python.
# tini (PID 1) sẽ forward SIGTERM trực tiếp đến python → cleanup đúng.
# exec python main.py
exec python main_play.py
