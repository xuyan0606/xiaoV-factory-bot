#!/usr/bin/env python3
"""
xiaoV Industrial IoT — 熔断器 + 指数退避重试
Circuit Breaker pattern: CLOSED → OPEN → HALF_OPEN → CLOSED
"""
import time, logging, functools
from enum import Enum

logging.basicConfig(level=logging.INFO, format='[CB] %(message)s')
log = logging.getLogger('CB')

class CircuitState(Enum):
    CLOSED = 'CLOSED'        # 正常工作
    OPEN = 'OPEN'            # 熔断开启
    HALF_OPEN = 'HALF_OPEN'  # 半开，尝试恢复

class CircuitBreaker:
    def __init__(self, name, failure_threshold=5, recovery_timeout=10, half_open_max=3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_attempts = 0
        self.last_failure_time = 0
        self.total_calls = 0
        self.total_failures = 0

    def call(self, func, *args, **kwargs):
        """执行受保护调用"""
        self.total_calls += 1

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                log.info(f"[{self.name}] OPEN→HALF_OPEN 尝试恢复")
                self.state = CircuitState.HALF_OPEN
                self.half_open_attempts = 0
            else:
                raise Exception(f"熔断器[{self.name}] OPEN, 请求被拒绝")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_max:
                log.info(f"[{self.name}] HALF_OPEN→CLOSED 恢复成功")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.half_open_attempts = 0
        self.failure_count = 0

    def _on_failure(self):
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                log.warning(f"[{self.name}] CLOSED→OPEN 触发熔断")
                self.state = CircuitState.OPEN

    def __call__(self, func):
        """装饰器模式"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper


def retry(max_retries=3, base_delay=1, max_delay=30):
    """指数退避重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        log.warning(f"重试 {attempt+1}/{max_retries}: {e}, 等待{delay}s")
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


# 示例使用
if __name__ == '__main__':
    cb = CircuitBreaker("PLC连接", failure_threshold=3, recovery_timeout=5)

    import random

    @cb
    @retry(max_retries=2, base_delay=1)
    def read_plc():
        if random.random() < 0.7:  # 70%失败率
            raise ConnectionError("PLC连接超时")
        return {"temperature": 36.5, "ph": 6.8}

    for i in range(15):
        try:
            data = read_plc()
            log.info(f"✅ 读取成功: {data}")
        except Exception as e:
            log.error(f"❌ 读取失败: {e}")
        time.sleep(0.5)

    log.info(f"统计: 总调用={cb.total_calls}, 失败={cb.total_failures}, 最终状态={cb.state.value}")
