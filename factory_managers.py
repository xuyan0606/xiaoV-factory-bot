"""
xiaoV Virtual Factory — 多车间主任机器人系统 v2.1
基于真实组织架构设计 + MoE Gate 路由（参考 DeepSeek-V3 MoE 架构）
+ FlashMLA 风格的分页块缓存（SessionHistory + block_table）

使用方法：from factory_managers import register_routes; register_routes(app, FACTORY_DATA)
"""
import json, time, re
from flask import request, jsonify

FACTORY_DATA = {}

# ==================== FlashMLA 风格分页块缓存 ====================
# 灵感来自 FlashMLA 的 block_table 管理：将对话历史分块存储，
# 类似于 FlashMLA 的 virtual block -> physical block mapping
# 
# 设计原则：
# - 每个 block 固定存储 N 条消息（page_block_size）
# - block_table 维护 session_id -> [block_id, block_id, ...]
# - 超过阈值（MAX_BLOCKS）时压缩旧 block 为摘要

PAGE_BLOCK_SIZE = 10      # 每个 block 固定 10 条消息（类似 FlashMLA page_block_size）
MAX_BLOCKS = 5            # 超过 5 个 block 自动压缩旧 block
COMPRESSED_MARKER = "__compressed__"  # 压缩 block 的标识

# 全局存储
_block_storage = {}       # block_id -> list[message_dict]  物理块存储
_block_table = {}         # session_id -> list[block_id]   虚拟到物理的映射

