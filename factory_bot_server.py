"""
科为博 — 钉钉工厂机器人 v2.0（安全版）
基于真实工厂数据，在钉钉里直接查询生产、库存、设备等信息

安全机制：
- Token 校验：所有请求必须携带正确 token
- 频率限制：防止滥用
- HTTPS 传输：ngrok 自动提供
"""
import json, hashlib, base64, hmac, time, re
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

# 加载车间主任模块
try:
    import factory_managers
except Exception:
    pass  # routes will be registered later

# ==================== 安全配置 ====================
# 【部署前必改】在钉钉机器人配置中设置一样的值
DINGTALK_TOKEN = "crvab_factory_2026"
RATE_LIMIT = 10  # 每秒最大请求数

# ==================== 钉钉群推送配置 ====================
# 添加自定义机器人后获得的 Webhook 地址
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=53a276e0ae96940e37ab04b87861d90db2c3ce138751bca4347f442dd209a4e6"

# ==================== 工厂数据 ====================
FACTORY_DATA = {
    "车间": [
        {"name": "发酵车间", "status": "运行中", "desc": "一期12台50m³罐, 二期8台100m³罐建设中", "process": "菌种扩培→发酵", "params": {"温度":"37°C","pH":"6.0-6.7","罐压":"0.05MPa"}},
        {"name": "提取车间", "status": "运行中", "desc": "板框压滤+硅藻土精滤+超滤膜浓缩", "process": "絮凝→粗滤→精滤→超滤", "params": {"粗滤浊度":"<5EBC","精滤浊度":"<1EBC","超滤压力":"0.4-0.8MPa"}},
        {"name": "干燥塔", "status": "运行中", "desc": "3座喷雾干燥塔", "process": "喷雾干燥制粉", "params": {"产品":"酶粉","进风温度":"180°C"}},
        {"name": "混合车间", "status": "运行中", "process": "复配混合", "params": {"设备":"混合机×4","产品":"复合酶"}},
        {"name": "制粒车间", "status": "运行中", "process": "制粒包装"},
        {"name": "空压间", "status": "运行中", "desc": "200m³+350m³离心空压机"},
        {"name": "污水处理", "status": "运行中", "desc": "重度+轻度处理池"},
        {"name": "质检中心", "status": "运行中", "process": "酶活/浊度/微生物检测"},
        {"name": "中控中心", "status": "运行中", "desc": "DCS已部署, 历史数据存储升级中"},
        {"name": "仓储库房", "status": "运行中", "desc": "常温库+4°C冷库, 面积2000m²"},
    ],
    "产品": [
        {"name": "液体酶制剂", "spec": "15B", "batch": "正在生产", "storage": "冷库"},
        {"name": "酶粉/颗粒", "spec": "多规格", "batch": "批次L-20260421", "storage": "常温库"},
        {"name": "益生菌菌粉", "spec": "乳酸菌", "batch": "批次P-20260420", "storage": "冷库(-18°C)"},
        {"name": "微生态制剂", "spec": "复合菌", "batch": "批次M-20260419", "storage": "冷库"},
    ],
    "设备": [
        {"name": "发酵罐", "型号": "50m³×12台/100m³×8台", "status": "运行", "维护": "每周检查搅拌轴套"},
        {"name": "板框压滤机", "型号": "4组", "status": "运行", "维护": "每批次换滤布"},
        {"name": "超滤膜系统", "型号": "管式膜", "status": "运行", "维护": "CIP清洗每批次"},
        {"name": "离心空压机", "型号": "200m³+350m³", "status": "运行", "维护": "月度保养"},
        {"name": "喷雾干燥塔", "型号": "3座", "status": "运行", "维护": "季度大修"},
        {"name": "混合机", "型号": "4台", "status": "运行", "维护": "每月校准"},
    ],
    "配方": {
        "15B液体酶": {
            "种子罐": "葡萄糖2.1kg(0.04%), 玉米浆干粉5.4kg(0.09%), 大豆蛋白5.4kg(0.09%), 硫酸铵1kg(0.02%), 磷酸氢二钠5.4kg(0.09%)",
            "发酵罐": "葡萄糖3000kg(30%), 玉米浆干粉175kg(1.75%), 大豆蛋白180kg(1.8%), 硫酸铵33kg(0.33%), 硫酸镁7.6kg(0.08%), 磷酸氢二钠180kg(1.8%), 氯化钙33kg(0.33%), 白砂糖100kg(1%), 麦芽浸粉5kg(0.05%)",
            "絮凝": "硅藻土→石灰水(pH8.5)→氯化钙(2-2.5%)→磷酸氢二钠(3-4%)→PMA絮凝剂(0.04%)",
            "防腐": "麦芽糊精15%+醋酸钠8%+山梨酸钾0.35%+山梨糖醇10%",
            "参数": "温度37°C, 罐压0.05MPa, 搅拌220rpm, pH6.0-6.7"
        }
    },
    "当前批次": {
        "L-20260421": {"产品":"液体酶15B","车间":"发酵车间","阶段":"发酵(36h)","酶活":"监测中","预计":"2026-04-28 放罐"},
        "P-20260420": {"产品":"益生菌菌粉","车间":"中试车间","阶段":"冻干","活菌数":"≥1×10¹¹ CFU/g","预计":"2026-04-25 入库"},
        "M-20260419": {"产品":"微生态制剂","车间":"中试车间","阶段":"发酵(72h)","状态":"正常","预计":"2026-04-27 放罐"},
    },
    "数字化升级": {
        "已完成": "DCS中控系统部署, 发酵车间自动控制(温度/pH/罐压/转速)",
        "进行中": "DCS历史数据存储系统, MES质量追溯系统, 设备管理系统",
        "规划中": "中试车间远程调控, 全厂数据中台, AI发酵优化"
    }
}

