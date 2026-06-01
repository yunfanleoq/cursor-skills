@echo off
cd /d "%~dp0"
if not exist "config.json" (
  copy "config.example.json" "config.json"
  echo 已创建 config.json，请编辑 api_key 后重启
)
pip install -r requirements.txt -q
python app.py
