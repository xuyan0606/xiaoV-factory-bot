#!/usr/bin/env python3
"""
科为博工厂 — 设备维保 RAG 知识库
纯 Python 实现：TF-IDF 向量化 + 余弦相似度搜索
零外部依赖
"""
import json, math, re, os, sqlite3, hashlib
from datetime import datetime
from collections import Counter

STOP_WORDS = set("的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 怎么 如何 哪个 怎么 为 对 从 于 被 把 让 向 往 用 以 及 所 将 通过 进行 可以 需要 这个 那个 请 问".split())

class Tokenizer:
    """简单中文分词器（基于二元语法+词典匹配）"""
    def __init__(self, dict_words=None):
        self.dict = set(dict_words or []) 
        # 设备相关词典
        self.dict.update([
            "发酵罐", "空压机", "干燥塔", "离心机", "板框过滤", "换热器",
            "水泵", "风机", "电机", "阀门", "仪表", "传感器", "管道",
            "温度", "pH", "压力", "液位", "转速", "流量", "溶氧",
            "提取", "制粒", "混合", "灭菌", "CIP", "SIP",
            "轴承", "密封", "润滑油", "过滤器", "膜组件",
            "PLC", "DCS", "变频器", "接触器", "继电器",
            "螺栓", "垫片", "法兰", "管件"
        ])

    def segment(self, text):
        """基于最大正向匹配 + 单字组合"""
        text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
        words = []
        i = 0
        while i < len(text):
            if text[i] == ' ':
                i += 1
                continue
            matched = False
            # 优先匹配词典（最长5字）
            for end in range(min(i + 5, len(text)), i, -1):
                if text[i:end] in self.dict:
                    words.append(text[i:end])
                    i = end
                    matched = True
                    break
            if not matched:
                words.append(text[i])
                i += 1
        return [w for w in words if w.strip() and w not in STOP_WORDS]


class TfidfVectorizer:
    """TF-IDF 向量化"""
    def __init__(self):
        self.idf = {}        # word -> idf
        self.vocab = {}      # word -> index
        self.doc_count = 0
        self.doc_freq = Counter()

    def fit(self, documents):
        """训练：计算IDF"""
        self.doc_count = len(documents)
        for doc in documents:
            terms = set(doc)
            for term in terms:
                self.doc_freq[term] += 1

        for term, freq in self.doc_freq.items():
            self.idf[term] = math.log((self.doc_count + 1) / (freq + 1)) + 1

        self.vocab = {term: i for i, term in enumerate(sorted(self.idf.keys()))}

    def transform(self, tokens):
        """文档转 TF-IDF 向量"""
        vec = [0.0] * len(self.vocab)
        term_counts = Counter(tokens)
        for term, count in term_counts.items():
            if term in self.vocab:
                tf = count / len(tokens) if tokens else 0
                vec[self.vocab[term]] = tf * self.idf.get(term, 1)
        return vec

    @staticmethod
    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        n_a = math.sqrt(sum(x * x for x in a))
        n_b = math.sqrt(sum(x * x for x in b))
        if n_a == 0 or n_b == 0:
            return 0
        return dot / (n_a * n_b)


class KnowledgeBase:
    """RAG 知识库 — 设备维保问答"""
    def __init__(self, db_path=None):
        self.tokenizer = Tokenizer()
        self.vectorizer = TfidfVectorizer()
        self.documents = []     # [(chunk_id, title, content, tokens), ...]
        self.vectors = []       # [tfidf_vector, ...]
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), 'knowledge_base.db')
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, content TEXT, category TEXT,
            created_at TEXT, source TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT, answer TEXT, score REAL,
            created_at TEXT)""")
        conn.commit()
        conn.close()

    def add_document(self, title, content, category="通用", source=""):
        """添加知识文档"""
        tokens = self.tokenizer.segment(content)
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO documents (title, content, category, created_at, source) VALUES (?,?,?,?,?)",
                    (title, content, category, datetime.now().isoformat(), source))
        conn.commit()
        conn.close()

        self.documents.append((len(self.documents), title, content, tokens))
        return len(self.documents) - 1

    def load_from_db(self):
        """从数据库加载所有文档"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT id, title, content, category FROM documents").fetchall()
        conn.close()
        self.documents = []
        for row in rows:
            tokens = self.tokenizer.segment(row[2])
            self.documents.append((row[0], row[1], row[2], tokens))
        return len(self.documents)

    def build_index(self):
        """构建 TF-IDF 索引"""
        if not self.documents:
            return
        docs_text = [list(set(d[3])) for d in self.documents]  # 去重
        self.vectorizer.fit(docs_text)

        self.vectors = []
        for doc in self.documents:
            vec = self.vectorizer.transform(doc[3])
            self.vectors.append(vec)

    def search(self, query, top_k=3):
        """搜索最相关文档"""
        query_tokens = self.tokenizer.segment(query)
        query_vec = self.vectorizer.transform(query_tokens)

        # 计算余弦相似度
        scores = []
        for i, vec in enumerate(self.vectors):
            score = TfidfVectorizer.cosine_similarity(query_vec, vec)
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: -x[1])
        results = []
        for i, score in scores[:top_k]:
            doc_id, title, content, _ = self.documents[i]
            results.append({"doc_id": doc_id, "title": title, "content": content, "score": round(score, 4)})
        return results

    def ask(self, question, top_k=3):
        """问一个知识问题，返回最相关的文档片段"""
        results = self.search(question, top_k)
        if not results:
            return {"question": question, "answer": "抱歉，知识库中没有找到相关信息。", "sources": []}

        # 拼接上下文
        context = "\n\n".join([f"[{r['title']}] {r['content'][:500]}" for r in results])
        answer = f"根据知识库中的相关文档，为您找到以下信息：\n\n{context}"

        # 记录查询
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO queries (question, answer, score, created_at) VALUES (?,?,?,?)",
                    (question, answer, results[0]['score'], datetime.now().isoformat()))
        conn.commit()
        conn.close()

        return {
            "question": question,
            "answer": answer,
            "sources": [r['title'] for r in results],
            "score": results[0]['score']
        }


