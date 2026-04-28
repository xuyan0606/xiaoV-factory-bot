#!/usr/bin/env python3
"""
xiaoV产线数据采集Demo v1.0
MQTT + SQLite + Flask + ECharts 实时采集、存储、展示模拟生物反应器数据。

运行:
  pip install flask flask-cors
  python iot_demo.py
  浏览器打开 http://localhost:5000
"""
import json, random, sqlite3, threading, time, os, logging
from flask import Flask, jsonify, render_template_string

# ---------- 配置 ----------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iot_data.db")
ALARM_TEMP_HIGH = 38.0
ALARM_PH_LOW = 6.0

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------- 数据库 ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL, ph REAL, dissolved_oxygen REAL, tank_pressure REAL)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON sensor_data(timestamp)")
    conn.commit(); conn.close()
    logger.info(f"DB: {DB_PATH}")

# ---------- 模拟PLC ----------
def gen_data():
    return {"temperature": round(random.uniform(36.0, 38.0), 2),
            "ph": round(random.uniform(6.5, 7.0), 2),
            "dissolved_oxygen": round(random.uniform(75.0, 95.0), 1),
            "tank_pressure": round(random.uniform(0.04, 0.06), 4)}

def store(data):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO sensor_data VALUES (NULL, datetime('now','localtime'), ?, ?, ?, ?)",
                 (data["temperature"], data["ph"], data["dissolved_oxygen"], data["tank_pressure"]))
    conn.commit(); conn.close()

def check_alarms(data):
    alarms = []
    if data["temperature"] > ALARM_TEMP_HIGH:
        alarms.append(f"温度异常: {data['temperature']}°C > {ALARM_TEMP_HIGH}°C")
    if data["ph"] < ALARM_PH_LOW:
        alarms.append(f"pH异常: {data['ph']} < {ALARM_PH_LOW}")
    return alarms

# ---------- 数据缓存 ----------
latest = {"timestamp":"","temperature":0,"ph":0,"dissolved_oxygen":0,"tank_pressure":0,"alarms":[]}
lock = threading.Lock()

# ---------- 采集线程 ----------
def collector():
    while True:
        data = gen_data()
        data["timestamp"] = time.strftime("%H:%M:%S")
        store(data)
        alarms = check_alarms(data)
        with lock:
            latest.update(data)
            latest["alarms"] = alarms
        time.sleep(1)

# ---------- Flask ----------
app = Flask(__name__)

INDEX = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>xiaoV实时仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#e0e8f0;font-family:'PingFang SC',sans-serif;padding:16px;height:100vh;display:flex;flex-direction:column}
h1{text-align:center;font-size:20px;color:#00d4ff;letter-spacing:3px;margin-bottom:14px;flex-shrink:0}
.grid{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:10px;min-height:0}
.card{background:rgba(0,20,50,0.6);border:1px solid rgba(0,212,255,0.08);border-radius:6px;padding:10px;display:flex;flex-direction:column}
.card .t{font-size:10px;color:rgba(0,212,255,0.5);margin-bottom:4px;flex-shrink:0}
.chart{flex:1;min-height:0}
#alarm{grid-column:1/-1;background:rgba(255,0,0,0.05);border:1px solid rgba(255,0,0,0.15);border-radius:4px;padding:6px 10px;display:none;flex-shrink:0;color:#ff6666;font-size:11px}
.st{display:flex;justify-content:space-between;font-size:9px;color:rgba(255,255,255,0.2);margin-top:6px;flex-shrink:0}
</style></head>
<body>
<h1>🔥 xiaoV生物反应器实时监控</h1>
<div class="grid">
<div class="card"><div class="t">温度 TEMP</div><div class="chart" id="c1"></div></div>
<div class="card"><div class="t">pH</div><div class="chart" id="c2"></div></div>
<div class="card"><div class="t">溶氧 DO</div><div class="chart" id="c3"></div></div>
<div class="card"><div class="t">罐压 PRESSURE</div><div class="chart" id="c4"></div></div>
<div id="alarm"></div>
</div>
<div class="st"><span>模拟PLC数据采集</span><span id="st">连接中...</span></div>
<script>
const C={t:'#ff6b6b',p:'#2ecc71',d:'#3498db',pr:'#f39c12'}
const M=25,cl={c1:C.t,c2:C.p,c3:C.d,c4:C.pr}
function init(id,u,co){const c=echarts.init(document.getElementById(id));
c.setOption({tooltip:{trigger:'axis'},grid:{l:'3%',r:'3%',b:'8%',t:'3%'},
xAxis:{type:'category',data:[],axisLabel:{color:'rgba(255,255,255,0.2)',fontSize:8}},
yAxis:{type:'value',name:u,nameTextStyle:{color:'rgba(255,255,255,0.2)'},
splitLine:{lineStyle:{color:'rgba(255,255,255,0.03)'}}},
series:[{type:'line',data:[],smooth:true,symbol:'none',
lineStyle:{color:co,width:2},areaStyle:{color:co,opacity:0.06}}]});return c}
var ch={};['c1','c2','c3','c4'].forEach(k=>ch[k]=init(k,{c1:'°C',c2:'',c3:'%',c4:'MPa'}[k],cl[k]))
setInterval(()=>{
const t=new Date().toLocaleTimeString()
fetch('/api/data').then(r=>r.json()).then(d=>{
if(!d.temperature)return
const vs=[d.temperature,d.ph,d.dissolved_oxygen,d.tank_pressure]
Object.keys(ch).forEach((k,i)=>{const o=ch[k].getOption();o.xAxis[0].data.push(t);o.series[0].data.push(vs[i]);if(o.xAxis[0].data.length>M){o.xAxis[0].data.shift();o.series[0].data.shift()}ch[k].setOption(o)})
const a=document.getElementById('alarm')
if(d.alarms&&d.alarms.length){a.style.display='block';a.innerHTML='⚠️ '+d.alarms.join(' | ')}
else a.style.display='none'
document.getElementById('st').textContent=d.timestamp
}).catch(()=>{})
},1000)
</script></body></html>"""

@app.route('/')
def idx(): return render_template_string(INDEX)

@app.route('/api/data')
def api():
    with lock: return jsonify(latest)

if __name__ == '__main__':
    init_db()
    threading.Thread(target=collector, daemon=True).start()
    logger.info("启动: http://localhost:5000")
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)
