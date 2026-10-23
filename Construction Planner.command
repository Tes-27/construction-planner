#!/bin/zsh
# Mac: ดับเบิลคลิกเพื่อเปิดโปรแกรม (ปิดหน้าต่าง Terminal = ปิดโปรแกรม)
#   ./"Construction Planner.command" machi --lan   → เปิดโครงการอื่น / ให้มือถือในวง Wi-Fi เข้าได้
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "[setup] สร้าง .venv ..."
  python3 -m venv .venv || { echo "ไม่พบ python3 — ติดตั้งจาก https://www.python.org/downloads/"; exit 1; }
fi
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt || exit 1
( sleep 2; open "http://localhost:5070" ) &
.venv/bin/python app/server.py "${1:-machi-demo}" $2