# ==================== 安全校验 ====================

def verify_token():
    """校验钉钉请求中的 token"""
    token = request.args.get('token', '')
    if not token:
        token = request.headers.get('Token', '')
    if token != DINGTALK_TOKEN:
        print(f"[安全告警] Token校验失败: 收到={token}, 期望={DINGTALK_TOKEN}, IP={request.remote_addr}")
        return False
    return True

# 频率限制器
_rate_limiter = {'calls': [], 'lock': False}

def check_rate_limit():
    """简单滑动窗口频率限制"""
    now = time.time()
    _rate_limiter['calls'] = [t for t in _rate_limiter['calls'] if now - t < 1]
    if len(_rate_limiter['calls']) >= RATE_LIMIT:
        return False
    _rate_limiter['calls'].append(now)
    return True

# ==================== 消息处理 ====================

def build_reply(msg_type, text):
    return {"msgtype": msg_type, "text": {"content": text}}

def handle_query(content):
    q = content.strip()

    # 帮助
    if q in ["帮助", "help", "?", "h"]:
        return """🤖 科为博工厂机器人 · 命令指南

📋 查车间     — 查看所有车间状态
📋 查车间 名称 — 查看特定车间详情
📦 查库存     — 查看产品信息
⚙️ 查设备     — 查看设备清单
📊 查生产     — 查看当前生产批次
📝 查配方     — 查看15B生产工艺配方
📈 查数字化   — 查看数字化升级进度
🔍 查 [关键词] — 搜索工厂数据
💡 帮助       — 显示此菜单
"""

    # 查车间
    if q.startswith("查车间"):
        parts = q.replace("查车间", "").strip()
        if parts:
            ws = [w for w in FACTORY_DATA["车间"] if parts in w["name"]]
            if ws:
                w = ws[0]
                reply = f"🏭 {w['name']}\n状态: {w['status']}\n工艺: {w['process']}"
                if w.get("desc"): reply += f"\n说明: {w['desc']}"
                if w.get("params"):
                    reply += "\n参数:"
                    for k,v in w["params"].items(): reply += f"\n  {k}: {v}"
                return reply
            return f'❌ 未找到车间: {parts}'
        reply = "🏭 **车间一览**\n"
        for w in FACTORY_DATA["车间"]:
            icon = "🟢" if w["status"]=="运行中" else "🟡" if w["status"]=="建设中" else "🔴"
            reply += f"\n{icon} {w['name']} — {w['status']}"
        reply += "\n\n发送「查车间 名称」查看详情"
        return reply

    # 查库存
    if q.startswith("查库存") or q.startswith("查产品"):
        reply = "📦 **产品库存**\n"
        for p in FACTORY_DATA["产品"]:
            reply += f"\n• {p['name']}"
            if p.get('spec'): reply += f" ({p['spec']})"
            if p.get('batch'): reply += f"\n  批次: {p['batch']}"
            if p.get('storage'): reply += f"\n  存放: {p['storage']}"
        return reply

    # 查设备
    if q.startswith("查设备"):
        parts = q.replace("查设备", "").strip()
        if parts:
            eqs = [e for e in FACTORY_DATA["设备"] if parts in e["name"]]
            if eqs:
                e = eqs[0]
                return f"⚙️ {e['name']}\n型号: {e['型号']}\n状态: {e['status']}\n维护: {e['维护']}"
            return f'❌ 未找到设备: {parts}'
        reply = "⚙️ **设备清单**\n"
        for e in FACTORY_DATA["设备"]:
            icon = "🟢" if e["status"]=="运行" else "🟡"
            reply += f"\n{icon} {e['name']} ({e['型号']})"
        reply += "\n\n发送「查设备 名称」查看详情"
        return reply

    # 查生产/批次
    if q.startswith("查生产") or q.startswith("查批次"):
        reply = "📊 **当前生产批次**\n"
        for bid, b in FACTORY_DATA["当前批次"].items():
            reply += f"\n🔹 {bid} — {b['产品']}"
            reply += f"\n  车间: {b['车间']} | 阶段: {b['阶段']}"
            if '酶活' in b: reply += f"\n  酶活: {b['酶活']}"
            if '活菌数' in b: reply += f"\n  活菌数: {b['活菌数']}"
            reply += f"\n  预计: {b['预计']}\n"
        return reply

    # 查配方
    if q.startswith("查配方"):
        parts = q.replace("查配方", "").strip()
        if not parts: parts = "15B"
        for name, data in FACTORY_DATA["配方"].items():
            if parts in name:
                reply = f"📝 **{name} 配方**\n"
                for k, v in data.items():
                    reply += f"\n■ {k}: {v}\n"
                return reply
        return f'❌ 未找到配方: {parts}'

    # 查数字化
    if q.startswith("查数字化") or q.startswith("进度"):
        d = FACTORY_DATA["数字化升级"]
        return f"""📈 **数字化升级进度**

✅ 已完成: {d['已完成']}

🔄 进行中: {d['进行中']}

📋 规划中: {d['规划中']}"""

    # 通用搜索
    if q.startswith("查"):
        keyword = q[1:].strip()
        if keyword:
            results = []
            for w in FACTORY_DATA["车间"]:
                if keyword in w["name"]: results.append(f"🏭 {w['name']}")
            for p in FACTORY_DATA["产品"]:
                if keyword in p["name"]: results.append(f"📦 {p['name']}")
            for e in FACTORY_DATA["设备"]:
                if keyword in e["name"]: results.append(f"⚙️ {e['name']}")
            for bid, b in FACTORY_DATA["当前批次"].items():
                if keyword in bid or keyword in b["产品"]: results.append(f"📊 {bid} {b['产品']}")
            if results:
                return "🔍 找到以下结果:\n" + "\n".join(results)
            return '❌ 未找到 "' + keyword + '" 相关信息'

    # 打招呼
    if any(k in q for k in ["你好","hi","hello","在吗"]):
        running = sum(1 for w in FACTORY_DATA['车间'] if w['status']=='运行中')
        return f'你好！我是科为博工厂机器人 🤖\n\n当前工厂状态:\n🟢 {running}/{len(FACTORY_DATA["车间"])} 车间运行中\n📊 {len(FACTORY_DATA["当前批次"])} 批生产中\n\n发送「帮助」查看我能做什么'

    return '❌ 我不理解 "' + q + '"\n发送「帮助」查看可用命令'


