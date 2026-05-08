"""
MES 完整服务 — Flask + Flask-SocketIO
REST API (端口 5002) + WebSocket 实时推送
"""

from flask import Flask, jsonify, request, send_from_directory
import os
from flask_socketio import SocketIO, emit
import mes_core as db
import mes_auth as auth
import json, datetime, threading, random, time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mes-2026'
app.config['JSON_AS_ASCII'] = False

# 初始化 JWT 认证
auth.init_auth(app)
auth.auth_routes(app, db)  # 注册 /api/auth/* 路由

# 允许跨域（Dashboard 从 5003 访问 5002 API）
@app.after_request
def add_cors(res):
    res.headers['Access-Control-Allow-Origin'] = 'http://localhost:5003'
    res.headers['Access-Control-Allow-Credentials'] = 'true'
    res.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    res.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return res

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─────────────────────────────────────────
# 传感器模拟状态
# ─────────────────────────────────────────
SIM_STATE = {}  # batch_id -> {temp, pH, DO, stir_speed, pressure}
TREND = {}

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def next_val(current, lo, hi, volatility=0.3):
    tid = id(current)
    if random.random() < 0.3:
        TREND[tid] = -TREND.get(tid, 0)
    delta = random.gauss(TREND.get(tid, 0) * 0.2, volatility)
    TREND[tid] = TREND.get(tid, 0) + delta * 0.1
    return clamp(current + delta, lo, hi)

def simulate_batch(batch_id, stage="fermentation"):
    cfg = {
        "fermentation": {
            "base": {"temp": 36.5, "pH": 6.5, "DO": 85.0, "stir_speed": 150.0, "pressure": 1.0},
            "lo":   {"temp": 34.0, "pH": 5.5, "DO": 60.0, "stir_speed": 100.0, "pressure": 0.8},
            "hi":   {"temp": 38.0, "pH": 7.0, "DO": 95.0, "stir_speed": 200.0, "pressure": 1.2},
        },
        "seed": {
            "base": {"temp": 35.0, "pH": 6.2, "DO": 70.0, "stir_speed": 120.0, "pressure": 0.9},
            "lo":   {"temp": 33.0, "pH": 5.8, "DO": 50.0, "stir_speed": 80.0,  "pressure": 0.7},
            "hi":   {"temp": 37.0, "pH": 6.8, "DO": 85.0, "stir_speed": 160.0, "pressure": 1.1},
        },
    }
    c = cfg.get(stage, cfg["fermentation"])
    SIM_STATE[batch_id] = c["base"].copy()

    while batch_id in SIM_STATE:
        time.sleep(2)
        if batch_id not in SIM_STATE:
            break
        row = {}
        for k in c["base"]:
            SIM_STATE[batch_id][k] = next_val(SIM_STATE[batch_id][k], c["lo"][k], c["hi"][k])
            row[k] = round(SIM_STATE[batch_id][k], 2)

        alerts = []
        if row["temp"] > 37.5:
            alerts.append({"type": "temp_high", "level": "critical", "value": row["temp"], "message": f"温度{row['temp']}°C 超过上限37.5°C"})
        if row["pH"] > 6.8:
            alerts.append({"type": "pH_high", "level": "warning", "value": row["pH"], "message": f"pH {row['pH']} 超过上限6.8"})
        if row["pH"] < 5.8:
            alerts.append({"type": "pH_low", "level": "warning", "value": row["pH"], "message": f"pH {row['pH']} 低于下限5.8"})
        if row["DO"] < 30:
            alerts.append({"type": "DO_low", "level": "critical", "value": row["DO"], "message": f"溶解氧{row['DO']}% 低于下限30%"})

        # 写入数据库
        db.record_batch_params(batch_id, row.get("temp"), row.get("pH"), row.get("DO"), row.get("stir_speed"), row.get("pressure"))
        db.check_and_alert(batch_id, batch_id[:7], row.get("temp"), row.get("pH"), row.get("DO"))

        socketio.emit("batch_params", {
            "batch_id": batch_id, "timestamp": datetime.datetime.now().isoformat(),
            "params": row, "alerts": alerts,
        }, namespace="/mes")

