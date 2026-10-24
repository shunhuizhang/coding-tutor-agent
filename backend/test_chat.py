# -*- coding: utf-8 -*-
"""最终验证：报错类问题全链路（搜索 + 引用提取）+ 概念类问题耗时。"""
import time

import requests

BASE = "http://127.0.0.1:8000"

login = requests.post(f"{BASE}/api/auth/login", json={"username": "demo", "password": "123456"}, timeout=15)
token = login.json()["token"]

cases = [
    "Python 报错 TypeError: 'NoneType' object is not subscriptable 是什么意思？怎么解决？",
    "什么是闭包？用简单例子说明",
]
for q in cases:
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/chat",
        json={"message": q},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    dt = time.time() - t0
    data = r.json()
    print(f"\n问题: {q[:30]}...")
    print(f"耗时: {dt:.1f} 秒 | 答案: {len(data['answer'])} 字符 | 引用: {len(data['citations'])} 条")
    for u in data["citations"][:3]:
        print("   -", u)
    print("回答开头:", data["answer"][:120].replace("\n", " "))
