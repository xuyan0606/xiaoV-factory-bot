#!/usr/bin/env python3
"""
科为博工厂 — 时序数据异常检测
纯 Python 实现：Z-Score / IQR / 移动平均 / 滑动窗口
零外部依赖
"""
import math, json, time, random
from datetime import datetime
from collections import deque
from statistics import mean, stdev, median

class AnomalyDetector:
    """异常检测器基类"""
    def detect(self, value, history=None):
        raise NotImplementedError


class ZScoreDetector(AnomalyDetector):
    """Z-Score 异常检测 — 基于历史均值的标准差"""
    def __init__(self, threshold=3.0, min_samples=10):
        self.threshold = threshold
        self.min_samples = min_samples

    def detect(self, value, history):
        if len(history) < self.min_samples:
            return False, 0.0, "样本不足"
        m = mean(history)
        s = stdev(history)
        if s == 0:
            return False, 0.0, "无波动"
        z = (value - m) / s
        if abs(z) > self.threshold:
            return True, round(z, 2), f"Z-Score={z:.2f} 超过阈值±{self.threshold}"
        return False, round(z, 2), "正常"


class IQRDetector(AnomalyDetector):
    """IQR 四分位距异常检测 — 适合非正态分布"""
    def __init__(self, multiplier=1.5):
        self.multiplier = multiplier

    def detect(self, value, history):
        if len(history) < 5:
            return False, 0.0, "样本不足"
        sorted_vals = sorted(history)
        n = len(sorted_vals)
        q1 = sorted_vals[int(n * 0.25)]
        q3 = sorted_vals[int(n * 0.75)]
        iqr = q3 - q1
        lower = q1 - self.multiplier * iqr
        upper = q3 + self.multiplier * iqr
        if value < lower:
            return True, round(value - lower, 2), f"低于下界 {lower:.2f}"
        if value > upper:
            return True, round(value - upper, 2), f"高于上界 {upper:.2f}"
        return False, round(value - median(history), 2), "正常"


class MADDetector(AnomalyDetector):
    """MAD（中位数绝对偏差）— 对异常值鲁棒"""
    def __init__(self, threshold=3.5):
        self.threshold = threshold

    def detect(self, value, history):
        if len(history) < 5:
            return False, 0.0, "样本不足"
        med = median(history)
        devs = [abs(v - med) for v in history]
        mad = median(devs)
        if mad == 0:
            return False, 0.0, "MAD=0"
        modified_z = 0.6745 * (value - med) / mad
        if abs(modified_z) > self.threshold:
            return True, round(modified_z, 2), f"MAD Z-Score={modified_z:.2f}"
        return False, round(modified_z, 2), "正常"


class RateOfChangeDetector(AnomalyDetector):
    """变化率异常检测 — 检测突变"""
    def __init__(self, threshold_ratio=0.15):
        self.threshold_ratio = threshold_ratio

    def detect(self, value, history):
        if len(history) < 3:
            return False, 0.0, "样本不足"
        prev = history[-1]
        if prev == 0:
            return False, 0.0, "上值为0"
        change = abs((value - prev) / prev)
        if change > self.threshold_ratio:
            return True, round(change * 100, 1), f"变化率 {change*100:.1f}% 超过阈值 {self.threshold_ratio*100:.1f}%"
        return False, round(change * 100, 1), "正常"


class MovingAverageDetector(AnomalyDetector):
    """移动平均偏差检测"""
    def __init__(self, window=10, threshold_std=2.0):
        self.window = window
        self.threshold_std = threshold_std

    def detect(self, value, history):
        if len(history) < self.window:
            return False, 0.0, "样本不足"
        window = history[-self.window:]
        ma = mean(window)
        residuals = [v - ma for v in window]
        s = stdev(residuals) if len(residuals) > 1 else 0
        if s == 0:
            return False, 0.0, "窗口内无波动"
        deviation = (value - ma) / s
        if abs(deviation) > self.threshold_std:
            return True, round(deviation, 2), f"偏离移动平均 {deviation:.2f}σ"
        return False, round(deviation, 2), "正常"


class EnsembleAnomalyDetector:
    """集成检测器 — 多个检测器投票"""
    def __init__(self):
        self.detectors = {
            "zscore": ZScoreDetector(threshold=3.0),
            "iqr": IQRDetector(multiplier=1.5),
            "mad": MADDetector(threshold=3.5),
            "roc": RateOfChangeDetector(threshold_ratio=0.15),
            "ma": MovingAverageDetector(window=10, threshold_std=2.0),
        }
        self.min_votes = 2  # 至少2个检测器判定异常才告警

    def detect(self, value, history, threshold_votes=None):
        votes = 0
        details = []
        threshold_votes = threshold_votes or self.min_votes

        for name, detector in self.detectors.items():
            is_anomaly, score, reason = detector.detect(value, history)
            if is_anomaly:
                votes += 1
                details.append({"detector": name, "score": score, "reason": reason})

        is_anomaly = votes >= threshold_votes
        return {
            "is_anomaly": is_anomaly,
            "votes": votes,
            "threshold": threshold_votes,
            "detectors": len(self.detectors),
            "details": details,
            "value": value,
            "timestamp": datetime.now().isoformat()
        }