def start_simulation(batch_id, stage="fermentation"):
    t = threading.Thread(target=simulate_batch, args=(batch_id, stage), daemon=True)
    t.start()
    return t

# ─────────────────────────────────────────
# WebSocket 事件
# ─────────────────────────────────────────
@socketio.on("connect", namespace="/mes")
def ws_connect():
    emit("connected", {"status": "ok", "time": datetime.datetime.now().isoformat()})

@socketio.on("disconnect", namespace="/mes")
def ws_disconnect():
    pass

@socketio.on("subscribe_batch", namespace="/mes")
def ws_subscribe(data):
    bid = data.get("batch_id")
    if bid and bid not in SIM_STATE:
        start_simulation(bid)
    emit("subscribed", {"batch_id": bid, "params": SIM_STATE.get(bid, {})}, namespace="/mes")

@socketio.on("unsubscribe_batch", namespace="/mes")
def ws_unsubscribe(data):
    bid = data.get("batch_id")
    if bid in SIM_STATE:
        del SIM_STATE[bid]

# ─────────────────────────────────────────
# REST 响应格式
# ─────────────────────────────────────────
def ok(data=None, message="ok"):
    return jsonify({"code": 0, "data": data, "message": message})

def fail(msg, code=1):
    return jsonify({"code": code, "data": None, "message": msg})

# ─────────────────────────────────────────
# REST 路由
# ─────────────────────────────────────────
@app.route("/api/health")
def health():
    return ok({"status": "running", "ws_clients": len(SIM_STATE)})

@app.route("/api/orders", methods=["GET"])
def get_orders():
    return ok(db.list_orders(status=request.args.get("status")))