def seed_knowledge_base(kb):
    """填充设备维保知识"""
    docs = [
        ("发酵罐日常巡检", "category:发酵设备",
         """发酵罐日常巡检要点：
1. 检查罐体外观有无腐蚀、裂纹、变形
2. 检查人孔、手孔密封是否良好，有无泄漏
3. 检查搅拌电机运行电流是否正常，轴承温度不超过70℃
4. 检查机械密封冲洗系统压力0.3-0.5MPa
5. 检查温度传感器、pH计、溶氧电极等仪表是否正常工作
6. 检查蒸汽灭菌管路、冷凝水管路有无泄漏
7. 每班检查视镜是否清洁透明
8. 记录发酵罐运行参数：温度、pH、DO、转速、罐压"""),

        ("空压机维护保养", "category:空压设备",
         """空压机维护保养规程：
1. 每日：检查油位、冷却水流量、排气温度(≤110℃)、运行压力
2. 每周：排放冷凝水、检查安全阀、清洗空气滤清器
3. 每月：更换油过滤器、检查皮带张紧度、测试保护装置
4. 每季度：更换润滑油(螺杆式空压机专用油)、清洗冷却器
5. 每年：大修更换轴承、密封件、进气阀维修
6. 紧急停机条件：异响、振动过大、排气温度超限、油压过低
7. 常见故障：排气温度高(冷却不良)、油耗大(密封老化)、压力不足(进气阀故障)"""),

        ("干燥塔操作规程", "category:干燥设备",
         """喷雾干燥塔操作要点：
1. 开机前检查：雾化器润滑油位、喷孔是否堵塞、热风系统正常
2. 进风温度控制：进风180-220℃，排风80-100℃
3. 塔体负压控制：-50~-200Pa
4. 雾化器转速：根据产品粒度要求调节(通常10000-18000rpm)
5. 物料浓度：固形物含量20-50%
6. 停机：先停进料，用水冲洗雾化器，逐步降温
7. 清洗：每批结束后CIP清洗，塔壁无挂粉
8. 每月：检查布袋除尘器、旋风分离器"""),

        ("离心机维护", "category:分离设备",
         """离心机日常维护：
1. 启动前检查：转鼓内无异物、轴承润滑良好、刹车系统正常
2. 运行监控：振动值≤4.5mm/s、轴承温度≤65℃、电流稳定
3. 每班：检查滤布或滤网完整性、清理积料
4. 每周：检查皮带张紧度、清洗转鼓内部
5. 每月：更换润滑油、检查密封件、紧固地脚螺栓
6. 每半年：全面检修主轴、轴承、差速器
7. 常见故障：振动大(布料不均/轴承磨损)、分离效果差(滤布破损/转速不足)、漏液(机械密封失效)"""),

        ("CIP清洗系统", "category:清洗系统",
         """CIP在线清洗操作规程：
1. 清洗程序：水洗→碱洗(2%NaOH, 75-80℃, 30min)→中间水洗→酸洗(1%HNO3, 65-70℃, 20min)→最终水洗
2. 清洗流量：管道流速≥1.5m/s，确保湍流
3. 检测项：清洗后pH中性、电导率达标、无肉眼可见残留
4. 记录：每次CIP记录清洗时间、温度、浓度、流量
5. 常见问题：清洗不彻底(流量不足/温度不够)、碱液浓度不足(补充不及时)"""),

        ("板框过滤机操作", "category:过滤设备",
         """板框过滤机操作维护：
1. 压紧：油压15-20MPa，确保各板框密封无泄漏
2. 进料：先低流量进料，待滤饼形成后逐步增加
3. 过滤压力：≤0.6MPa
4. 卸料：松开压紧装置，逐片卸料，清理滤布
5. 滤布更换：视滤布破损情况，通常每2-4周更换
6. 维护：每季度检查油路密封、液压油更换"""),

        ("电机维护保养", "category:电气设备",
         """电机日常维护：
1. 每日：检查运行电流、温升(≤80K)、振动、异响
2. 每周：清洁风扇罩、检查接线盒密封
3. 每月：测量绝缘电阻(≥0.5MΩ)、检查轴承润滑
4. 每季度：更换润滑脂、检查电缆接头
5. 每年：大修更换轴承、检查定子绕组
6. 防爆电机特殊要求：隔爆面清洁无锈、紧固螺栓扭矩达标"""),

        ("DCS系统维护", "category:控制系统",
         """DCS集散控制系统维护：
1. 每日：检查控制器CPU负荷率(≤50%)、网络状态、IO模块通信
2. 每周：备份组态文件、检查操作站显示、测试报警功能
3. 每月：清理机柜过滤网、检查UPS电池状态
4. 每季度：检查接地电阻(≤4Ω)、端子排紧固
5. 每年：系统全面备份、版本升级评估
6. 故障处理：IO模块故障先检查接线再换模块、通信中断检查交换机/网线"""),

        ("蒸汽系统管理", "category:公用工程",
         """蒸汽系统运行维护：
1. 锅炉：定期排污(每班1次)、水质化验(硬度≤0.03mmol/L)
2. 分汽缸：每天排水、检查安全阀
3. 管道：每月检查保温层完好、疏水阀工作正常
4. 蒸汽品质：压力稳定±0.05MPa、温度达标
5. 节能：检查凝结水回收率(目标≥80%)、疏水阀漏气率(目标≤3%)"""),

        ("微生物发酵常见问题", "category:发酵工艺",
         """发酵过程常见问题及处理：
1. 染菌：检查无菌空气系统、灭菌温度时间、设备泄漏点
2. 产率低：优化培养基配方、调整温度/pH/溶氧参数
3. 泡沫过多：调整搅拌转速、添加消泡剂(少量多次)
4. 溶氧不足：提高搅拌转速、增加通气量、降低罐压
5. pH失控：检查pH计校准、调整补酸补碱速率
6. 菌种退化：定期复壮、优化保藏条件(-80℃或液氮)"""),

        ("换热器维护", "category:换热设备",
         """换热器维护保养：
1. 板式换热器：定期清洗板片(碱洗+酸洗)、检查密封垫片老化
2. 管壳式换热器：检查管束结垢情况、清洗管程/壳程
3. 运行监控：进出口温差、压差(压差增大说明结垢)
4. 清洗周期：视水质情况，通常3-6个月
5. 维修：密封垫片更换、管束堵管(不超过总管数10%)"""),

        ("安全阀管理", "category:安全设备",
         """安全阀管理规程：
1. 每年强制校验(法定要求)
2. 每班检查铅封完好、泄放管畅通
3. 整定压力：工作压力的1.05-1.1倍
4. 泄放量应满足最大工况需求
5. 泄放后复位压力不低于整定压力的90%
6. 记录：校验日期、整定压力、校验机构"""),
    ]

    for title, category, content in docs:
        kb.add_document(title, content, category)
        print(f"  📚 添加文档: {title}")

    kb.build_index()
    print(f"\n  共加载 {len(docs)} 篇维保知识文档")


# 直接运行：命令行问答
if __name__ == '__main__':
    import sys
    kb = KnowledgeBase()
    n = kb.load_from_db()
    if n == 0:
        print("首次运行，加载知识库...")
        seed_knowledge_base(kb)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        result = kb.ask(question)
        print(f"\n问题: {result['question']}")
        print(f"匹配度: {result['score']}")
        print(f"来源: {result['sources']}")
        print(f"\n回答:\n{result['answer']}")
    else:
        print("\n科为博设备维保知识库 RAG 系统")
        print("输入问题查询，输入 q 退出")
        print("=" * 50)
        while True:
            q = input("\n问题: ").strip()
            if q.lower() in ('q', 'quit', 'exit'):
                break
            if not q:
                continue
            result = kb.ask(q)
            print(f"\n📖 来源: {', '.join(result['sources'])} (匹配度: {result['score']})")
            print(f"\n{result['answer']}")