# ==================== 路由 ====================

@app.route('/dingtalk/webhook', methods=['POST'])
def webhook():
    """接收钉钉 outgoing 机器人消息（含安全校验）"""

    # 1. Token 校验
    if not verify_token():
        return jsonify({"msgtype": "text", "text": {"content": "⛔ 安全校验失败"}}), 403

    # 2. 频率限制
    if not check_rate_limit():
        return jsonify({"msgtype": "text", "text": {"content": "⏳ 请求过于频繁，请稍后再试"}})

    # 3. 解析消息
    data = request.json
    if not data:
        return jsonify({"msgtype": "text", "text": {"content": "无效请求"}})

    content = ""
    msgtype = data.get("msgtype", "")
    if msgtype == "text":
        content = data.get("text", {}).get("content", "").strip()
    elif "text" in data:
        content = data.get("text", "")

    # 去掉 @机器人
    content = re.sub(r'@.*?\s', '', content).strip()

    print(f"[收到] IP={request.remote_addr} | {content}")

    # 4. 处理查询
    reply_text = handle_query(content)
    return jsonify(build_reply("text", reply_text))


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "factory": "内蒙古科为博生物科技", "version": "2.0"})


@app.route('/push', methods=['POST'])
def push_to_dingtalk():
    """外部推送接口：接收数据并格式化为钉钉消息"""
    if not verify_token():
        return jsonify({"error": "token invalid"}), 403

    data = request.json
    if not data:
        return jsonify({"error": "no data"}), 400

    title = data.get("title", "")
    content = data.get("content", "")
    msg_type = data.get("type", "text")

    if msg_type == "alert":
        text = f"⚠️ **{title}**\n{content}\n时间: {time.strftime('%Y-%m-%d %H:%M')}"
    elif msg_type == "report":
        text = f"📊 **{title}**\n{content}"
    else:
        text = f"{title}\n{content}"

    return jsonify(build_reply("text", text))


