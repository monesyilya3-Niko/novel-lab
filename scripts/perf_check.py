#!/usr/bin/env python3
"""novel-lab 性能 / 边界可复现检查（跑在隔离服务上）。

用法（推荐）:  ./scripts/perf_isolated.sh
手动用法    :  python3 scripts/perf_check.py --base-url http://127.0.0.1:18081 --server-pid <PID>

用例（全部只用标准库，跑在隔离副本服务上，真实状态零写入）:
  T1 并发读    20 并发 GET /api/overview        → avg / p99 / max 延迟
  T2 并发写    10 并发上传不同书籍              → 全部 200 且 total_books +10
  T3 100MB 上传 真实 100MB multipart 上传       → 200；采样服务端进程 RSS 峰值
  T4 超限拒绝  Content-Length = 100MB+1         → 413 立即拒绝（不读 body）
  T5 调用超时  黑洞 TCP + timeout=2 的模型      → 批次失败且 last_error 含 timeout

输出 JSON（stdout），exit 0 = 全部通过。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import http.client
import json
import math
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request

MAX_UPLOAD = 100 * 1024 * 1024  # 与 router._MAX_UPLOAD_BYTES 同值（边界测试不断言源码常量，只测行为）


def _req(base, method, path, data=None, headers=None, timeout=60):
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "replace"))


def build_multipart(file_bytes: bytes, filename: str):
    boundary = "----e2eperfboundary1234"
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{filename}\"\r\nContent-Type: text/plain\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    body = head + file_bytes + tail
    return body, f"multipart/form-data; boundary={boundary}"


def server_rss_kb(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


class RssSampler:
    """后台采样服务端 RSS，记录峰值。"""

    def __init__(self, pid: int, interval: float = 0.05):
        self.pid = pid
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()

    def _run(self):
        while not self._stop.is_set():
            v = server_rss_kb(self.pid)
            if v > self.peak:
                self.peak = v
            time.sleep(self.interval)

    def __enter__(self):
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self._t.join()


def t1_concurrent_reads(base):
    # 冷启动单请求（懒初始化成本），再测热机 20 并发
    t0 = time.perf_counter()
    st, body = _req(base, "GET", "/api/overview")
    cold_ms = round((time.perf_counter() - t0) * 1000, 1)
    assert st == 200 and body["code"] == 0

    lat = []

    def one(_):
        t0 = time.perf_counter()
        st, body = _req(base, "GET", "/api/overview")
        dt = (time.perf_counter() - t0) * 1000
        assert st == 200 and body["code"] == 0, f"overview 失败: {st} {body}"
        return dt

    with cf.ThreadPoolExecutor(max_workers=20) as ex:
        lat = sorted(ex.map(one, range(20)))
    return {
        "n": 20, "cold_single_ms": cold_ms,
        "warm_avg_ms": round(sum(lat) / len(lat), 1),
        "warm_p99_ms": round(lat[math.ceil(0.99 * len(lat)) - 1], 1),
        "warm_max_ms": round(lat[-1], 1),
    }


def t2_concurrent_uploads(base):
    st, body = _req(base, "GET", "/api/overview")
    before = body["data"]["total_books"]

    def one(i):
        name = f"perf_cw_{os.getpid()}_{i}_{int(time.time()*1000)}.txt"
        content = ("第1章 并发\n" + "正文。" * 200 + "\n").encode()
        data, ctype = build_multipart(content, name)
        st2, b2 = _req(base, "POST", "/api/import-upload", data=data,
                       headers={"Content-Type": ctype}, timeout=120)
        assert st2 == 200 and b2["code"] == 0, f"并发上传失败: {st2} {b2}"
        return b2["data"]["book_id"]

    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        ids = list(ex.map(one, range(10)))
    assert len(set(ids)) == 10, "book_id 应互不相同"
    st, body = _req(base, "GET", "/api/overview")
    after = body["data"]["total_books"]
    assert after == before + 10, f"书数应 +10: {before} -> {after}"
    return {"n": 10, "books_added": after - before}


def t3_upload_100mb(base, pid):
    # 100 章 × ~0.99MB 章节体，总计约 99MB，保证能解析出章节且逼近 100MB 上限
    unit = "甲乙丙丁戊己庚辛壬癸。"  # 33 bytes（utf-8）
    chunk = "第X章 边界\n" + unit * 31457  # ≈ 1038081 B ≈ 0.99MB
    parts = [chunk.replace("第X章", f"第{i+1}章") for i in range(100)]
    content = ("\n".join(parts)).encode("utf-8")
    # 精确凑到 100MB（含 multipart 开销则略超——服务端按 Content-Length 计，属"上限内"）
    assert len(content) <= MAX_UPLOAD, f"测试文件 {len(content)} 超过 100MB，请调小"
    data, ctype = build_multipart(content, "perf_100mb.txt")
    assert len(data) >= 90 * 1024 * 1024, f"文件过小({len(data)})，失去边界意义"

    rss_before_kb = server_rss_kb(pid)
    with RssSampler(pid) as sampler:
        t0 = time.perf_counter()
        st, body = _req(base, "POST", "/api/import-upload", data=data,
                        headers={"Content-Type": ctype}, timeout=300)
        dt = time.perf_counter() - t0
    assert st == 200 and body["code"] == 0, f"100MB 上传失败: {st} {str(body)[:200]}"
    # 内存回归硬上限：旧 stdlib email 解析器实现 100MB 上传时 RSS 峰值约 3.1GB；
    # 手工边界扫描实现预期峰值约 2×body + baseline（≈250MB）。600MB 为回归哨兵，
    # 非任务书指标（任务书无内存数值要求），只用于捕捉"量级倒退"。
    peak_mb = sampler.peak / 1024
    assert peak_mb < 600, (
        f"100MB 上传 RSS 峰值 {peak_mb:.0f}MB 超过 600MB 回归上限 "
        f"(baseline {rss_before_kb / 1024:.0f}MB)，疑似解析器内存放大倒退"
    )
    return {
        "bytes": len(data), "elapsed_s": round(dt, 1),
        "server_rss_peak_mb": round(peak_mb, 1),
        "server_rss_before_mb": round(rss_before_kb / 1024, 1),
    }


def t4_oversize_rejected(base):
    """Content-Length = 100MB+1，只发 header 就应被 413 拒绝（服务端不读 body）。"""
    u = urllib.parse.urlparse(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    conn.putrequest("POST", "/api/import-upload")
    conn.putheader("Content-Type", "multipart/form-data; boundary=x")
    conn.putheader("Content-Length", str(MAX_UPLOAD + 1))
    conn.endheaders()
    resp = conn.getresponse()
    body = resp.read(4096).decode("utf-8", "replace")
    conn.close()
    assert resp.status == 413, f"期望 413，实际 {resp.status}: {body[:200]}"
    assert "100MB" in body
    return {"status": 413}


class Blackhole:
    """接受 TCP 连接但永不回包，用于触发客户端超时。"""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(8)
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._serve, daemon=True)
        self._t.start()

    def _serve(self):
        self.sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                c, _ = self.sock.accept()
            except TimeoutError:
                continue
            threading.Thread(target=self._hang, args=(c,), daemon=True).start()

    @staticmethod
    def _hang(c):
        try:
            c.settimeout(60)
            c.recv(65536)
            time.sleep(60)
        except OSError:
            pass
        finally:
            c.close()

    def close(self):
        self._stop.set()
        self.sock.close()


def t5_call_timeout(base, server_root):
    bh = Blackhole()
    try:
        st, body = _req(base, "POST", "/api/models", data=json.dumps({
            "id": "perf-timeout", "protocol": "openai",
            "base_url": f"http://127.0.0.1:{bh.port}",
            "model_name": "dummy", "timeout": 2,
            # 假 key（隔离服务专用，非真实密钥）：让请求越过"缺少 API Key"检查，
            # 真正走到 HTTP 调用层，触发黑洞超时。副本跑完即删。
            "api_key": "e2e-fake-key-not-real",
        }).encode(), headers={"Content-Type": "application/json"})
        assert st in (200, 409), f"建超时模型失败: {st} {body}"

        content = ("第1章 超时\n" + "正文。" * 200 + "\n").encode()
        data, ctype = build_multipart(content, f"perf_timeout_{os.getpid()}.txt")
        st, body = _req(base, "POST", "/api/import-upload", data=data,
                        headers={"Content-Type": ctype}, timeout=120)
        book_id = body["data"]["book_id"]

        st, body = _req(base, "GET", "/api/genres")
        genre = body["data"]["genres"][0]
        st, body = _req(base, "POST", "/api/analyze/start",
                        data=json.dumps({"book_id": book_id, "genre": genre,
                                         "model_id": "perf-timeout"}).encode(),
                        headers={"Content-Type": "application/json"})
        assert st == 200 and body["code"] == 0, f"启动分析失败: {st} {body}"

        deadline = time.time() + 60
        t_start = time.time()
        failed = []
        while time.time() < deadline:
            st, body = _req(base, "GET", f"/api/status?book_id={book_id}")
            states = (body["data"] or {}).get("chapter_states", {}) or {}
            failed = [k for k, v in states.items()
                      if isinstance(v, dict) and v.get("status") == "failed"]
            if failed:
                break
            time.sleep(1)
        assert failed, "60s 内未观察到批次失败（timeout 可能未生效）"
        elapsed = round(time.time() - t_start, 1)
        # 白盒复核（隔离副本）：last_error 应含 timed out，证明走的是超时路径
        # 而非"缺少 API Key"等快速失败路径。
        err_text = ""
        mirror_found = False
        if server_root:
            import glob as _glob
            for f in _glob.glob(os.path.join(server_root, "gui", "state",
                                             f"gui_state_{book_id}.json")):
                try:
                    err_text = json.load(open(f)).get("last_error", "") or ""
                    mirror_found = True
                except OSError:
                    pass
        if mirror_found:
            assert "timed out" in err_text.lower(), \
                f"last_error 未含超时证据: {err_text[:150]!r}"
        return {"timeout_observed": True,
                "failed_batches": failed[:3], "elapsed_s": elapsed,
                "last_error_head": err_text[:120]}
    finally:
        bh.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--server-pid", type=int, required=True)
    ap.add_argument("--server-root", default="",
                    help="隔离服务副本根目录（用于白盒复核状态文件）")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    results = {}
    results["T1_concurrent_reads"] = t1_concurrent_reads(base)
    results["T2_concurrent_uploads"] = t2_concurrent_uploads(base)
    results["T3_upload_100MB"] = t3_upload_100mb(base, args.server_pid)
    results["T4_oversize_rejected"] = t4_oversize_rejected(base)
    results["T5_call_timeout"] = t5_call_timeout(base, args.server_root or None)
    results["verdict"] = "ALL_PASS"
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
