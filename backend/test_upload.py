# -*- coding: utf-8 -*-
"""端到端验证：登录 → 上传图片（1x1 PNG）→ 返回 OSS 签名 URL。"""
import io
import sys
import requests

BASE = "http://127.0.0.1:8000"

# 1) 登录拿 token
r = requests.post(f"{BASE}/api/auth/login", json={"username": "demo", "password": "123456"}, timeout=15)
r.raise_for_status()
token = r.json()["token"]
print("login OK")

# 2) 上传 1x1 PNG
png = bytes.fromhex(
    '89504e470d0a1a0a0000000d494844520000000100000001080600000'
    '01f15c4890000000d49444154789c626001000000ffff030000060005'
    '57bfabd40000000049454e44ae426082'
)
files = {"file": ("probe.png", io.BytesIO(png), "image/png")}
headers = {"Authorization": f"Bearer {token}"}
r = requests.post(f"{BASE}/api/upload", headers=headers, files=files, timeout=30)
r.raise_for_status()
data = r.json()
print("upload OK")
print("object_key:", data["object_key"])
print("url:", data["url"])

# 3) 用签名 URL 回读图片，确认可访问
r = requests.get(data["url"], timeout=30)
r.raise_for_status()
print("signed url GET:", r.status_code, "bytes:", len(r.content))
sys.stdout.flush()