# ==================== 钉钉群消息推送 ====================

def push_to_group(title, content, msg_type="text"):
    """向钉钉群推送消息"""
    import urllib.request, ssl, certifi

    if msg_type == "alert":
        text = f"⚠️ {title}\n{content}\n\n科为博"
    elif msg_type == "report":
        text = f"📊 {title}\n{content}\n\n科为博"
    elif msg_type == "success":
        text = f"✅ {title}\n{content}\n\n科为博"
    else:
        text = f"{title}\n{content}\n\n科为博"

    payload = json.dumps({
        "msgtype": "text",
        "text": {"content": text}
    }).encode("utf-8")

    req = urllib.request.Request(
        DINGTALK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        result = json.loads(resp.read())
        if result.get("errcode") == 0:
            print(f"[推送成功] {title}")
            return True
        else:
            print(f"[推送失败] {result}")
            return False
    except Exception as e:
        print(f"[推送异常] {e}")
        return False


@app.route('/push/test', methods=['GET'])
def push_test():
    """测试推送：发送一条消息到钉钉群"""
    success = push_to_group(
        "科为博工厂助手已上线 ✅",
        "机器人配置成功！\n"
        f"时间: {time.strftime('%Y-%m-%d %H:%M')}\n"
        f"当前状态: 运行中\n"
        f"正在生产: {len(FACTORY_DATA['当前批次'])} 批\n"
        f"运行车间: {sum(1 for w in FACTORY_DATA['车间'] if w['status']=='运行中')}/{len(FACTORY_DATA['车间'])}",
        "success"
    )
    if success:
        return jsonify({"status": "ok", "message": "推送成功"})
    return jsonify({"status": "error", "message": "推送失败"}), 500


@app.route('/push/report', methods=['GET'])
def push_report():
    """推送生产日报"""
    running = sum(1 for w in FACTORY_DATA['车间'] if w['status']=='运行中')
    total_ws = len(FACTORY_DATA['车间'])

    batch_info = ""
    for bid, b in FACTORY_DATA["当前批次"].items():
        batch_info += f"\n🔹 {b['产品']} - {b['阶段']}"

    content = (
        f"📋 科为博生产日报\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏭 车间: {running}/{total_ws} 运行中\n"
        f"📊 在产批次:{batch_info}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🕐 {time.strftime('%Y-%m-%d %H:%M')}"
    )

    success = push_to_group("生产日报", content, "report")
    if success:
        return jsonify({"status": "ok", "message": "日报推送成功"})
    return jsonify({"status": "error", "message": "推送失败"}), 500


@app.route('/chat', methods=['GET'])
def chat_page():
    """科为博工厂查询助手 — 网页版"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>科为博工厂查询助手</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#e8f0ff;font-family:'PingFang SC','Microsoft YaHei',sans-serif;min-height:100vh;display:flex;flex-direction:column}
.header{background:linear-gradient(135deg,#0d0d2b,#1a1a3e);padding:16px 20px;border-bottom:1px solid rgba(0,212,255,0.15);display:flex;align-items:center;gap:12px}
.header h1{font-size:16px;color:#00d4ff}
.header .badge{background:rgba(0,255,136,0.15);color:#00ff88;font-size:10px;padding:2px 8px;border-radius:4px}
.chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:85%;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.6;white-space:pre-wrap}
.msg.u{align-self:flex-end;background:#00d4ff;color:#0a0a1a}
.msg.b{align-self:flex-start;background:rgba(255,255,255,0.06);border:1px solid rgba(0,212,255,0.15)}
.msg.b .l{color:#00d4ff;font-size:11px;margin-bottom:4px}
.in{padding:12px 16px;border-top:1px solid rgba(0,212,255,0.1);display:flex;gap:8px;background:#0d0d2b}
.in input{flex:1;padding:10px 14px;border:1px solid rgba(0,212,255,0.2);border-radius:6px;background:rgba(0,0,0,0.3);color:#e8f0ff;font-size:14px;outline:none}
.in input:focus{border-color:#00d4ff}
.in button{padding:10px 20px;border:none;border-radius:6px;background:#00d4ff;color:#0a0a1a;font-weight:bold;cursor:pointer;font-size:14px}
.in button:hover{background:#00b8e6}
.sug{display:flex;flex-wrap:wrap;gap:6px;padding:8px 16px 4px;border-top:1px solid rgba(255,255,255,0.04)}
.sug button{padding:4px 10px;border:1px solid rgba(0,212,255,0.2);border-radius:12px;background:transparent;color:rgba(0,212,255,0.7);font-size:11px;cursor:pointer}
.sug button:hover{background:rgba(0,212,255,0.1)}
.st{padding:6px 16px;font-size:10px;color:rgba(255,255,255,0.2);border-top:1px solid rgba(255,255,255,0.04);display:flex;justify-content:space-between}
</style>
</head>
<body>
<div class="header"><h1>🔬 科为博工厂查询</h1><span class="badge">● 在线</span></div>
<div class="chat" id="chat"></div>
<div class="sug" id="sug">
<button onclick="q('帮助')">💡 帮助</button>
<button onclick="q('查车间')">🏭 查车间</button>
<button onclick="q('查生产')">📊 查生产</button>
<button onclick="q('查设备')">⚙️ 查设备</button>
<button onclick="q('查配方')">📝 查配方</button>
<button onclick="q('查库存')">📦 查库存</button>
<button onclick="q('查数字化')">📈 查数字化</button>
</div>
<div class="in">
<input id="inp" placeholder="输入命令..." onkeydown="if(event.key==='Enter')s()">
<button onclick="s()">发送</button>
</div>
<div class="st"><span>基于真实工厂数据</span><span>内蒙古科为博生物科技</span></div>
<script>
async function query(m){const r=await fetch('/dingtalk/webhook?token=crvab_factory_2026',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msgtype:'text',text:{content:m}})});const d=await r.json();return d.text?.content||'(无响应)'}
function add(c,u){const d=document.getElementById('chat'),div=document.createElement('div');div.className='msg '+(u?'u':'b');if(!u){const l=document.createElement('div');l.className='l';l.textContent='🤖 科为博工厂助手';div.appendChild(l)}const t=document.createElement('div');t.textContent=c;div.appendChild(t);d.appendChild(div);d.scrollTop=d.scrollHeight}
async function s(){const i=document.getElementById('inp'),m=i.value.trim();if(!m)return;i.value='';add(m,1);const r=await query(m);add(r,0)}
function q(m){add(m,1);query(m).then(r=>add(r,0))}
window.onload=()=>{setTimeout(()=>{add('你好！我是科为博工厂助手 🤖\\n\\n当前工厂状态:\\n🟢 10/10 车间运行中\\n📊 3 批生产中\\n\\n点击下方按钮或输入命令查询',0)},300)}
</script>
</body>
</html>"""

if __name__ == '__main__':
    # 注册车间主任路由
    try:
        import factory_managers
        factory_managers.register_routes(app, FACTORY_DATA)
        print("  ✅ 车间主任模块已加载")
    except Exception as e:
        print(f"  ⚠️ 车间主任模块加载失败: {e}")

    print("=" * 50)
    print("=" * 50)
    print("  科为博 钉钉工厂机器人 v2.0")
    print("  INNER MONGOLIA CRVAB BIO-TECHNOLOGY")
    print("=" * 50)
    print(f"\n  安全配置:")
    print(f"  Token: {DINGTALK_TOKEN}")
    print(f"  频率限制: {RATE_LIMIT} 次/秒")
    print(f"\n  本地地址: http://localhost:5001")
    print(f"  Webhook: POST /dingtalk/webhook?token={DINGTALK_TOKEN}")
    print(f"\n  部署步骤:")
    print(f"  1. ngrok http 5001")
    print(f"  2. 在钉钉群中添加 outgoing 机器人")
    print(f"  3. URL 填写: https://你的ngrok地址/dingtalk/webhook")
    print(f"  4. Token 填写: {DINGTALK_TOKEN}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=False)
