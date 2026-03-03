#!/usr/bin/env python3
"""systemdサービスファイルを正しく書き直すスクリプト"""

SERVICE = """\
[Unit]
Description=Station Studio Streamlit App
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/station-studio
ExecStart=/opt/station-studio/venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

path = "/etc/systemd/system/station-studio.service"
with open(path, "w") as f:
    f.write(SERVICE)
print(f"Written: {path}")
