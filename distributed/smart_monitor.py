#!/usr/bin/env python3
"""
科为博工厂 — 智能监控中心
集成 RAG 知识库 + 时序异常检测 + 钉钉告警
"""
import sys, os, json, time, random, logging, threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_knowledge_base import KnowledgeBase, seed_knowledge_base
from anomaly_detector import AnomalyMonitor, simulate_sensor_data

logging.basicConfig(level=logging.INFO, format='[SMART] %(message)s')
log = logging.getLogger('SMART')

class SmartMonitoringCenter:
    """监控中心 — 融合 RAG 问答 + 异常检测 + 告警"""
    def __init__(self):
        self.kb = KnowledgeBase()
        self.anomaly = AnomalyMonitor(window_size=50)
        self.alert_history = []
        self._init_kb()

    def _init_kb(self):
        n = self.kb.load_from_db()
        if n == 0:
            log.info("初始化知识库...")
            seed_knowledge_base(self.kb)

    def ask(self, question):
        """RAG 知识问答"""
        return self.kb.ask(question)

    def feed_sensor(self, device_id, metric, value):
        """送入传感器数据并检测异常"""
        result = self.anomaly.feed(device_id, metric, value)
        if result["is_anomaly"]:
            alert = {
                "type": "anomaly",
                "device": device_id,
                "metric": metric,
                "value": value,
                "votes": result["votes"],
                "details": result["details"],
                "timestamp": datetime.now().isoformat(),
                "message": f"[{device_id}] {metric} 异常, 值={value:.2f}, {result['votes']}个检测器告警"
            }
            self.alert_history.append(alert)
            log.warning(f"🚨 {alert['message']}")
        return result

    def get_status(self):
        return {
            "status": "running",
            "knowledge_docs": len(self.kb.documents),
            "anomaly_stats": self.anomaly.get_stats(),
            "recent_alerts": len(self.alert_history[-20:]),
            "total_alerts": len(self.alert_history)
        }

    def get_anomaly_report(self):
        return self.anomaly.generate_report()

    def diagnose_anomaly(self, device_id, metric):
        """异常诊断 — 结合知识库解释异常原因"""
        question = f"{device_id} {metric} 异常原因及处理方法"
        kb_result = self.kb.ask(question)

        device_alerts = [a for a in self.alert_history
                        if a["device"] == device_id and a["metric"] == metric]

        return {
            "device": device_id,
            "metric": metric,
            "recent_alerts": len(device_alerts),
            "knowledge_advice": kb_result["answer"][:500],
            "sources": kb_result["sources"]
        }

    def generate_dingtalk_message(self, max_alerts=5):
        """生成钉钉群消息格式"""
        recent = self.alert_history[-max_alerts:] if self.alert_history else []

        lines = ["**科为博智能监控日报**", ""]

        # 知识库统计
        lines.append(f"📚 知识库: {len(self.kb.documents)}篇设备维保文档")
        lines.append(f"📊 异常检测: {self.anomaly.get_stats()['anomaly_rate']}%异常率")
        lines.append("")

        # 最近告警
        if recent:
            lines.append("**⚠️ 最近告警**")
            for a in reversed(recent):
                lines.append(f"- {a['device']} {a['metric']}: {a['value']:.2f} ({a['votes']}票)")
            lines.append("")

        # 建议
        lines.append("💡 **建议**")
        if self.anomaly.anomaly_count > 10:
            lines.append("- 异常率偏高，建议检查相关设备运行状态")
            lines.append("- 可输入\"查询 [设备名] 维保\"获取维护手册")
        else:
            lines.append("- 设备运行状态良好，继续保持")

        return "\n".join(lines)


# 模拟运行
if __name__ == '__main__':
    center = SmartMonitoringCenter()

    print("=" * 50)
    print("  科为博智能监控中心")
    print("=" * 50)

    # 模拟传感器流
    for t in range(100):
        for dev in ["发酵罐-01", "发酵罐-02", "发酵罐-03"]:
            for metric, normal in [("温度", 36), ("pH", 6.8), ("罐压", 0.8)]:
                v = simulate_sensor_data(normal, 0.04)
                center.feed_sensor(dev, metric, v)
        time.sleep(0.02)

    # RAG 问答测试
    print("\n" + "=" * 50)
    print("RAG 问答测试")
    print("=" * 50)
    for q in ["空压机温度过高怎么办", "发酵罐染菌如何处理", "CIP清洗流程"]:
        result = center.ask(q)
        print(f"\nQ: {q}")
        print(f"来源: {', '.join(result['sources'])} (匹配度: {result['score']})")

    print("\n" + "=" * 50)
    print("异常诊断测试")
    print("=" * 50)
    diagnosis = center.diagnose_anomaly("发酵罐-01", "温度")
    print(f"设备: {diagnosis['device']} / {diagnosis['metric']}")
    print(f"近期告警: {diagnosis['recent_alerts']}次")
    print(f"知识库建议: {diagnosis['knowledge_advice'][:200]}...")

    print("\n" + "=" * 50)
    print("钉钉推送消息预览")
    print("=" * 50)
    print(center.generate_dingtalk_message())