class AnomalyMonitor:
    """实时异常监控器 — 按设备/指标维护滑动窗口"""
    def __init__(self, window_size=50):
        self.window_size = window_size
        self.ensemble = EnsembleAnomalyDetector()
        self.history = {}       # device_metric -> deque
        self.anomaly_log = []   # 异常记录
        self.normal_count = 0
        self.anomaly_count = 0

    def _key(self, device_id, metric):
        return f"{device_id}:{metric}"

    def feed(self, device_id, metric, value):
        """送入一条新的传感器数据"""
        key = self._key(device_id, metric)
        if key not in self.history:
            self.history[key] = deque(maxlen=self.window_size)

        hist = list(self.history[key])
        result = self.ensemble.detect(value, hist)
        self.history[key].append(value)

        if result["is_anomaly"]:
            result["device_id"] = device_id
            result["metric"] = metric
            self.anomaly_log.append(result)
            self.anomaly_count += 1
        else:
            self.normal_count += 1

        return result

    def get_recent_anomalies(self, n=10):
        return list(self.anomaly_log[-n:])

    def get_stats(self):
        total = self.normal_count + self.anomaly_count
        return {
            "total_points": total,
            "normal": self.normal_count,
            "anomalies": self.anomaly_count,
            "anomaly_rate": round(self.anomaly_count / total * 100, 2) if total > 0 else 0,
            "monitored_devices": len(set(k.split(":")[0] for k in self.history.keys())),
            "monitored_metrics": len(self.history)
        }

    def generate_report(self):
        """生成异常检测报告"""
        anomalies = self.get_recent_anomalies(20)
        if not anomalies:
            return "✅ 最近未检测到异常"

        lines = ["⚠️ 异常检测报告", "=" * 50]
        for a in reversed(anomalies):
            lines.append(f"[{a['timestamp']}] {a['device_id']} / {a['metric']}")
            lines.append(f"  值: {a['value']:.2f} | 投票: {a['votes']}/{a['detectors']}")
            for d in a['details']:
                lines.append(f"  - {d['detector']}: {d['reason']}")
            lines.append("")
        lines.append(f"统计: 总数据点 {self.normal_count+self.anomaly_count} | 异常率 {self.get_stats()['anomaly_rate']}%")

        # 按设备分组统计
        device_stats = {}
        for a in self.anomaly_log:
            dev = a['device_id']
            if dev not in device_stats:
                device_stats[dev] = {"count": 0, "metrics": {}}
            device_stats[dev]["count"] += 1
            m = a['metric']
            device_stats[dev]["metrics"][m] = device_stats[dev]["metrics"].get(m, 0) + 1

        lines.append(f"\n设备异常统计:")
        for dev, stats in sorted(device_stats.items(), key=lambda x: -x[1]["count"]):
            lines.append(f"  {dev}: {stats['count']}次异常")
            for m, c in stats['metrics'].items():
                lines.append(f"    - {m}: {c}次")

        return "\n".join(lines)


# 模拟传感器数据 + 异常注入
def simulate_sensor_data(normal_temp=36.0, anomaly_chance=0.05):
    """模拟发酵罐温度数据，偶尔注入异常"""
    if random.random() < anomaly_chance:
        return normal_temp + random.choice([-10, -5, 5, 8, 12])  # 异常
    return normal_temp + random.gauss(0, 0.5)  # 正常波动


# 示例
if __name__ == '__main__':
    print("=" * 50)
    print("  科为博工厂 · 时序异常检测系统")
    print("=" * 50)

    monitor = AnomalyMonitor(window_size=50)

    # 模拟3个发酵罐数据
    devs = ["发酵罐-01", "发酵罐-02", "发酵罐-03"]
    metrics = ["温度", "pH", "罐压"]

    # 生成200个时间点
    for t in range(200):
        for dev in devs:
            for metric in metrics:
                if metric == "温度":
                    v = simulate_sensor_data(random.choice([36, 37, 35]), 0.03)
                elif metric == "pH":
                    v = simulate_sensor_data(6.8, 0.02)
                else:
                    v = simulate_sensor_data(0.08, 0.02) * 10

                result = monitor.feed(dev, metric, v)
                if result["is_anomaly"]:
                    print(f"🚨 [{t:03d}s] {dev} {metric} = {v:.2f} 异常 ({result['votes']}票)")

    print(f"\n{monitor.generate_report()}")

    total = monitor.normal_count + monitor.anomaly_count
    expected_anomalies = int(total * 0.03)  # 约3%异常率
    detected = monitor.anomaly_count
    print(f"\n  总数据点: {total}")
    print(f"  检测到异常: {detected} 次")
    print(f"  异常率: {monitor.get_stats()['anomaly_rate']}%")
