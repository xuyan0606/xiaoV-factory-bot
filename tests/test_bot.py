"""xiaoV Factory Bot — 单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from factory_bot_server import app, FACTORY_DATA


def test_health():
    """健康检查"""
    client = app.test_client()
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"


def _post(msg):
    """Helper: POST to webhook with token"""
    return app.test_client().post(
        "/dingtalk/webhook?token=xiaov_factory_2026",
        json={"msgtype": "text", "text": {"content": msg}}
    )


def test_help():
    """帮助命令"""
    r = _post("帮助")
    assert r.status_code == 200
    data = r.get_json()
    assert "命令指南" in data["text"]["content"]


def test_workshop_query():
    """查车间"""
    r = _post("查车间")
    assert r.status_code == 200
    data = r.get_json()
    assert "发酵车间" in data["text"]["content"]


def test_batch_query():
    """查生产"""
    r = _post("查生产")
    assert r.status_code == 200
    data = r.get_json()
    assert "批次" in data["text"]["content"]


def test_equipment_query():
    """查设备"""
    r = _post("查设备")
    assert r.status_code == 200
    data = r.get_json()
    assert "发酵罐" in data["text"]["content"]


def test_factory_data_exists():
    """工厂数据完整性"""
    assert "车间" in FACTORY_DATA
    assert "产品" in FACTORY_DATA
    assert "设备" in FACTORY_DATA
    assert "配方" in FACTORY_DATA
    assert "当前批次" in FACTORY_DATA
    assert "数字化升级" in FACTORY_DATA


if __name__ == "__main__":
    # Run manually
    for name in dir():
        if name.startswith("test_"):
            fn = globals()[name]
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                sys.exit(1)
    print("\nALL TESTS PASSED ✅")