@app.route("/api/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    o = db.get_order(order_id)
    return ok(o) if o else fail("工单不存在", 404)

@app.route("/api/orders", methods=["POST"])
@auth.require_permission("orders")
def new_order():
    b = request.json
    for f in ["product_code", "product_name", "batch_size"]:
        if f not in b: return fail(f"缺少字段: {f}")
    oid = db.create_order(b["product_code"], b["product_name"], b["batch_size"],
                          b.get("fermenter_id"), b.get("plan_start"), b.get("plan_end"), b.get("priority", 2))
    return ok({"order_id": oid}, "工单创建成功")

@app.route("/api/orders/<order_id>/status", methods=["PUT"])
@auth.require_permission("orders")
def update_order_status(order_id):
    b = request.json
    if "status" not in b: return fail("缺少 status")
    if not db.get_order(order_id): return fail("工单不存在", 404)
    db.update_order_status(order_id, b["status"])
    return ok({"order_id": order_id, "status": b["status"]})

@app.route("/api/orders/<order_id>/report", methods=["POST"])
@auth.require_permission("orders")
def report_order_api(order_id):
    b = request.json
    if not db.get_order(order_id): return fail("工单不存在", 404)
    db.report_order(order_id, b.get("operator","未知"), b.get("input_qty"), b.get("output_qty"), b.get("remark"))
    return ok({"order_id": order_id}, "报工成功")

@app.route("/api/batches", methods=["GET"])
def get_batches():
    bid = request.args.get("order_id")
    if bid:
        b = db.get_batch_by_order(bid)
        return ok([b] if b else [])
    return ok(db.list_batches())

@app.route("/api/batches/<batch_id>", methods=["GET"])
def get_batch(batch_id):
    b = db.get_batch(batch_id)
    return ok(b) if b else fail("批次不存在", 404)

@app.route("/api/batches", methods=["POST"])
@auth.require_permission("batches")
def new_batch():
    b = request.json
    if "order_id" not in b: return fail("缺少 order_id")
    if not db.get_order(b["order_id"]): return fail("工单不存在", 404)
    bid = db.create_batch(b["order_id"])
    return ok({"batch_id": bid}, "批次创建成功")

@app.route("/api/batches/<batch_id>/advance", methods=["POST"])
@auth.require_permission("batches")
def advance_stage(batch_id):
    ns = db.advance_batch_stage(batch_id)
    return ok({"batch_id": batch_id, "stage": ns}, "阶段推进成功")

@app.route("/api/batches/<batch_id>/params", methods=["POST"])
def record_params(batch_id):
    b = request.json
    batch = db.get_batch(batch_id)
    if not batch: return fail("批次不存在", 404)
    equip_id = request.args.get("equip_id", batch_id[:7])
    alerts = db.check_and_alert(batch_id, equip_id, b.get("temp"), b.get("pH"), b.get("DO"))
    db.record_batch_params(batch_id, b.get("temp"), b.get("pH"), b.get("DO"), b.get("stir_speed"), b.get("pressure"))
    return ok({"batch_id": batch_id, "alerts": alerts, **b}, f"参数记录成功，触发告警{len(alerts)}个" if alerts else "参数记录成功")

@app.route("/api/batches/<batch_id>/history", methods=["GET"])
def batch_history(batch_id):
    """获取批次历史参数，支持时间范围过滤"""
    # 支持 start/end 或 start_time/end_time
    start_time = request.args.get("start") or request.args.get("start_time")
    end_time = request.args.get("end") or request.args.get("end_time")
    limit = int(request.args.get("limit", 2000))
    batch = db.get_batch(batch_id)
    if not batch:
        return fail("批次不存在", 404)
    return ok(db.get_batch_history(batch_id, limit=limit, start_time=start_time, end_time=end_time))

@app.route("/api/batches/<batch_id>/latest", methods=["GET"])
def batch_latest(batch_id):
    """获取批次最新一条参数"""
    batch = db.get_batch(batch_id)
    if not batch:
        return fail("批次不存在", 404)
    history = db.get_batch_history(batch_id, limit=1)
    if not history:
        return ok(None, "暂无参数记录")
    return ok(history[-1])

@app.route("/api/quality/tests", methods=["GET"])
def get_quality_tests():
    return ok(db.list_quality_tests(batch_id=request.args.get("batch_id"), result=request.args.get("result")))

@app.route("/api/quality/tests", methods=["POST"])
@auth.require_permission("quality")
def new_quality_test():
    b = request.json
    for f in ["batch_id", "stage", "tester"]:
        if f not in b: return fail(f"缺少字段: {f}")
    if not db.get_batch(b["batch_id"]): return fail("批次不存在", 404)
    tid = db.create_quality_test(b["batch_id"], b["stage"], b["tester"],
                                  enzyme_activity=b.get("enzyme_activity"), moisture=b.get("moisture"),
                                  microbial_count=b.get("microbial_count"), pH_value=b.get("pH_value"),
                                  appearance=b.get("appearance"), remark=b.get("remark"))
    # 自动判定
    judge_result = db.judge_quality(tid)
    # fail 时触发告警
    if judge_result and judge_result['result'] == 'fail':
        _trigger_quality_alert(tid, judge_result)
    return ok({"test_id": tid, "judge": judge_result}, "质检记录创建成功，判定完成")

@app.route("/api/quality/tests/<test_id>/judge", methods=["POST"])
@auth.require_permission("quality")
def judge_test(test_id):
    r = db.judge_quality(test_id)
    if r and r['result'] == 'fail':
        _trigger_quality_alert(test_id, r)
    return ok({"test_id": test_id, "result": r}, f"判定完成: {r['result']}")

@app.route("/api/quality/tests/<test_id>/review", methods=["POST"])
@auth.require_permission("quality")
def review_test(test_id):
    """人工审核覆盖自动判定"""
    b = request.json
    if not b.get("reviewed_by"): return fail("缺少审核人")
    if not b.get("result"): return fail("缺少判定结果")
    if b["result"] not in ("pass", "fail", "warning"):
        return fail("result 只能是 pass/fail/warning")
    rec = db.review_quality_test(test_id, b["reviewed_by"], b["result"], b.get("review_remark"))
    if not rec: return fail("质检记录不存在", 404)
    return ok(rec, "审核完成")

def _trigger_quality_alert(test_id, judge_result):
    """质检fail时写入系统告警"""
    t = db.list_quality_tests(batch_id=None, limit=1)
    with db.use_db() as d:
        details = judge_result.get('details') or []
        msg_parts = [f"质检{test_id}不合格:"]
        for iss in details:
            if iss['type'] == 'low':
                msg_parts.append(f"{iss['param']}={iss['value']}{iss['unit']} 低于下限{iss['lo']}{iss['unit']}")
            else:
                msg_parts.append(f"{iss['param']}={iss['value']}{iss['unit']} 超过上限{iss['hi']}{iss['unit']}")
        msg = "；".join(msg_parts)
        d.execute("""
            INSERT INTO alerts (alert_type, level, message, status)
            VALUES ('quality_fail', 'critical', ?, 'active')
        """, [msg])

# ─── 质量标准 API ────────────────────────────
@app.route("/api/quality/specs", methods=["GET"])
def get_quality_specs():
    """GET /api/quality/specs — 质量标准列表"""
    product_type = request.args.get("product_type")
    stage = request.args.get("stage")
    return ok(db.list_quality_specs(product_type=product_type, stage=stage))

@app.route("/api/quality/specs", methods=["POST"])
@auth.require_permission("quality")
def new_quality_spec():
    """POST /api/quality/specs — 新增标准"""
    b = request.json
    for f in ["product_type", "stage", "param_name"]:
        if f not in b: return fail(f"缺少字段: {f}")
    sid = db.create_quality_spec(
        b["product_type"], b["stage"], b["param_name"],
        lo=b.get("lo"), hi=b.get("hi"), unit=b.get("unit")
    )
    return ok({"standard_id": sid}, "质量标准创建成功")

@app.route("/api/quality/specs/<standard_id>", methods=["GET"])
def get_quality_spec(standard_id):
    s = db.get_quality_spec(standard_id)
    return ok(s) if s else fail("标准不存在", 404)

@app.route("/api/equipment", methods=["GET"])
def get_equipment():
    return ok(db.list_equipment(equip_type=request.args.get("type"), status=request.args.get("status")))

@app.route("/api/equipment/<equip_id>", methods=["GET"])
def get_equip(equip_id):
    e = db.get_equipment(equip_id)
    return ok(e) if e else fail("设备不存在", 404)

@app.route("/api/equipment", methods=["POST"])
@auth.require_permission("equipment")
def new_equipment():
    b = request.json
    for f in ["equip_id", "equip_name", "equip_type"]:
        if f not in b: return fail(f"缺少字段: {f}")
    db.create_equipment(b["equip_id"], b["equip_name"], b["equip_type"], b.get("model"), b.get("location"))
    return ok({"equip_id": b["equip_id"]}, "设备创建成功")

@app.route("/api/equipment/<equip_id>/status", methods=["PUT"])
def update_equip_status(equip_id):
    b = request.json
    if "status" not in b: return fail("缺少 status")
    db.update_equip_status(equip_id, b["status"])
    return ok({"equip_id": equip_id, "status": b["status"]})

# ─────────────────────────────────────────
# 维保计划 API
# ─────────────────────────────────────────

# GET /api/maintenance/plans
@app.route("/api/maintenance/plans", methods=["GET"])
def get_maint_plans():
    return ok(db.list_maintenance_plans(
        equip_id=request.args.get("equip_id"),
        status=request.args.get("status")
    ))

# POST /api/maintenance/plans
@app.route("/api/maintenance/plans", methods=["POST"])
@auth.require_permission("maintenance")
def new_maint_plan():
    b = request.json
    for f in ["equip_id", "maintenance_type"]:
        if f not in b: return fail(f"缺少字段: {f}")
    if not db.get_equipment(b["equip_id"]): return fail("设备不存在", 404)
    plan_id = db.create_maintenance_plan(
        b["equip_id"], b["maintenance_type"],
        interval_days=b.get("interval_days"),
        last_date=b.get("last_date"),
        next_date=b.get("next_date"),
        remark=b.get("remark")
    )
    plan = db.get_maintenance_plan(plan_id)
    socketio.emit("maintenance_update", {"action": "created", "plan": plan}, namespace="/mes")
    return ok({"plan_id": plan_id, "plan": plan}, "维保计划创建成功")

# PUT /api/maintenance/plans/<plan_id>
@app.route("/api/maintenance/plans/<plan_id>", methods=["PUT"])
@auth.require_permission("maintenance")
def update_maint_plan(plan_id):
    b = request.json
    plan = db.update_maintenance_plan(plan_id, **b)
    if not plan: return fail("维保计划不存在", 404)
    socketio.emit("maintenance_update", {"action": "updated", "plan": plan}, namespace="/mes")
    return ok(plan, "维保计划更新成功")

# GET /api/maintenance/records
@app.route("/api/maintenance/records", methods=["GET"])
def get_maint_records():
    return ok(db.list_maintenance_records(
        plan_id=request.args.get("plan_id"),
        equip_id=request.args.get("equip_id"),
        limit=int(request.args.get("limit", 50))
    ))

# POST /api/maintenance/records
@app.route("/api/maintenance/records", methods=["POST"])
@auth.require_permission("maintenance")
def new_maint_record():
    b = request.json
    for f in ["plan_id", "equip_id", "maintenance_type"]:
        if f not in b: return fail(f"缺少字段: {f}")
    record_id = db.create_maintenance_record(
        b["plan_id"], b["equip_id"], b["maintenance_type"],
        executor=b.get("executor"),
        result=b.get("result"),
        cost=b.get("cost"),
        remark=b.get("remark")
    )
    socketio.emit("maintenance_update", {"action": "record_created", "record_id": record_id}, namespace="/mes")
    return ok({"record_id": record_id}, "维保记录创建成功")

# GET /api/maintenance/overdue
@app.route("/api/maintenance/overdue", methods=["GET"])
def overdue_maint():
    return ok(db.get_overdue_maintenance())

# GET /api/maintenance/upcoming
@app.route("/api/maintenance/upcoming", methods=["GET"])
def upcoming_maint():
    days = int(request.args.get("days", 7))
    return ok(db.get_upcoming_maintenance(days=days))

# POST /api/maintenance/generate-plans
@app.route("/api/maintenance/generate-plans", methods=["POST"])
@auth.require_permission("maintenance")
def generate_maint_plans():
    created = db.auto_generate_plans()
    plans = db.list_maintenance_plans()
    return ok({"created": len(created), "plans": plans}, f"已为 {len(created)} 台设备生成维保计划")

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    return ok(db.list_alerts(status=request.args.get("status", "active")))

# ─── 班次与交接班 API ────────────────────────────

@app.route("/api/shifts/current", methods=["GET"])
def get_current_shift():
    """GET /api/shifts/current — 当前班次"""
    shift = db.get_current_shift()
    if not shift:
        return fail("无活跃班次", 404)
    # 补充班次名称
    shift['shift_name'] = db.SHIFT_TYPES.get(shift['shift_type'], {}).get('name', shift['shift_type'])
    return ok(shift)

@app.route("/api/shifts", methods=["GET"])
def get_shifts():
    """GET /api/shifts?date= — 按日期查班次"""
    shift_date = request.args.get("date")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    shifts = db.list_shifts(shift_date=shift_date, status=status, limit=limit)
    for s in shifts:
        s['shift_name'] = db.SHIFT_TYPES.get(s['shift_type'], {}).get('name', s['shift_type'])
    return ok(shifts)

@app.route("/api/shifts", methods=["POST"])
@auth.require_permission("shifts")
def new_shift():
    """POST /api/shifts — 新建班次"""
    b = request.json
    for f in ["shift_date", "shift_type"]:
        if f not in b:
            return fail(f"缺少字段: {f}")
    if b['shift_type'] not in db.SHIFT_TYPES:
        return fail("shift_type 必须是 early/mid/night 之一")
    shift_id = db.create_shift(
        b["shift_date"], b["shift_type"],
        leader=b.get("leader"),
        start_time=b.get("start_time"),
        end_time=b.get("end_time"),
        status=b.get("status", "active")
    )
    shift = db.get_shift(shift_id)
    shift['shift_name'] = db.SHIFT_TYPES.get(shift['shift_type'], {}).get('name', shift['shift_type'])
    return ok(shift, "班次创建成功")

@app.route("/api/shifts/<shift_id>", methods=["PUT"])
@auth.require_permission("shifts")
def update_shift(shift_id):
    """PUT /api/shifts/<id> — 更新班次状态"""
    b = request.json
    if "status" not in b:
        return fail("缺少 status")
    shift = db.update_shift_status(shift_id, b["status"])
    if not shift:
        return fail("班次不存在", 404)
    shift['shift_name'] = db.SHIFT_TYPES.get(shift['shift_type'], {}).get('name', shift['shift_type'])
    return ok(shift)

@app.route("/api/handover", methods=["GET"])
def get_handover_history():
    """GET /api/handover?limit= — 交接记录历史"""
    limit = int(request.args.get("limit", 10))
    records = db.get_handover_history(limit=limit)
    for r in records:
        r['handover_type_label'] = db.HANDOVER_TYPE_LABELS.get(r['handover_type'], r['handover_type'])
        r['shift_out_name'] = db.SHIFT_TYPES.get(r.get('shift_out_type', ''), {}).get('name', r.get('shift_out_type', ''))
        r['shift_in_name'] = db.SHIFT_TYPES.get(r.get('shift_in_type', ''), {}).get('name', r.get('shift_in_type', ''))
    return ok(records)

@app.route("/api/handover", methods=["POST"])
@auth.require_permission("handover")
def new_handover():
    """POST /api/handover — 新建交接记录"""
    b = request.json
    for f in ["shift_id_out", "handover_type"]:
        if f not in b:
            return fail(f"缺少字段: {f}")
    shift_out = db.get_shift(b["shift_id_out"])
    if not shift_out:
        return fail("交班班次不存在", 404)
    shift_id_in = b.get("shift_id_in")
    if shift_id_in:
        shift_in = db.get_shift(shift_id_in)
        if not shift_in:
            return fail("接班班次不存在", 404)
    record_id = db.create_handover(
        shift_id_out=b["shift_id_out"],
        shift_id_in=shift_id_in,
        handover_type=b["handover_type"],
        content=b.get("content"),
        issues=b.get("issues"),
        attachments=b.get("attachments"),
        created_by=b.get("created_by")
    )
    record = db.get_handover(record_id)
    record['handover_type_label'] = db.HANDOVER_TYPE_LABELS.get(record['handover_type'], record['handover_type'])
    socketio.emit("handover_update", {"action": "created", "record": record}, namespace="/mes")
    return ok(record, "交接记录创建成功")

@app.route("/api/handover/<int:record_id>/confirm", methods=["PUT"])
@auth.require_permission("handover")
def confirm_handover_api(record_id):
    """PUT /api/handover/<id>/confirm — 接班人确认"""
    b = request.json
    if not b.get("confirmed_by"):
        return fail("缺少 confirmed_by")
    record = db.confirm_handover(record_id, b["confirmed_by"])
    if not record:
        return fail("交接记录不存在", 404)
    record['handover_type_label'] = db.HANDOVER_TYPE_LABELS.get(record['handover_type'], record['handover_type'])
    socketio.emit("handover_update", {"action": "confirmed", "record": record}, namespace="/mes")
    return ok(record, "交接已确认")

@app.route("/api/work/reports", methods=["GET"])
def get_work_reports():
    """GET /api/work/reports - 查询报工记录列表"""
    return ok(db.list_work_reports(
        order_id=request.args.get("order_id"),
        batch_id=request.args.get("batch_id"),
        worker=request.args.get("worker"),
        status=request.args.get("status"),
        date=request.args.get("date"),
        limit=int(request.args.get("limit", 50))
    ))

@app.route("/api/work/reports", methods=["POST"])
@auth.require_permission("work")
def new_work_report():
    """POST /api/work/reports - 新增报工记录（投料+产出+得率）"""
    b = request.json
    for f in ["order_id", "worker"]:
        if f not in b:
            return fail(f"缺少字段: {f}")
    if b.get("order_id") and not db.get_order(b["order_id"]):
        return fail("工单不存在", 404)
    if b.get("batch_id") and not db.get_batch(b["batch_id"]):
        return fail("批次不存在", 404)
    db.create_work_report(
        order_id=b["order_id"],
        batch_id=b.get("batch_id"),
        worker=b["worker"],
        report_time=b.get("report_time"),
        stage=b.get("stage"),
        input_amount=b.get("input_amount"),
        output_amount=b.get("output_amount"),
        yield_rate=b.get("yield_rate"),
        status=b.get("status", "recorded"),
        remark=b.get("remark")
    )
    return ok({"order_id": b.get("order_id"), "batch_id": b.get("batch_id")}, "报工成功")

@app.route("/api/work/reports/<int:work_report_id>", methods=["PUT"])
@auth.require_permission("work")
def update_work_report(work_report_id):
    """PUT /api/work/reports/<id> - 更新报工记录（确认/取消/修改）"""
    b = request.json
    rec = db.update_work_report(work_report_id, **b)
    if not rec:
        return fail("报工记录不存在", 404)
    return ok(rec, "更新成功")

@app.route("/api/alerts/<int:alert_id>/resolve", methods=["POST"])
@auth.require_permission("alerts")
def resolve_alert(alert_id):
    db.resolve_alert(alert_id)
    return ok({"alert_id": alert_id}, "告警已关闭")

@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    with db.use_db() as d:
        def cnt(sql): return d.execute(sql).fetchone()[0]
        return ok({
            "total_orders": cnt("SELECT COUNT(*) FROM production_orders"),
            "in_progress": cnt("SELECT COUNT(*) FROM production_orders WHERE status='in_progress'"),
            "completed": cnt("SELECT COUNT(*) FROM production_orders WHERE status='completed'"),
            "active_alerts": cnt("SELECT COUNT(*) FROM alerts WHERE status='active'"),
            "pending_tests": cnt("SELECT COUNT(*) FROM quality_tests WHERE result='pending'"),
            "running_batches": cnt("SELECT COUNT(*) FROM batches WHERE stage NOT IN ('completed','pending')"),
        })

@app.errorhandler(404)
def not_found(e): return fail("接口不存在", 404)

@app.errorhandler(500)
def server_error(e): return fail("服务器错误", 500)

# ─────────────────────────────────────────
# 启动
# ─────────────────────────────────────────
if __name__ == "__main__":
    db.init_db()
    db.seed_demo_data()

    # 自动启动活跃批次的模拟
    with db.use_db() as d:
        rows = d.execute("SELECT batch_id FROM batches WHERE stage NOT IN ('completed','pending')").fetchall()
        for row in rows:
            bid = dict(row)["batch_id"]
            print(f"[MES] 启动传感器模拟: {bid}")
            start_simulation(bid)

    # 自动为所有设备生成维保计划
    db.auto_generate_plans()
    print("[MES] 维保计划初始化完成")

    print("[MES] 服务启动: http://localhost:5002 + ws://localhost:5002/mes")
    socketio.run(app, host="0.0.0.0", port=5002, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
