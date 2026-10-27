#!/usr/bin/env python3
"""机器 TX 上报 + max(CDT, 新鲜 TX) 阈值判断的测试。

锁死四条规则：
  1. traffic_used 取 CDT 接口流量与新鲜 TX 的最高值；
  2. 超过 180 秒的 TX、或非当月月份的 TX，一律忽略、回落到 CDT；
  3. 未知 instance_id 上报返回 404，不建服务器、不写数据；
  4. 负数 tx_gb、非法 month 一律拒绝，不写数据。
CDT 为 None 且 TX 新鲜时用 TX；两者都 None 时 traffic_used 为 None，
_over_threshold 对 None 本来就返回 False，不会误停机。

跑法：python scripts/test_tx_report.py
（需要先装 requirements.txt；测试用临时数据目录，不碰真实面板数据。）
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="cdt-tx-report-")
os.environ["CDT_DATA_DIR"] = _TMP
os.environ["CDT_DRY_RUN"] = "1"

from app import aliyun, db, repo, shift  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import api as api_module  # noqa: E402

TEST_TOKEN = "tx-test-token-for-local-test-only"
INSTANCE_ID = "i-tx-test-001"


def _current_month() -> str:
    return repo._month_of(int(time.time()))


class TxReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.server_id = repo.upsert_server(
            {
                "label": "TX测试机",
                "access_key_id": "LTAI5tFakeKeyForTest",
                "access_key_secret": "fake-secret-for-test",
                "region_id": "cn-hongkong",
                "site": "international",
                "instance_id": INSTANCE_ID,
                "quota_gb": 200,
                "threshold_gb": 188,
            }
        )
        repo.set_settings({"tx_report_token": TEST_TOKEN})

    def setUp(self) -> None:
        db.execute("DELETE FROM tx_reports")
        # 每个用例开始都恢复测试 Token（503 用例会在 finally 里恢复）。
        repo.set_settings({"tx_report_token": TEST_TOKEN})

    def _record(self, tx_gb: float, month: str | None = None) -> None:
        repo.record_tx_report(
            server_id=self.server_id,
            instance_id=INSTANCE_ID,
            month=month if month is not None else _current_month(),
            tx_gb=tx_gb,
            hostname="tx-test-host",
            interface="eth0",
        )

    def _client(self) -> TestClient:
        app = FastAPI()
        api_module.register(app)
        return TestClient(app, raise_server_exceptions=False)

    def _payload(self, **overrides) -> dict:
        payload = {
            "instance_id": INSTANCE_ID,
            "hostname": "tx-test-host",
            "public_ipv4": "203.0.113.1",
            "interface": "eth0",
            "month": _current_month(),
            "tx_gb": 120.0,
            "timestamp": "2030-01-01T00:00:00+00:00",
        }
        payload.update(overrides)
        return payload

    # -- max() 规则 ------------------------------------------------------
    def test_max_picks_higher_tx(self):
        self._record(150.0)
        used, source = repo.effective_traffic(100.0, self.server_id)
        self.assertEqual(used, 150.0)
        self.assertEqual(source, "max")

    def test_max_picks_higher_cdt(self):
        self._record(80.0)
        used, source = repo.effective_traffic(120.0, self.server_id)
        self.assertEqual(used, 120.0)
        self.assertEqual(source, "cdt")

    def test_stale_tx_ignored(self):
        self._record(190.0)
        db.execute(
            "UPDATE tx_reports SET received_at=? WHERE server_id=?",
            (int(time.time()) - 200, self.server_id),
        )
        used, source = repo.effective_traffic(100.0, self.server_id)
        self.assertEqual(used, 100.0)
        self.assertEqual(source, "cdt")

    def test_old_month_tx_ignored(self):
        # 上月最后一分钟上报的高值，不能在新月继续顶阈值。
        year, month = _current_month().split("-")
        if month == "01":
            old_month = f"{int(year) - 1}-12"
        else:
            old_month = f"{year}-{int(month) - 1:02d}"
        self._record(199.0, month=old_month)
        used, source = repo.effective_traffic(100.0, self.server_id)
        self.assertEqual(used, 100.0)
        self.assertEqual(source, "cdt")

    def test_cdt_none_uses_fresh_tx(self):
        self._record(90.0)
        used, source = repo.effective_traffic(None, self.server_id)
        self.assertEqual(used, 90.0)
        self.assertEqual(source, "tx")

    def test_both_none_stays_none_and_no_false_stop(self):
        used, source = repo.effective_traffic(None, self.server_id)
        self.assertIsNone(used)
        self.assertIsNone(source)
        self.assertFalse(shift._over_threshold({"traffic_used": None, "threshold_gb": 188}))

    def test_refresh_uses_max(self):
        self._record(150.0)
        orig_traffic = shift.aliyun.get_traffic_gb
        orig_instance = shift.aliyun.get_instance
        try:
            shift.aliyun.get_traffic_gb = lambda server: 100.0  # noqa: ARG005
            shift.aliyun.get_instance = lambda server: aliyun.InstanceInfo(  # noqa: ARG005
                "Running", "", "203.0.113.1", "cn-hongkong"
            )
            server = repo.get_server(self.server_id, decrypt_secret=True)
            assert server is not None
            shift._refresh(server)
            self.assertEqual(server["traffic_used"], 150.0)
            self.assertEqual(server["traffic_source"], "max")
        finally:
            shift.aliyun.get_traffic_gb = orig_traffic
            shift.aliyun.get_instance = orig_instance

    def test_refresh_stores_cdt_and_summary_shows_three_values(self):
        self._record(150.0)
        orig_traffic = shift.aliyun.get_traffic_gb
        orig_instance = shift.aliyun.get_instance
        try:
            shift.aliyun.get_traffic_gb = lambda server: 100.0  # noqa: ARG005
            shift.aliyun.get_instance = lambda server: aliyun.InstanceInfo(  # noqa: ARG005
                "Running", "", "203.0.113.1", "cn-hongkong"
            )
            server = repo.get_server(self.server_id, decrypt_secret=True)
            assert server is not None
            shift._refresh(server)
        finally:
            shift.aliyun.get_traffic_gb = orig_traffic
            shift.aliyun.get_instance = orig_instance
        fresh = repo.get_server(self.server_id)
        assert fresh is not None
        self.assertEqual(fresh.get("cdt_traffic_gb"), 100.0)
        self.assertEqual(fresh.get("traffic_used"), 150.0)
        summary = api_module.server_summary(fresh)
        self.assertEqual(summary.get("cdt_gb"), 100.0)
        self.assertEqual(summary.get("tx_gb"), 150.0)
        self.assertTrue(summary.get("tx_fresh"))
        self.assertEqual(summary.get("traffic_used"), 150.0)
        self.assertEqual(summary.get("traffic_source"), "max")
        self.assertIsNotNone(summary.get("tx_age_seconds"))
        self.assertLessEqual(summary.get("tx_age_seconds"), 180)

    def test_summary_without_tx_shows_none_not_zero(self):
        # 从未上报时 TX 必须显示为 None（界面上是“—/未上报”），不能写成 0 GB
        # 误导用户以为本月 TX 就是 0。
        server = repo.get_server(self.server_id)
        assert server is not None
        summary = api_module.server_summary(server)
        self.assertIsNone(summary.get("tx_gb"))
        self.assertFalse(summary.get("tx_fresh"))
        self.assertIsNone(summary.get("tx_age_seconds"))

    # -- 上报接口 --------------------------------------------------------
    def test_endpoint_accepts_valid_report(self):
        client = self._client()
        resp = client.post(
            "/api/v1/tx-report",
            json=self._payload(tx_gb=123.5),
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json().get("ok"))
        self.assertEqual(resp.json().get("server_id"), self.server_id)
        self.assertEqual(repo.fresh_tx_gb(self.server_id), 123.5)

    def test_endpoint_machine_timestamp_is_not_trusted(self):
        # 机器 timestamp 写成未来时间也不应影响：面板用收到时间判新鲜。
        client = self._client()
        resp = client.post(
            "/api/v1/tx-report",
            json=self._payload(),
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(repo.fresh_tx_gb(self.server_id), 120.0)

    def test_endpoint_unknown_instance_404_and_no_write(self):
        client = self._client()
        resp = client.post(
            "/api/v1/tx-report",
            json=self._payload(instance_id="i-tx-unknown-999"),
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        self.assertEqual(resp.status_code, 404, resp.text)
        self.assertIsNone(repo.latest_tx_report(self.server_id))

    def test_endpoint_negative_tx_rejected(self):
        client = self._client()
        resp = client.post(
            "/api/v1/tx-report",
            json=self._payload(tx_gb=-1),
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIsNone(repo.latest_tx_report(self.server_id))

    def test_endpoint_bad_month_rejected(self):
        client = self._client()
        resp = client.post(
            "/api/v1/tx-report",
            json=self._payload(month="2026-13"),
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIsNone(repo.latest_tx_report(self.server_id))

    def test_endpoint_wrong_token_401(self):
        client = self._client()
        resp = client.post(
            "/api/v1/tx-report",
            json=self._payload(),
            headers={"Authorization": "Bearer wrong-token"},
        )
        self.assertEqual(resp.status_code, 401, resp.text)
        self.assertIsNone(repo.latest_tx_report(self.server_id))

    def test_endpoint_no_token_configured_503(self):
        try:
            repo.set_settings({"tx_report_token": ""})
            # set_settings 会把空串原样存入（security.encrypt("") == ""），
            # tx_report_token() 此时应返回空，接口应 503 而非无鉴权放行。
            # 注意：环境变量 CDT_TX_REPORT_TOKEN 未设置时才走这条分支。
            if os.environ.get("CDT_TX_REPORT_TOKEN"):
                self.skipTest("CDT_TX_REPORT_TOKEN 已设置，跳过未配置分支")
            client = self._client()
            resp = client.post(
                "/api/v1/tx-report",
                json=self._payload(),
                headers={"Authorization": f"Bearer {TEST_TOKEN}"},
            )
            self.assertEqual(resp.status_code, 503, resp.text)
        finally:
            repo.set_settings({"tx_report_token": TEST_TOKEN})


if __name__ == "__main__":
    unittest.main(verbosity=2)