class SessionHistory:
    """
    FlashMLA 风格的分页对话历史管理器
    
    类似于 FlashMLA 的 block_table 机制：
    - virtual_block_ids: 逻辑上的 block 序列（session 相关）
    - physical_blocks: 实际存储的消息块（page_block_size 条消息/block）
    
    当对话超过 MAX_BLOCKS 个 block 时，自动压缩旧的 block 为摘要。
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._ensure_table_entry()
    
    def _ensure_table_entry(self):
        """确保 session 在 block_table 中有条目"""
        if self.session_id not in _block_table:
            _block_table[self.session_id] = []
    
    def _create_block(self) -> str:
        """创建一个新的物理 block，返回 block_id"""
        block_id = f"block_{self.session_id}_{len(_block_storage)}_{int(time.time()*1000)}"
        _block_storage[block_id] = []
        return block_id
    
    def _get_or_create_block(self) -> tuple[str, list]:
        """获取当前最新的 block，如果没有则创建"""
        block_ids = _block_table.get(self.session_id, [])
        if not block_ids:
            block_id = self._create_block()
            _block_table[self.session_id].append(block_id)
            return block_id, _block_storage[block_id]
        
        last_block_id = block_ids[-1]
        block = _block_storage.get(last_block_id)
        if block is None:
            # 块丢失，创建一个新块
            block_id = self._create_block()
            _block_table[self.session_id].append(block_id)
            return block_id, _block_storage[block_id]
        
        if len(block) >= PAGE_BLOCK_SIZE:
            # 当前块已满，创建新块
            block_id = self._create_block()
            _block_table[self.session_id].append(block_id)
            return block_id, _block_storage[block_id]
        
        return last_block_id, block
    
    def append(self, role: str, content: str):
        """追加一条消息到历史"""
        block_id, block = self._get_or_create_block()
        block.append({"role": role, "content": content})
        
        # 检查是否需要压缩
        self._check_compress()
    
    def _check_compress(self):
        """检查是否需要压缩旧 blocks"""
        block_ids = _block_table.get(self.session_id, [])
        if len(block_ids) > MAX_BLOCKS:
            self._compress_old_blocks()
    
    def _compress_old_blocks(self):
        """压缩旧 blocks 为摘要（保留最近 MAX_BLOCKS 个）"""
        block_ids = _block_table.get(self.session_id, [])
        if len(block_ids) <= MAX_BLOCKS:
            return
        
        # 需要压缩的 blocks 数量
        compress_count = len(block_ids) - MAX_BLOCKS
        
        # 收集要压缩的消息（从最早的开始）
        messages_to_summarize = []
        for i in range(compress_count):
            block_id = block_ids[i]
            block = _block_storage.get(block_id, [])
            if block and not block[0].get(COMPRESSED_MARKER):
                messages_to_summarize.extend(block)
        
        if not messages_to_summarize:
            return
        
        # 生成压缩摘要
        summary = self._generate_summary(messages_to_summarize)
        
        # 创建压缩后的摘要 block
        compressed_block_id = self._create_block()
        _block_storage[compressed_block_id] = [
            {COMPRESSED_MARKER: True, "summary": summary}
        ]
        
        # 替换 block_table 中的旧 blocks 为压缩 block
        _block_table[self.session_id] = [compressed_block_id] + block_ids[compress_count:]
        
        # 清理旧的 physical blocks（可以被 GC）
        for i in range(compress_count):
            old_block_id = block_ids[i]
            if old_block_id in _block_storage:
                del _block_storage[old_block_id]
    
    def _generate_summary(self, messages: list) -> str:
        """生成压缩摘要（简单的策略：提取关键信息）"""
        if not messages:
            return ""
        
        # 简单策略：计算各 role 的消息数，提取首尾关键内容
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        assistant_msgs = [m["content"] for m in messages if m.get("role") == "assistant"]
        
        summary_parts = []
        if user_msgs:
            summary_parts.append(f"用户提问 {len(user_msgs)} 次，涉及: {user_msgs[0][:50]}{'...' if len(user_msgs[0])>50 else ''}")
        if assistant_msgs:
            summary_parts.append(f"助手回复 {len(assistant_msgs)} 次")
        
        return " | ".join(summary_parts) if summary_parts else f"历史对话 {len(messages)} 条"
    
    def get_all_messages(self) -> list:
        """获取完整的消息历史（包括压缩摘要）"""
        block_ids = _block_table.get(self.session_id, [])
        all_messages = []
        
        for block_id in block_ids:
            block = _block_storage.get(block_id, [])
            if not block:
                continue
            
            # 检查是否是压缩 block
            if block[0].get(COMPRESSED_MARKER):
                all_messages.append({
                    "role": "system",
                    "content": f"[早期对话摘要] {block[0].get('summary', '')}"
                })
            else:
                all_messages.extend(block)
        
        return all_messages
    
    def get_page(self, page: int = 1, page_size: int = 20) -> dict:
        """获取分页历史（兼容旧 API）"""
        all_messages = self.get_all_messages()
        total = len(all_messages)
        total_pages = max(1, (total + page_size - 1) // page_size)
        
        start = (page - 1) * page_size
        end = start + page_size
        page_messages = all_messages[start:end]
        
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "messages": page_messages
        }
    
    def clear(self):
        """清除该 session 的所有 blocks"""
        block_ids = _block_table.get(self.session_id, [])
        for block_id in block_ids:
            if block_id in _block_storage:
                del _block_storage[block_id]
        _block_table[self.session_id] = []
    
    @staticmethod
    def get_block_info(session_id: str) -> dict:
        """获取 session 的 block 状态信息（调试用）"""
        block_ids = _block_table.get(session_id, [])
        info = {
            "session_id": session_id,
            "block_count": len(block_ids),
            "blocks": []
        }
        for bid in block_ids:
            block = _block_storage.get(bid, [])
            info["blocks"].append({
                "block_id": bid,
                "message_count": len(block),
                "is_compressed": bool(block and block[0].get(COMPRESSED_MARKER))
            })
        return info


def get_history(key: str) -> SessionHistory:
    """获取或创建 session 的历史管理器"""
    return SessionHistory(key)


# 保留旧接口的兼容函数（用于现有代码）
conversations = {}

def _legacy_get_history(key):
    """旧版 get_history 兼容函数（内部使用）"""
    if key not in conversations:
        conversations[key] = []
    return conversations[key]

# ==================== MoE Gate 路由层 ====================
# 灵感来自 DeepSeek-V3 MoE：输入经过 Gate 路由器，选择 top-k 最相关的 expert 并行处理
# 区别：DeepSeek 用 MLP+sigmoid 评分，这里用关键词共现+权重评分

EXPERT_HANDLERS = {}  # 动态注册：expert_name -> (keywords, handler_fn)

def register_expert(name, keywords, handler_fn):
    """注册一个专家 handler（类似 DeepSeek MoE 的 Expert 注册）"""
    EXPERT_HANDLERS[name] = {"keywords": keywords, "handler": handler_fn}

def _score_experts(query: str) -> list[tuple[str, float]]:
    """计算每个 expert 对当前 query 的相关性分数（参考 DeepSeek Gate）"""
    q = query.lower()
    scores = {}
    for name, spec in EXPERT_HANDLERS.items():
        score = 0.0
        for kw in spec["keywords"]:
            if kw in q:
                score += 1.0
        scores[name] = score
    # 按分数降序排列，取 top-3
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [(n, s) for n, s in ranked if s > 0]

def gate_route(query: str, person_id: str, p: dict, compressed: bool = False) -> str:
    """MoE Gate 路由：参考 DeepSeek Gate.forward() — 只激活 top-k experts
    
    Args:
        query: 用户查询
        person_id: 会话/人物 ID
        p: 人物信息字典
        compressed: 是否处于压缩模式（长对话自动启用）
    """
    emoji = p["emoji"]
    title = p["title"]

    # Step 1: Gate 计算各 expert 分数
    scored = _score_experts(query)

    # Step 2: 无匹配 → 走默认兜底
    if not scored:
        return default_handler(emoji, title)

    # Step 3: 取 top-k（k=2，避免回答过长）
    topk = scored[:2]
    results = []

    for expert_name, score in topk:
        handler = EXPERT_HANDLERS[expert_name]["handler"]
        result = handler(query, person_id, p)
        if result:
            results.append(result)

    if not results:
        return default_handler(emoji, title)

    # Step 4: 多 expert 结果合并（类似 MoE 的 weighted sum）
    base_reply = "\n\n".join(results)
    
    # 如果是长对话压缩模式，在回复末尾添加提示
    if compressed:
        base_reply += "\n\n[注：对话历史较长，部分早期内容已压缩为摘要]"
    
    return base_reply

# ==================== 默认兜底 ====================

def default_handler(emoji, title):
    return f"{emoji} {title}：你问的这个我需要确认一下。\n\n可以问我车间状态、生产进度、设备情况、配方参数。\n或者问我的上级/下属关系。"

# ==================== 组织架构数据 ====================

ORG_STRUCTURE = {
    "总经理":          {"title":"总经理","emoji":"👔","color":"#ff4444","desc":"公司最高管理者，统筹全局","subordinates":["生产总监","技术总监","技术部","质量管理部","安环部","销售部","采购部","财务部","人力资源部"]},
    "生产总监":        {"title":"生产总监","emoji":"🏭","color":"#ff8844","desc":"管辖全厂生产，确保产量和质量达标","supervisor":"总经理","subordinates":["干燥车间","混合车间","污水车间","维修车间","发酵车间","提取车间","制粒车间","仓储部"]},
    "技术总监":        {"title":"技术总监","emoji":"🔬","color":"#00d4ff","desc":"领导生物技术研究院，负责研发和技术创新","supervisor":"总经理","subordinates":["生物技术研究院","技术部"]},
    "干燥车间":        {"title":"干燥车间主任","emoji":"🔥","color":"#ff8844","desc":"管理3座喷雾干燥塔的干燥制粉生产","supervisor":"生产总监"},
    "混合车间":        {"title":"混合车间主任","emoji":"🔄","color":"#ff8844","desc":"负责酶制剂复配混合生产","supervisor":"生产总监"},
    "污水车间":        {"title":"污水车间主任","emoji":"💧","color":"#66bbaa","desc":"管理重度+轻度污水处理，确保达标排放","supervisor":"生产总监"},
    "维修车间":        {"title":"维修车间主任","emoji":"🔧","color":"#ff6688","desc":"全厂设备维护保养、应急维修、空压机管理","supervisor":"生产总监"},
    "发酵车间":        {"title":"发酵车间主任","emoji":"🧪","color":"#00d4ff","desc":"管理一期12台50m³+二期8台100m³发酵罐","supervisor":"生产总监"},
    "提取车间":        {"title":"提取车间主任","emoji":"⚗️","color":"#00ff88","desc":"管理絮凝→粗滤→精滤→超滤全流程","supervisor":"生产总监"},
    "制粒车间":        {"title":"制粒车间主任","emoji":"💊","color":"#ff8844","desc":"负责酶制剂和益生菌颗粒产品生产","supervisor":"生产总监"},
    "仓储部":          {"title":"仓储主任","emoji":"📦","color":"#aa66ff","desc":"管理常温库2000m²+4°C冷库","supervisor":"生产总监"},
    "生物技术研究院":  {"title":"研究院院长","emoji":"🎓","color":"#00d4ff","desc":"领导6大研究中心","supervisor":"技术总监","subordinates":["酶制剂应用研究中心","发酵工艺研究中心","检测评估中心","益生菌应用研究中心","菌种管理保藏中心","合成生物学创新中心"]},
    "酶制剂应用研究中心": {"title":"酶制剂研究中心主任","emoji":"🧬","color":"#00d4ff","desc":"负责酶制剂的应用研发、配方优化、客户技术支持","supervisor":"生物技术研究院"},
    "发酵工艺研究中心": {"title":"发酵工艺研究中心主任","emoji":"🔬","color":"#00d4ff","desc":"负责发酵工艺优化、新菌种放大、工艺参数研究","supervisor":"生物技术研究院"},
    "检测评估中心":    {"title":"检测评估中心主任","emoji":"📋","color":"#ffcc00","desc":"负责酶活检测、理化分析、微生物检测、稳定性评估","supervisor":"生物技术研究院"},
    "益生菌应用研究中心": {"title":"益生菌研究中心主任","emoji":"🦠","color":"#00d4ff","desc":"负责益生菌菌种筛选、功效评价、应用开发","supervisor":"生物技术研究院"},
    "菌种管理保藏中心": {"title":"菌种保藏中心主任","emoji":"🧫","color":"#00d4ff","desc":"负责菌种筛选、保藏、活化、供应管理","supervisor":"生物技术研究院"},
    "合成生物学创新中心": {"title":"合成生物学中心主任","emoji":"🧪","color":"#aa66ff","desc":"负责基因编辑、代谢工程、合成生物学平台建设","supervisor":"生物技术研究院"},
    "技术部":          {"title":"技术部部长","emoji":"📐","color":"#44aaff","desc":"负责工艺技术标准、技术文档、生产技术支持","supervisor":"技术总监"},
    "质量管理部":      {"title":"质量部部长","emoji":"✅","color":"#ffcc00","desc":"负责质量管理体系、质量控制、客户验厂","supervisor":"总经理"},
    "安环部":          {"title":"安环部部长","emoji":"🛡️","color":"#66bbaa","desc":"负责安全生产、环保合规、职业健康","supervisor":"总经理"},
    "销售部":          {"title":"销售部部长","emoji":"📈","color":"#44aaff","desc":"负责酶制剂、益生菌产品销售和客户开发","supervisor":"总经理"},
    "采购部":          {"title":"采购部部长","emoji":"🛒","color":"#44aaff","desc":"负责原料采购、供应商管理、物流协调","supervisor":"总经理"},
    "财务部":          {"title":"财务部部长","emoji":"💰","color":"#ffcc00","desc":"负责财务管理、成本核算、预算控制","supervisor":"总经理"},
    "人力资源部":      {"title":"人力资源部部长","emoji":"👥","color":"#ff6688","desc":"负责人员招聘、培训、绩效考核","supervisor":"总经理"},
}

conversations = {}

def get_history(key):
    if key not in conversations:
        conversations[key] = []
    return conversations[key]

def generate_reply(person_id, msg):
    p = ORG_STRUCTURE.get(person_id)
    if not p:
        return "未知岗位"
    emoji, title = p["emoji"], p["title"]
    q = msg.lower()

    # 获取 session 历史（使用新的 SessionHistory）
    history = get_history(person_id)

    # 1. 个人级查询不走 MoE Gate（职责明确，不需要路由）
    if any(g in q for g in ["你好","hi","hello","在吗",title[:2]]):
        return f"{emoji} {title}：你好！我是{title}，{p['desc']}。有什么需要帮忙的？"

    if "上级" in q or "汇报" in q or "归谁管" in q:
        if "supervisor" in p:
            s = ORG_STRUCTURE.get(p["supervisor"], {})
            return f"{emoji} {title}：我的上级是{s.get('emoji','')} {s.get('title',p['supervisor'])}。"
        return f"{emoji} {title}：我直接向总经理汇报。"

    if "下属" in q or "管哪些" in q or "团队" in q:
        if "subordinates" in p:
            return f"{emoji} {title}：我管辖的部门/岗位：\n"+"\\n".join(f"- {ORG_STRUCTURE.get(s,{}).get('emoji','')} {s}" for s in p["subordinates"])
        return f"{emoji} {title}：我没有直接下属，但跟各部门协同工作。"

    # 2. 工厂数据查询 → MoE Gate 路由（参考 DeepSeek MoE）
    # 检查对话长度，超过阈值时启用压缩摘要
    all_msgs = history.get_all_messages()
    if len(all_msgs) > PAGE_BLOCK_SIZE * 2:
        reply = gate_route(msg, person_id, p, compressed=True)
    else:
        reply = gate_route(msg, person_id, p, compressed=False)
    
    # 追加到历史
    history.append("user", msg)
    history.append("assistant", reply)
    
    return reply


# ==================== 专家 Handler（MoE Expert） ====================
# 每个 handler 签名：(query, person_id, p) -> str | None
# 返回 None 表示该 expert 不处理这个 query

def _h车间(query, person_id, p):
    emoji = p["emoji"]
    if "车间" not in query.lower():
        return None
    r = f"{emoji} {p['title']}：各车间情况：\n"
    for w in FACTORY_DATA.get("车间", []):
        r += f"\n{'🟢' if w['status']=='运行中' else '🟡'} {w['name']} — {w['status']}"
    return r

def _h生产(query, person_id, p):
    emoji = p["emoji"]
    if not any(k in query.lower() for k in ["生产", "批次", "进度"]):
        return None
    r = f"{emoji} {p['title']}：当前在产批次：\n"
    for bid, b in FACTORY_DATA.get("当前批次", {}).items():
        r += f"\n📊 {bid} — {b['产品']} | {b['阶段']}"
    return r

def _h设备(query, person_id, p):
    emoji = p["emoji"]
    if not any(k in query.lower() for k in ["设备", "机器", "故障"]):
        return None
    r = f"{emoji} {p['title']}：设备状态：\n"
    for e in FACTORY_DATA.get("设备", []):
        r += f"\n{'🟢' if e['status']=='运行' else '🔴'} {e['name']} ({e['型号']})"
    return r

def _h配方(query, person_id, p):
    emoji = p["emoji"]
    if "配方" not in query.lower() and "工艺参数" not in query.lower():
        return None
    for n, d in FACTORY_DATA.get("配方", {}).items():
        r = f"{emoji} {p['title']}：{n}配方：\n"
        for k, v in d.items():
            r += f"\n■ {k}: {v[:80]}{'...' if len(v)>80 else ''}"
        return r
    return None

def _h库存(query, person_id, p):
    emoji = p["emoji"]
    if not any(k in query.lower() for k in ["库存", "产品", "存货"]):
        return None
    r = f"{emoji} {p['title']}：产品库存：\n"
    for prod in FACTORY_DATA.get("产品", []):
        r += f"\n📦 {prod['name']} ({prod.get('spec','')}) — {prod.get('storage','')}"
    return r

def _h数字化(query, person_id, p):
    emoji = p["emoji"]
    if not any(k in query.lower() for k in ["数字化", "系统", "升级"]):
        return None
    d = FACTORY_DATA.get("数字化升级", {})
    return f"{emoji} {p['title']}：数字化转型：\n\n✅ {d.get('已完成','')}\n\n🔄 {d.get('进行中','')}\n\n📋 {d.get('规划中','')}"

def _h帮助(query, person_id, p):
    emoji = p["emoji"]
    if not any(k in query.lower() for k in ["帮助", "功能", "能做什么"]):
        return None
    return (f"{emoji} {p['title']}：我能帮你：\n\n"
            f"📋 车间状态\n📊 生产进度\n⚙️ 设备情况\n📝 工艺配方\n📦 产品库存\n📈 数字化进度\n\n"
            f"也可以问我的上级或下属是谁。")

# 注册所有专家（参考 DeepSeek MoE: self.experts = nn.ModuleList([Expert(...) for ...])）
register_expert("车间",     ["车间", "干燥", "混合", "污水", "发酵", "提取", "制粒"], _h车间)
register_expert("生产",     ["生产", "批次", "进度", "产品"],                          _h生产)
register_expert("设备",     ["设备", "机器", "故障", "维修", "维护"],                  _h设备)
register_expert("配方",     ["配方", "工艺参数", "菌种", "培养基"],                    _h配方)
register_expert("库存",     ["库存", "产品", "存货", "仓储", "冷库"],                 _h库存)
register_expert("数字化",   ["数字化", "系统", "升级", "信息化"],                     _h数字化)
register_expert("帮助",     ["帮助", "功能", "能做什么", "菜单"],                     _h帮助)


FACTORY_PAGE = "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">\n<title>xiaoV Virtual Factory — 组织架构</title>\n<style>\n*{margin:0;padding:0;box-sizing:border-box}\nbody{background:#0a0a1a;color:#e8f0ff;font-family:'PingFang SC','Microsoft YaHei',sans-serif;height:100vh;display:flex;flex-direction:column}\n.header{background:linear-gradient(135deg,#0d0d2b,#1a1a3e);padding:12px 16px;border-bottom:1px solid rgba(0,212,255,0.12);display:flex;align-items:center;gap:10px;flex-shrink:0}\n.header h1{font-size:15px;color:#00d4ff;margin:0}\n.badge{background:rgba(0,255,136,0.15);color:#00ff88;font-size:9px;padding:2px 7px;border-radius:4px}\n.main{display:flex;flex:1;overflow:hidden}\n.sidebar{width:210px;background:rgba(0,0,0,0.2);border-right:1px solid rgba(0,212,255,0.08);overflow-y:auto;flex-shrink:0;padding:6px}\n.sec{padding:6px 10px;font-size:10px;color:rgba(255,255,255,0.25);margin-top:6px;letter-spacing:1px}\n.mgr{padding:8px 10px;margin:1px 0;border-radius:5px;cursor:pointer;transition:all.15s;display:flex;align-items:center;gap:7px;font-size:12px}\n.mgr:hover{background:rgba(0,212,255,0.06)}\n.mgr.active{background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.15)}\n.mgr .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}\n.mgr .rl{color:rgba(255,255,255,0.35);font-size:9px}\n.mgr .nm{color:rgba(255,255,255,0.85)}\n.ca{flex:1;display:flex;flex-direction:column}\n.ch{padding:10px 16px;border-bottom:1px solid rgba(0,212,255,0.08);display:flex;align-items:center;gap:8px;flex-shrink:0}\n.ch h2{font-size:14px;margin:0}\n.ch .sb{font-size:11px;color:rgba(255,255,255,0.4)}\n.st{font-size:10px;color:#00ff88;margin-left:auto}\n.ms{flex:1;overflow-y:auto;padding:12px 16px;display:flex;flex-direction:column;gap:10px}\n.msg{max-width:80%;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.7;white-space:pre-wrap}\n.msg.u{align-self:flex-end;background:#00d4ff;color:#0a0a1a}\n.msg.b{align-self:flex-start;background:rgba(255,255,255,0.05);border:1px solid rgba(0,212,255,0.1)}\n.msg.b .w{font-size:11px;margin-bottom:4px;opacity:0.7}\n.in{padding:10px 16px;border-top:1px solid rgba(0,212,255,0.08);display:flex;gap:8px;background:#0d0d2b;flex-shrink:0}\n.in input{flex:1;padding:9px 12px;border:1px solid rgba(0,212,255,0.15);border-radius:6px;background:rgba(0,0,0,0.3);color:#e8f0ff;font-size:13px;outline:none}\n.in input:focus{border-color:#00d4ff}\n.in button{padding:9px 18px;border:none;border-radius:6px;background:#00d4ff;color:#0a0a1a;font-weight:bold;cursor:pointer;font-size:13px}\n.q{padding:6px 16px 8px;display:flex;gap:5px;flex-wrap:wrap;flex-shrink:0;border-top:1px solid rgba(255,255,255,0.03)}\n.q button{padding:3px 9px;border:1px solid rgba(0,212,255,0.15);border-radius:10px;background:transparent;color:rgba(0,212,255,0.6);font-size:10px;cursor:pointer}\n.q button:hover{background:rgba(0,212,255,0.08)}\n@media(max-width:700px){.sidebar{width:50px}.sidebar .mgr span{display:none}}\n</style></head>\n<body>\n<div class=header><h1>🏭 xiaoV Virtual Factory</h1><span class=badge id=ob>●在线</span></div>\n<div class=main>\n<div class=sidebar id=sb></div>\n<div class=ca>\n<div class=ch><h2 id=cn>👔 选择角色</h2><span class=sb id=ct></span><span class=st>●在线</span></div>\n<div class=ms id=ms>\n<div style=text-align:center;color:rgba(255,255,255,0.15);margin-top:60px;font-size:12px;line-height:2>\n🏭 xiaoV Biotech<br><br>左侧选择一位管理者<br>查看组织架构或咨询业务\n</div></div>\n<div class=q id=q></div>\n<div class=in><input id=inp placeholder=输入消息... onkeydown=\"if(event.key==='Enter')s()\"><button onclick=s()>发送</button></div>\n</div></div>\n<script>\nlet orgs={},cur=null;\nasync function init(){\nconst r=await fetch('/api/org');const d=await r.json();orgs=d.orgs;\nconst sb=document.getElementById('sb');\nlet secs={};\nfor(const[id,o]of Object.entries(orgs)){const s=o.supervisor||'核心';if(!secs[s])secs[s]=[];secs[s].push({id,...o})}\nfor(const[s,its]of Object.entries(secs)){\nconst se=document.createElement('div');se.className='sec';se.textContent='▸ '+s;sb.appendChild(se);\nfor(const m of its){\nconst d=document.createElement('div');d.className='mgr';d.dataset.id=m.id;\nd.innerHTML='<div class=dot style=background:'+m.color+'></div><span><div class=nm>'+m.emoji+' '+m.id+'</div><div class=rl>'+m.title+'</div></span>';\nd.onclick=()=>select(m.id);sb.appendChild(d)}}\ndocument.getElementById('ob').textContent='● '+Object.keys(orgs).length+'位在线'}\nasync function select(id){\nif(!orgs[id])return;\ndocument.querySelectorAll('.mgr').forEach(e=>e.classList.toggle('active',e.dataset.id===id));\nconst o=orgs[id];cur=id;\ndocument.getElementById('cn').textContent=o.emoji+' '+o.id;\ndocument.getElementById('ct').textContent=o.title+' | '+o.desc;\ndocument.getElementById('ms').innerHTML='<div style=text-align:center;color:rgba(255,255,255,0.12);margin-top:20px;font-size:12px>与'+o.title+'对话中</div>';\nconst qb=document.getElementById('q');qb.innerHTML='';\n['车间情况','当前生产','设备状态','工艺配方','帮助'].forEach(q=>{const b=document.createElement('button');b.textContent=q;b.onclick=()=>qa(q);qb.appendChild(b)});\na(o.emoji+' '+o.title+'：你好，我是'+o.title+'。有什么可以帮你的？',0,o)}\nfunction a(t,u,p){\nconst ms=document.getElementById('ms');\nconst d=document.createElement('div');d.className='msg '+(u?'u':'b');\nif(!u&&p){const w=document.createElement('div');w.className='w';w.textContent=p.emoji+' '+p.title;d.appendChild(w)}\nconst c=document.createElement('div');c.textContent=t;d.appendChild(c);\nms.appendChild(d);ms.scrollTop=ms.scrollHeight}\nasync function s(){\nconst i=document.getElementById('inp');const m=i.value.trim();\nif(!m||!cur)return;i.value='';\na(m,1,0);\ntry{const r=await fetch('/api/chat2/'+cur,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});const d=await r.json();a(d.reply,0,d.person)}\ncatch(e){a('⚠️ 连接异常',0,0)}}\nasync function qa(q){if(!cur)return;a(q,1,0);const r=await fetch('/api/chat2/'+cur,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q})});const d=await r.json();a(d.reply,0,d.person)}\ninit();\n</script>\n</body></html>"


def register_routes(app, factory_data):
    """注册所有车间主任路由到 Flask app"""
    global FACTORY_DATA
    FACTORY_DATA = factory_data

    @app.route('/api/org', methods=['GET'])
    def get_org():
        tree = {}
        for pid, p in ORG_STRUCTURE.items():
            tree[pid] = {
                "id": pid, "title": p["title"], "emoji": p["emoji"],
                "color": p["color"], "desc": p["desc"],
                "supervisor": p.get("supervisor"),
                "subordinates": p.get("subordinates", []),
            }
        return jsonify({"orgs": tree, "root": "总经理"})

    @app.route('/api/chat2/<person_id>', methods=['POST'])
    def chat_person(person_id):
        if person_id not in ORG_STRUCTURE:
            return jsonify({"error": "未知岗位"}), 404
        data = request.json
        if not data or "message" not in data:
            return jsonify({"error": "请输入消息"}), 400
        msg = data["message"].strip()
        reply = generate_reply(person_id, msg)
        # generate_reply 已经内部处理 history 追加（使用 SessionHistory）
        p = ORG_STRUCTURE[person_id]
        return jsonify({
            "reply": reply,
            "person": {"id": person_id, "name": p["title"], "emoji": p["emoji"], "title": p["title"]}
        })

    @app.route('/api/chat2/<person_id>/history', methods=['GET'])
    def get_chat_history(person_id):
        """获取分页历史记录（新 API）"""
        if person_id not in ORG_STRUCTURE:
            return jsonify({"error": "未知岗位"}), 404
        
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        
        history = get_history(person_id)
        result = history.get_page(page=page, page_size=page_size)
        
        return jsonify({
            "person_id": person_id,
            "history": result
        })

    @app.route('/api/chat2/<person_id>/blocks', methods=['GET'])
    def get_block_info(person_id):
        """获取 block 状态信息（调试用）"""
        if person_id not in ORG_STRUCTURE:
            return jsonify({"error": "未知岗位"}), 404
        
        info = SessionHistory.get_block_info(person_id)
        return jsonify(info)

    @app.route('/api/chat2/<person_id>/clear', methods=['POST'])
    def clear_history(person_id):
        if person_id in _block_table:
            get_history(person_id).clear()
        return jsonify({"status": "ok"})

    @app.route('/factory/org', methods=['GET'])
    def factory_org_page():
        return FACTORY_PAGE, 200, {'Content-Type': 'text/html; charset=utf-8'}
