# 科为博生物科技 MES 数据库设计

## 工厂背景

- 企业：内蒙古科为博生物科技有限公司 (CRVAB)
- 主营：酶制剂、益生菌、生物发酵
- 发酵车间：一期 12×50m³ + 二期 8×100m³
- 提取车间、干燥塔3座、混合制粒、空压间、变电室、污水池
- 仓储：2000m²常温库 + 冷库
- 其他：中控DCS、质检、维修、中试车间
- 组织：总经理 → 生产总监(8车间) → 技术总监(6研究中心:酶制剂/发酵工艺/益生菌/菌种保藏/合成生物学/检测评估)

---

## 1. 基础数据 (Base Data) — 22表

### 1.1 组织架构

#### org_company (公司)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 公司代码 |
| name | VARCHAR(100) | NOT NULL | 公司名称 |
| address | VARCHAR(200) | | 地址 |
| tel | VARCHAR(20) | | 电话 |
| is_active | BOOLEAN | DEFAULT 1 | 是否启用 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

#### org_department (部门/车间)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 部门代码 |
| name | VARCHAR(100) | NOT NULL | 部门名称 |
| dept_type | VARCHAR(20) | NOT NULL | 类型: workshop(车间)/office(科室)/lab(实验室) |
| parent_id | INTEGER | FK→org_department(id) | 上级部门 |
| manager_id | INTEGER | FK→employee(id) | 负责人 |
| company_id | INTEGER | FK→org_company(id) | 所属公司 |
| sort_order | INTEGER | DEFAULT 0 | 排序 |
| is_active | BOOLEAN | DEFAULT 1 | 是否启用 |

#### org_work_center (工段/班组)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 工段代码 |
| name | VARCHAR(100) | NOT NULL | 工段名称 |
| work_center_type | VARCHAR(20) | NOT NULL | 类型: production(生产)/packing(包装)/utility(公用) |
| department_id | INTEGER | FK→org_department(id) | 所属车间 |
| leader_id | INTEGER | FK→employee(id) | 班长 |
| is_active | BOOLEAN | DEFAULT 1 | 是否启用 |

### 1.2 人员主数据

#### employee (员工)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| emp_no | VARCHAR(20) | NOT NULL UNIQUE | 工号 |
| name | VARCHAR(50) | NOT NULL | 姓名 |
| gender | VARCHAR(4) | | 性别 |
| birth_date | DATE | | 出生日期 |
| id_card | VARCHAR(18) | | 身份证号 |
| phone | VARCHAR(20) | | 手机号 |
| email | VARCHAR(100) | | 邮箱 |
| hire_date | DATE | | 入职日期 |
| department_id | INTEGER | FK→org_department(id) | 所属部门 |
| work_center_id | INTEGER | FK→org_work_center(id) | 所属工段 |
| position | VARCHAR(50) | | 岗位 |
| job_title | VARCHAR(50) | | 职称 |
| education | VARCHAR(20) | | 学历 |
| major | VARCHAR(50) | | 专业 |
| is_active | BOOLEAN | DEFAULT 1 | 在职状态 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | |

#### employee_certification (员工资质)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| employee_id | INTEGER | FK→employee(id) | 员工ID |
| cert_type | VARCHAR(30) | NOT NULL | 资质类型: operator(操作证)/sterilize(灭菌证)/electric(电工)/welder(焊工)/quality(质检员) |
| cert_name | VARCHAR(100) | NOT NULL | 资质名称 |
| cert_no | VARCHAR(50) | | 证书编号 |
| issue_date | DATE | | 发证日期 |
| expire_date | DATE | | 到期日期 |
| issuing_authority | VARCHAR(100) | | 发证机构 |
| is_active | BOOLEAN | DEFAULT 1 | 是否有效 |
| remark | VARCHAR(200) | | 备注 |

#### employee_training (员工培训)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| employee_id | INTEGER | FK→employee(id) | 员工ID |
| training_type | VARCHAR(30) | NOT NULL | 培训类型: gmp/SOP/safety/technical |
| training_name | VARCHAR(100) | NOT NULL | 培训名称 |
| trainer | VARCHAR(50) | | 培训人 |
| training_date | DATE | NOT NULL | 培训日期 |
| duration_hours | DECIMAL(5,1) | | 培训时长(小时) |
| result | VARCHAR(20) | | 结果: pass/fail |
| score | DECIMAL(5,2) | | 考核分数 |
| remark | VARCHAR(200) | | 备注 |

#### employee_shift (排班记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| employee_id | INTEGER | FK→employee(id) | 员工ID |
| shift_date | DATE | NOT NULL | 日期 |
| shift_type | VARCHAR(10) | NOT NULL | 班次: day(白班)/mid(中班)/night(夜班) |
| work_center_id | INTEGER | FK→org_work_center(id) | 工段 |
| is_active | BOOLEAN | DEFAULT 1 | |

### 1.3 物料主数据

#### material_category (物料分类)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 分类编码 |
| name | VARCHAR(100) | NOT NULL | 分类名称 |
| parent_id | INTEGER | FK→material_category(id) | 上级分类 |
| level | INTEGER | DEFAULT 0 | 层级 |
| sort_order | INTEGER | DEFAULT 0 | 排序 |

#### material (物料主数据)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| material_code | VARCHAR(30) | NOT NULL UNIQUE | 物料编码 |
| old_code | VARCHAR(30) | | 旧编码 |
| name | VARCHAR(100) | NOT NULL | 物料名称 |
| english_name | VARCHAR(100) | | 英文名称 |
| category_id | INTEGER | FK→material_category(id) | 物料分类 |
| material_type | VARCHAR(20) | NOT NULL | 类型: raw_material(原料)/auxiliary(辅料)/packaging(包材)/semi(中间品)/finished(成品)/consumable(耗材) |
| spec | VARCHAR(100) | | 规格型号 |
| unit | VARCHAR(10) | NOT NULL | 基本单位: kg/L/piece/bag/drum |
| unit_weight | DECIMAL(10,3) | | 单位重量(kg) |
| density | DECIMAL(10,4) | | 密度(kg/L) |
| cas_no | VARCHAR(20) | | CAS号(化学品) |
| storage_condition | VARCHAR(200) | | 存储条件 |
| shelf_life_days | INTEGER | | 保质期(天) |
| is_active | BOOLEAN | DEFAULT 1 | 是否启用 |
| is_controlled | BOOLEAN | DEFAULT 0 | 是否管制物料 |
| min_stock_qty | DECIMAL(12,3) | | 最低库存量 |
| max_stock_qty | DECIMAL(12,3) | | 最高库存量 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | |

#### material_supplier (物料-供应商关系)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| material_id | INTEGER | FK→material(id) | 物料ID |
| supplier_id | INTEGER | FK→supplier(id) | 供应商ID |
| supplier_material_code | VARCHAR(30) | | 供应商物料编码 |
| is_preferred | BOOLEAN | DEFAULT 0 | 是否首选 |
| approval_status | VARCHAR(20) | DEFAULT 'pending' | 审批状态 |

#### supplier (供应商)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 供应商编码 |
| name | VARCHAR(100) | NOT NULL | 供应商名称 |
| short_name | VARCHAR(50) | | 简称 |
| contact_person | VARCHAR(50) | | 联系人 |
| phone | VARCHAR(20) | | 联系电话 |
| address | VARCHAR(200) | | 地址 |
| tax_no | VARCHAR(30) | | 税号 |
| bank_info | VARCHAR(200) | | 银行信息 |
| supply_category | VARCHAR(50) | | 供应类别 |
| grade | VARCHAR(10) | | 等级: A/B/C |
| is_active | BOOLEAN | DEFAULT 1 | |

#### customer (客户)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 客户编码 |
| name | VARCHAR(100) | NOT NULL | 客户名称 |
| short_name | VARCHAR(50) | | 简称 |
| contact_person | VARCHAR(50) | | 联系人 |
| phone | VARCHAR(20) | | 联系电话 |
| address | VARCHAR(200) | | 地址 |
| grade | VARCHAR(10) | | 等级 |
| is_active | BOOLEAN | DEFAULT 1 | |

### 1.4 设备主数据

#### equipment_category (设备分类)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| code | VARCHAR(20) | NOT NULL UNIQUE | 分类编码 |
| name | VARCHAR(100) | NOT NULL | 分类名称 |
| parent_id | INTEGER | FK→equipment_category(id) | 上级分类 |

#### equipment (设备台账)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equip_no | VARCHAR(30) | NOT NULL UNIQUE | 设备编号 |
| name | VARCHAR(100) | NOT NULL | 设备名称 |
| category_id | INTEGER | FK→equipment_category(id) | 设备分类 |
| equip_type | VARCHAR(30) | NOT NULL | 设备类型: fermenter(发酵罐)/extractor(提取罐)/dryer(干燥塔)/centrifuge(离心机)/compressor(空压机)/heat_exchanger(换热器)/pump(泵)/valve(阀门)/instrument(仪表)/mixer(混合机)/granulator(制粒机)/tank(储罐)/boiler(锅炉)/purifier(纯化水)/other |
| model | VARCHAR(50) | | 型号 |
| spec | VARCHAR(100) | | 规格参数 |
| manufacturer | VARCHAR(100) | | 生产厂家 |
| serial_no | VARCHAR(50) | | 出厂编号 |
| voltage | VARCHAR(20) | | 电压等级 |
| power_kw | DECIMAL(8,2) | | 功率(kW) |
| capacity | VARCHAR(50) | | 容量/处理能力 |
| install_date | DATE | | 安装日期 |
| commission_date | DATE | | 投用日期 |
| department_id | INTEGER | FK→org_department(id) | 使用车间 |
| work_center_id | INTEGER | FK→org_work_center(id) | 使用工段 |
| location | VARCHAR(100) | | 安装位置 |
| equipment_status | VARCHAR(20) | DEFAULT 'idle' | 状态: idle(空闲)/running(运行)/maintenance(维修)/fault(故障)/scrapped(报废) |
| run_status | VARCHAR(20) | DEFAULT 'stopped' | 运行状态: running(运行中)/stopped(停止)/standby(待机) |
| asset_no | VARCHAR(30) | | 固定资产编号 |
| scrap_date | DATE | | 报废日期 |
| is_active | BOOLEAN | DEFAULT 1 | |
| remark | VARCHAR(200) | | 备注 |

#### equipment_parameter (设备参数)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| param_code | VARCHAR(30) | NOT NULL | 参数代码: temp/pH/DO/pressure/speed/flow/level |
| param_name | VARCHAR(50) | NOT NULL | 参数名称 |
| unit | VARCHAR(20) | | 单位 |
| standard_min | DECIMAL(12,4) | | 标准下限 |
| standard_max | DECIMAL(12,4) | | 标准上限 |
| alarm_min | DECIMAL(12,4) | | 报警下限 |
| alarm_max | DECIMAL(12,4) | | 报警上限 |
| precision | INTEGER | DEFAULT 2 | 小数位数 |

#### equipment_document (设备文档)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| doc_type | VARCHAR(30) | NOT NULL | 文档类型: manual(说明书)/drawing(图纸)/certificate(合格证)/warranty(保修卡)/other |
| doc_name | VARCHAR(100) | NOT NULL | 文档名称 |
| file_path | VARCHAR(200) | | 文件路径 |
| upload_date | DATE | | 上传日期 |

## 2. 工艺管理 (Process Management) — 16表

#### product (产品主数据)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| product_code | VARCHAR(30) | NOT NULL UNIQUE | 产品编码 |
| product_name | VARCHAR(100) | NOT NULL | 产品名称 |
| product_type | VARCHAR(20) | NOT NULL | 产品类型: enzyme(酶制剂)/probiotic(益生菌)/intermediate(中间体) |
| spec | VARCHAR(100) | | 规格 |
| unit | VARCHAR(10) | NOT NULL | 单位 |
| yield_unit | VARCHAR(10) | | 产量单位: U/g(酶活)/CFU/g(活菌数) |
| shelf_life_days | INTEGER | | 保质期(天) |
| storage_condition | VARCHAR(200) | | 存储条件 |
| is_active | BOOLEAN | DEFAULT 1 | |

#### product_bom (产品BOM)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| product_id | INTEGER | FK→product(id) | 产品ID |
| material_id | INTEGER | FK→material(id) | 物料ID |
| bom_version | VARCHAR(20) | NOT NULL | BOM版本 |
| sequence_no | INTEGER | | 序号 |
| quantity_per_unit | DECIMAL(12,4) | NOT NULL | 单位用量 |
| unit | VARCHAR(10) | | 用量单位 |
| loss_rate | DECIMAL(5,2) | DEFAULT 0 | 损耗率(%) |
| is_active | BOOLEAN | DEFAULT 1 |
| effective_date | DATE | | 生效日期 |
| expire_date | DATE | | 失效日期 |
| UNIQUE(product_id, material_id, bom_version) | | |

#### route (工艺路线)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| product_id | INTEGER | FK→product(id) | 产品ID |
| route_code | VARCHAR(30) | NOT NULL UNIQUE | 工艺路线编码 |
| route_name | VARCHAR(100) | NOT NULL | 工艺路线名称 |
| route_version | VARCHAR(20) | NOT NULL | 版本号 |
| is_active | BOOLEAN | DEFAULT 1 |
| effective_date | DATE | | 生效日期 |
| expire_date | DATE | | 失效日期 |
| remark | VARCHAR(200) | | 备注 |

#### route_step (工艺步骤)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| route_id | INTEGER | FK→route(id) | 工艺路线ID |
| step_no | INTEGER | NOT NULL | 步骤序号 |
| step_code | VARCHAR(20) | | 步骤代码 |
| step_name | VARCHAR(100) | NOT NULL | 步骤名称 |
| step_type | VARCHAR(20) | NOT NULL | 步骤类型: ferment(发酵)/extract(提取)/dry(干燥)/mix(混合)/granulate(制粒)/cip(CIP清洗)/sterilize(灭菌)/pack(包装)/inprocess(中间品检测) |
| work_center_id | INTEGER | FK→org_work_center(id) | 执行工段 |
| equipment_type | VARCHAR(30) | | 所需设备类型 |
| standard_duration_min | INTEGER | | 标准用时(分钟) |
| is_hold_point | BOOLEAN | DEFAULT 0 | 是否停检点 |
| is_critical | BOOLEAN | DEFAULT 0 | 是否关键步骤 |

#### process_param_template (工艺参数模板)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| route_step_id | INTEGER | FK→route_step(id) | 工艺步骤ID |
| param_code | VARCHAR(30) | NOT NULL | 参数代码: temp/pH/DO/stir_speed/pressure/foam/flow_rate/level |
| param_name | VARCHAR(50) | NOT NULL | 参数名称 |
| unit | VARCHAR(20) | | 单位: ℃/pH/%/rpm/MPa/m³/h |
| standard_min | DECIMAL(12,4) | | 标准下限 |
| standard_max | DECIMAL(12,4) | | 标准上限 |
| alarm_min | DECIMAL(12,4) | | 报警下限 |
| alarm_max | DECIMAL(12,4) | | 报警上限 |
| sample_interval_sec | INTEGER | DEFAULT 300 | 采集间隔(秒) |
| is_required | BOOLEAN | DEFAULT 1 | 是否必填 |
| sort_order | INTEGER | DEFAULT 0 | 排序 |

#### batch_rule (批号规则)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| product_id | INTEGER | FK→product(id) | 产品ID |
| rule_name | VARCHAR(50) | NOT NULL | 规则名称 |
| prefix | VARCHAR(10) | | 前缀: CRVAB |
| date_format | VARCHAR(20) | | 日期格式: YYYYMMDD |
| seq_length | INTEGER | DEFAULT 4 | 流水号长度 |
| separator | VARCHAR(5) | | 分隔符: - |
| sample_rule | VARCHAR(50) | | 示例: CRVAB-20260427-0001 |
| is_active | BOOLEAN | DEFAULT 1 | |

#### batch_number_seq (批号流水号)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| rule_id | INTEGER | FK→batch_rule(id) | 规则ID |
| date_key | VARCHAR(10) | NOT NULL | 日期: 20260427 |
| current_seq | INTEGER | DEFAULT 0 | 当前流水号 |
| UNIQUE(rule_id, date_key) | | |

#### fermentation_formula (发酵配方)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| product_id | INTEGER | FK→product(id) | 产品ID |
| formula_code | VARCHAR(30) | NOT NULL UNIQUE | 配方编码 |
| formula_name | VARCHAR(100) | NOT NULL | 配方名称 |
| batch_size | DECIMAL(12,3) | | 批量(L/kg) |
| target_yield | DECIMAL(12,3) | | 目标产量 |
| formula_version | VARCHAR(20) | | 版本号 |
| is_active | BOOLEAN | DEFAULT 1 |
| effective_date | DATE | |
| remark | VARCHAR(200) | |

#### fermentation_formula_detail (发酵配方明细)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| formula_id | INTEGER | FK→fermentation_formula(id) | 配方ID |
| material_id | INTEGER | FK→material(id) | 物料ID |
| sequence_no | INTEGER | | 序号 |
| quantity | DECIMAL(12,4) | NOT NULL | 用量 |
| unit | VARCHAR(10) | | 单位 |
| add_method | VARCHAR(30) | | 添加方式: batch(一次)/feed(流加)/continuous(连续) |
| add_time_point | VARCHAR(50) | | 添加时间点 |
| remark | VARCHAR(200) | | |

#### sop_document (SOP文档)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| doc_code | VARCHAR(30) | NOT NULL UNIQUE | 文档编号 |
| doc_name | VARCHAR(100) | NOT NULL | 文档名称 |
| doc_type | VARCHAR(20) | NOT NULL | 类型: sop(操作规程)/standard(标准)/method(方法) |
| relate_type | VARCHAR(20) | | 关联类型: product/equipment/step |
| relate_id | INTEGER | | 关联ID |
| version | VARCHAR(10) | | 版本号 |
| content | TEXT | | 内容/路径 |
| is_active | BOOLEAN | DEFAULT 1 |
| effective_date | DATE | |
| review_cycle_days | INTEGER | | 审核周期(天) |

## 3. 生产过程 (Production Process) — 28表

#### work_order (工单)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| order_no | VARCHAR(30) | NOT NULL UNIQUE | 工单编号 |
| product_id | INTEGER | FK→product(id) | 产品ID |
| planned_qty | DECIMAL(12,3) | NOT NULL | 计划数量 |
| unit | VARCHAR(10) | NOT NULL | 单位 |
| route_id | INTEGER | FK→route(id) | 工艺路线ID |
| formula_id | INTEGER | FK→fermentation_formula(id) | 配方ID |
| status | VARCHAR(20) | DEFAULT 'draft' | 状态: draft/pending/approved/released/in_progress/completed/closed/cancelled |
| priority | INTEGER | DEFAULT 5 | 优先级 1-10 |
| plan_start_time | DATETIME | | 计划开始时间 |
| plan_end_time | DATETIME | | 计划结束时间 |
| actual_start_time | DATETIME | | 实际开始时间 |
| actual_end_time | DATETIME | | 实际结束时间 |
| department_id | INTEGER | FK→org_department(id) | 执行车间 |
| created_by | INTEGER | FK→employee(id) | 创建人 |
| approved_by | INTEGER | FK→employee(id) | 批准人 |
| is_active | BOOLEAN | DEFAULT 1 |
| remark | VARCHAR(200) | |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### batch_record (批次记录 — 核心表)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_no | VARCHAR(50) | NOT NULL UNIQUE | 批号: CRVAB-YYYYMMDD-NNNN |
| work_order_id | INTEGER | FK→work_order(id) | 工单ID |
| product_id | INTEGER | FK→product(id) | 产品ID |
| product_name | VARCHAR(100) | | 产品名称 |
| batch_qty | DECIMAL(12,3) | | 批量 |
| batch_unit | VARCHAR(10) | | 批量单位 |
| route_id | INTEGER | FK→route(id) | 工艺路线ID |
| formula_id | INTEGER | FK→fermentation_formula(id) | 配方ID |
| equipment_id | INTEGER | FK→equipment(id) | 主设备(发酵罐)ID |
| status | VARCHAR(20) | DEFAULT 'pending' | 状态: pending(待投料)/feeding(投料中)/fermenting(发酵中)/extracting(提取中)/drying(干燥中)/mixing(混合中)/granulating(制粒中)/packing(包装中)/completed(完成)/quarantine(待检)/released(放行)/rejected(拒绝)/cancelled(取消) |
| fermenter_no | VARCHAR(30) | | 发酵罐编号 |
| strain_name | VARCHAR(100) | | 菌种名称 |
| strain_batch | VARCHAR(50) | | 菌种批号 |
| inoculum_volume | DECIMAL(10,2) | | 接种量(L) |
| start_time | DATETIME | | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| actual_yield | DECIMAL(12,3) | | 实际产量 |
| yield_unit | VARCHAR(10) | | 产量单位 |
| yield_value | DECIMAL(12,2) | | 酶活/活菌数 |
| operator_id | INTEGER | FK→employee(id) | 操作员 |
| supervisor_id | INTEGER | FK→employee(id) | 班长 |
| qc_status | VARCHAR(20) | DEFAULT 'pending' | 质检状态: pending(待检)/sampling(取样)/testing(检测中)/released(放行)/rejected(不合格) |
| is_closed | BOOLEAN | DEFAULT 0 |
| remark | VARCHAR(500) | |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### batch_feeding_record (投料记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| material_id | INTEGER | FK→material(id) | 物料ID |
| material_code | VARCHAR(30) | | 物料编码 |
| material_name | VARCHAR(100) | | 物料名称 |
| material_batch_no | VARCHAR(50) | | 物料批号 |
| planned_qty | DECIMAL(12,4) | | 计划用量 |
| actual_qty | DECIMAL(12,4) | NOT NULL | 实际用量 |
| unit | VARCHAR(10) | NOT NULL | 单位 |
| feed_time | DATETIME | NOT NULL | 投料时间 |
| operator_id | INTEGER | FK→employee(id) | 操作员 |
| checker_id | INTEGER | FK→employee(id) | 复核人 |
| feeding_method | VARCHAR(30) | | 投料方式: manual(人工)/automatic(自动)/feed(流加) |
| is_verified | BOOLEAN | DEFAULT 0 | 是否复核 |
| remark | VARCHAR(200) | | 备注 |

#### batch_ferment_param (发酵过程参数记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| record_time | DATETIME | NOT NULL | 记录时间 |
| temperature | DECIMAL(6,2) | | 温度(℃) |
| ph_value | DECIMAL(4,2) | | pH值 |
| do_value | DECIMAL(5,2) | | 溶氧(%) / DO |
| stir_speed | DECIMAL(6,1) | | 搅拌转速(rpm) |
| tank_pressure | DECIMAL(6,3) | | 罐压(MPa) |
| foam_level | VARCHAR(10) | | 泡沫状态: none/low/mid/high |
| air_flow | DECIMAL(8,2) | | 空气流量(m³/h) |
| od_value | DECIMAL(6,3) | | OD值(菌液浓度) |
| glucose_conc | DECIMAL(6,2) | | 葡萄糖浓度(g/L) |
| nh3_addition | DECIMAL(8,2) | | 氨水补加量(mL) |
| oil_addition | DECIMAL(8,2) | | 消泡剂补加量(mL) |
| feed_rate | DECIMAL(8,2) | | 流加速率(L/h) |
| power_consumption | DECIMAL(10,2) | | 功率消耗(kWh) |
| remark | VARCHAR(200) | |
| UNIQUE(batch_id, record_time) | | |

#### batch_extract_record (提取过程记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| step_name | VARCHAR(50) | NOT NULL | 步骤名称: centrifugation(离心)/filtration(过滤)/concentration(浓缩)/precipitation(沉淀)/dissolution(溶解) |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| start_time | DATETIME | | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| feed_volume | DECIMAL(12,2) | | 进料体积(L) |
| feed_temp | DECIMAL(6,2) | | 进料温度(℃) |
| outlet_temp | DECIMAL(6,2) | | 出料温度(℃) |
| pressure_in | DECIMAL(6,3) | | 进口压力(MPa) |
| pressure_out | DECIMAL(6,3) | | 出口压力(MPa) |
| flow_rate | DECIMAL(8,2) | | 流速(L/h) |
| ph_value | DECIMAL(4,2) | | pH值 |
| added_solvent | VARCHAR(50) | | 添加溶剂 |
| solvent_volume | DECIMAL(10,2) | | 溶剂体积(L) |
| output_volume | DECIMAL(12,2) | | 出料体积(L) |
| yield_pct | DECIMAL(5,2) | | 收率(%) |
| operator_id | INTEGER | FK→employee(id) | 操作员 |
| remark | VARCHAR(200) | | |

#### batch_dry_record (干燥过程记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| equipment_id | INTEGER | FK→equipment(id) | 干燥塔ID |
| start_time | DATETIME | | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| inlet_temp | DECIMAL(6,2) | | 进风温度(℃) |
| outlet_temp | DECIMAL(6,2) | | 出风温度(℃) |
| feed_rate | DECIMAL(8,2) | | 进料速率(L/h) |
| atomizer_speed | DECIMAL(8,2) | | 雾化器转速(rpm) |
| air_pressure | DECIMAL(6,3) | | 压缩空气压力(MPa) |
| feed_volume | DECIMAL(10,2) | | 进料体积(L) |
| feed_concentration | DECIMAL(5,2) | | 进料浓度(%) |
| output_weight | DECIMAL(10,2) | | 出料重量(kg) |
| moisture_pct | DECIMAL(5,2) | | 水分含量(%) |
| yield_pct | DECIMAL(5,2) | | 收率(%) |
| operator_id | INTEGER | FK→employee(id) | |
| remark | VARCHAR(200) | | |

#### batch_mix_record (混合制粒记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| step_type | VARCHAR(20) | NOT NULL | 步骤: mix(混合)/granulate(制粒)/sift(过筛) |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| start_time | DATETIME | | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| material_amount | DECIMAL(10,2) | | 物料量(kg) |
| mixing_time_min | INTEGER | | 混合时间(min) |
| mixing_speed | DECIMAL(8,2) | | 混合转速(rpm) |
| granule_size | VARCHAR(20) | | 颗粒目数 |
| binder_name | VARCHAR(50) | | 粘合剂名称 |
| binder_amount | DECIMAL(10,2) | | 粘合剂用量 |
| moisture_after | DECIMAL(5,2) | | 干燥后水分(%) |
| output_weight | DECIMAL(10,2) | | 出料重量(kg) |
| operator_id | INTEGER | FK→employee(id) | |
| remark | VARCHAR(200) | | |

#### batch_cip_record (CIP清洗记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID(可为空，系统清洗) |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| cip_type | VARCHAR(20) | NOT NULL | 清洗类型: pre(预清洗)/alkali(碱洗)/acid(酸洗)/rinse(水洗)/final(最终冲洗) |
| start_time | DATETIME | NOT NULL | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| tank_temp | DECIMAL(6,2) | | 清洗罐温度(℃) |
| return_temp | DECIMAL(6,2) | | 回流温度(℃) |
| flow_rate | DECIMAL(8,2) | | 流速(m³/h) |
| pressure | DECIMAL(6,3) | | 压力(MPa) |
| alkali_conc | DECIMAL(6,2) | | 碱浓度(%) |
| acid_conc | DECIMAL(6,2) | | 酸浓度(%) |
| rinse_volume | DECIMAL(10,2) | | 冲洗水量(L) |
| conductivity | DECIMAL(8,2) | | 电导率(μS/cm) |
| ph_return | DECIMAL(4,2) | | 回流pH |
| is_pass | BOOLEAN | DEFAULT 0 | 是否合格 |
| operator_id | INTEGER | FK→employee(id) | |
| remark | VARCHAR(200) | | |

#### batch_sterilize_record (灭菌记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID(可为空) |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| sterilize_type | VARCHAR(20) | NOT NULL | 灭菌类型: empty(空消)/medium(实消)/continuous(连消)/pipeline(管道) |
| start_time | DATETIME | NOT NULL | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| sterilize_temp | DECIMAL(6,2) | | 灭菌温度(℃) |
| sterilize_pressure | DECIMAL(6,3) | | 灭菌压力(MPa) |
| hold_time_min | INTEGER | | 保温时间(min) |
| is_pass | BOOLEAN | DEFAULT 0 | |
| operator_id | INTEGER | FK→employee(id) | |
| remark | VARCHAR(200) | | |

#### batch_intermediate (中间品/半成品记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| material_id | INTEGER | FK→material(id) | 中间品物料ID |
| material_batch_no | VARCHAR(50) | | 中间品批号 |
| production_step | VARCHAR(30) | NOT NULL | 生产步骤: after_ferment(发酵液)/after_extract(提取液)/after_dry(干燥粉)/after_mix(混合粉) |
| quantity | DECIMAL(12,3) | NOT NULL | 数量 |
| unit | VARCHAR(10) | NOT NULL | 单位 |
| test_result | VARCHAR(20) | | 检测结果: pending/pass/fail |
| potency_value | DECIMAL(12,2) | | 效价/酶活(U/g) |
| storage_location | VARCHAR(50) | | 存放位置 |
| storage_temp | DECIMAL(5,2) | | 存放温度(℃) |
| hold_start_time | DATETIME | | 暂存开始时间 |
| hold_end_time | DATETIME | | 暂存结束时间(超期预警) |
| operator_id | INTEGER | FK→employee(id) | |
| remark | VARCHAR(200) | | |

#### batch_operation_log (批次操作日志)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| operation_time | DATETIME | DEFAULT CURRENT_TIMESTAMP | 操作时间 |
| operator_id | INTEGER | FK→employee(id) | 操作人 |
| action_type | VARCHAR(30) | NOT NULL | 操作类型: status_change/feeding/param_change/sampling/qc/remark |
| action_detail | TEXT | | 操作详情 |
| old_value | VARCHAR(100) | | 旧值 |
| new_value | VARCHAR(100) | | 新值 |

#### batch_tank_assignment (发酵罐分配)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| assignment_type | VARCHAR(20) | DEFAULT 'primary' | 分配类型: primary(主罐)/secondary(二级)/seed(种子罐) |
| start_time | DATETIME | | 占用开始时间 |
| end_time | DATETIME | | 占用结束时间 |
| status | VARCHAR(20) | DEFAULT 'active' | 状态: active/completed |

#### sampling_record (取样记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| sample_no | VARCHAR(30) | NOT NULL UNIQUE | 样品编号 |
| sample_type | VARCHAR(20) | NOT NULL | 样品类型: raw_material(原料)/intermediate(中间品)/finished(成品)/environmental(环境)/water(水) |
| sample_point | VARCHAR(50) | | 取样点 |
| sample_time | DATETIME | NOT NULL | 取样时间 |
| sample_qty | DECIMAL(8,2) | | 取样量 |
| sample_person | INTEGER | FK→employee(id) | 取样人 |
| sample_purpose | VARCHAR(100) | | 取样目的 |
| test_status | VARCHAR(20) | DEFAULT 'pending' | 检测状态: pending/in_progress/completed |

#### batch_label (批次标签/标识)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| label_type | VARCHAR(20) | NOT NULL | 标签类型: status_tag(状态牌)/qc_tag(质检签)/material_tag(物料签) |
| label_content | VARCHAR(200) | | 标签内容 |
| print_time | DATETIME | | 打印时间 |
| printed_by | INTEGER | FK→employee(id) | 打印人 |

#### batch_energy_consumption (批次能耗记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| energy_type | VARCHAR(20) | NOT NULL | 能耗类型: electricity(电)/steam(蒸汽)/water(水)/compressed_air(压缩空气) |
| meter_no | VARCHAR(30) | | 仪表编号 |
| start_reading | DECIMAL(12,2) | | 起始读数 |
| end_reading | DECIMAL(12,2) | | 结束读数 |
| consumption | DECIMAL(12,2) | | 消耗量 |
| unit | VARCHAR(10) | | 单位: kWh/t/m³ |

## 4. 质量管理 (Quality Management) — 17表

#### qc_standard (检验标准)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| standard_code | VARCHAR(30) | NOT NULL UNIQUE | 标准编号 |
| standard_name | VARCHAR(100) | NOT NULL | 标准名称 |
| standard_type | VARCHAR(20) | NOT NULL | 类型: raw_material(原料)/intermediate(中间品)/finished(成品)/water(水)/environmental(环境) |
| material_id | INTEGER | FK→material(id) | 适用物料 |
| product_id | INTEGER | FK→product(id) | 适用产品 |
| version | VARCHAR(10) | NOT NULL | 版本号 |
| is_active | BOOLEAN | DEFAULT 1 |
| effective_date | DATE | |
| expire_date | DATE | |

#### qc_standard_item (检验标准项目)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| standard_id | INTEGER | FK→qc_standard(id) | 检验标准ID |
| item_code | VARCHAR(20) | NOT NULL | 项目代码 |
| item_name | VARCHAR(100) | NOT NULL | 项目名称: appearance(外观)/moisture(水分)/ash(灰分)/protein(蛋白)/potency(效价)/ph/purity(纯度)/heavy_metal(重金属)/microbe(微生物)/particle_size(粒度) |
| test_method | VARCHAR(100) | | 检测方法 |
| standard_value | VARCHAR(100) | | 标准值(文本) |
| standard_min | DECIMAL(12,4) | | 下限 |
| standard_max | DECIMAL(12,4) | | 上限 |
| unit | VARCHAR(20) | | 单位 |
| data_type | VARCHAR(20) | DEFAULT 'numeric' | 数据类型: numeric/text/boolean/option |
| options | VARCHAR(200) | | 选项值(逗号分隔) |
| sort_order | INTEGER | DEFAULT 0 |

#### qc_test_record (检验记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| test_no | VARCHAR(30) | NOT NULL UNIQUE | 检验编号 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| sample_id | INTEGER | FK→sampling_record(id) | 样品ID |
| standard_id | INTEGER | FK→qc_standard(id) | 检验标准ID |
| test_type | VARCHAR(20) | NOT NULL | 检验类型: incoming(来料)/inprocess(过程)/finished(成品)/stability(稳定性)/environmental(环境) |
| test_time | DATETIME | NOT NULL | 检验时间 |
| tester_id | INTEGER | FK→employee(id) | 检验员 |
| reviewer_id | INTEGER | FK→employee(id) | 复核人 |
| overall_result | VARCHAR(20) | DEFAULT 'pending' | 结论: pending/pass/fail |
| test_notes | TEXT | | 检验备注 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### qc_test_detail (检验记录明细)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| test_record_id | INTEGER | FK→qc_test_record(id) | 检验记录ID |
| item_id | INTEGER | FK→qc_standard_item(id) | 检验项目ID |
| test_value | VARCHAR(100) | | 检测值 |
| numeric_value | DECIMAL(12,4) | | 数值结果 |
| is_pass | BOOLEAN | | 是否合格 |
| remark | VARCHAR(200) | | |

#### nonconformance (不合格品处理)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| nc_no | VARCHAR(30) | NOT NULL UNIQUE | 不合格编号 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| test_record_id | INTEGER | FK→qc_test_record(id) | 检验记录ID |
| material_id | INTEGER | FK→material(id) | 物料ID |
| nc_type | VARCHAR(20) | NOT NULL | 类型: raw_material(原料)/intermediate(中间品)/finished(成品)/packaging(包材) |
| nc_level | VARCHAR(10) | NOT NULL | 等级: minor(轻微)/major(主要)/critical(严重) |
| nc_description | TEXT | NOT NULL | 不合格描述 |
| discover_time | DATETIME | NOT NULL | 发现时间 |
| discoverer_id | INTEGER | FK→employee(id) | 发现人 |
| disposition | VARCHAR(30) | | 处理方式: rework(返工)/scrap(报废)/downgrade(降级)/return(退货)/use_as_is(让步接收) |
| disposition_detail | TEXT | | 处理详情 |
| disposition_by | INTEGER | FK→employee(id) | 处理人 |
| disposition_time | DATETIME | | 处理时间 |
| status | VARCHAR(20) | DEFAULT 'open' | 状态: open/in_process/closed |
| is_closed | BOOLEAN | DEFAULT 0 |

#### deviation (偏差管理)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| deviation_no | VARCHAR(30) | NOT NULL UNIQUE | 偏差编号 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| deviation_type | VARCHAR(30) | NOT NULL | 偏差类型: process(工艺)/equipment(设备)/material(物料)/operation(操作)/environment(环境)/utility(公用工程) |
| deviation_level | VARCHAR(10) | NOT NULL | 等级: minor/major/critical |
| description | TEXT | NOT NULL | 偏差描述 |
| discover_time | DATETIME | | 发现时间 |
| reporter_id | INTEGER | FK→employee(id) | 报告人 |
| impact_analysis | TEXT | | 影响分析 |
| root_cause | TEXT | | 根本原因 |
| corrective_action | TEXT | | 纠正措施 |
| preventive_action | TEXT | | 预防措施 |
| reviewer_id | INTEGER | FK→employee(id) | 审核人 |
| review_time | DATETIME | | 审核时间 |
| approver_id | INTEGER | FK→employee(id) | 批准人 |
| approve_time | DATETIME | | 批准时间 |
| status | VARCHAR(20) | DEFAULT 'open' | 状态: open/investigating/action/corrected/closed |
| is_closed | BOOLEAN | DEFAULT 0 |

#### change_management (变更管理)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| change_no | VARCHAR(30) | NOT NULL UNIQUE | 变更编号 |
| change_type | VARCHAR(30) | NOT NULL | 变更类型: process(工艺)/equipment(设备)/material(物料)/method(方法)/facility(设施)/software(软件) |
| title | VARCHAR(200) | NOT NULL | 变更标题 |
| description | TEXT | | 变更描述 |
| reason | TEXT | | 变更原因 |
| risk_assessment | TEXT | | 风险评估 |
| proposed_by | INTEGER | FK→employee(id) | 提出人 |
| proposed_time | DATETIME | | 提出时间 |
| reviewer_id | INTEGER | FK→employee(id) | 审核人 |
| approver_id | INTEGER | FK→employee(id) | 批准人 |
| effective_date | DATE | | 生效日期 |
| status | VARCHAR(20) | DEFAULT 'draft' | 状态: draft/pending/reviewed/approved/rejected/implemented/closed |

#### stability_study (稳定性考察)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| study_no | VARCHAR(30) | NOT NULL UNIQUE | 考察编号 |
| batch_id | INTEGER | FK→batch_record(id) | 批次ID |
| product_id | INTEGER | FK→product(id) | 产品ID |
| study_type | VARCHAR(20) | NOT NULL | 类型: long_term(长期)/accelerated(加速)/photo(光照) |
| condition_temp | VARCHAR(20) | | 温度条件: 25℃/40℃ |
| condition_humidity | VARCHAR(20) | | 湿度条件: 60%RH/75%RH |
| start_date | DATE | NOT NULL | 开始日期 |
| planned_duration_months | INTEGER | | 计划周期(月) |
| status | VARCHAR(20) | DEFAULT 'active' | 状态: active/completed/terminated |

#### stability_test_point (稳定性检测时间点)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| stability_id | INTEGER | FK→stability_study(id) | 考察ID |
| month_point | INTEGER | NOT NULL | 时间点(月): 0/1/3/6/9/12/18/24/36 |
| planned_test_date | DATE | | 计划检测日期 |
| actual_test_date | DATE | | 实际检测日期 |
| test_record_id | INTEGER | FK→qc_test_record(id) | 检验记录ID |
| status | VARCHAR(20) | DEFAULT 'pending' | 状态: pending/completed/skipped |

#### supplier_audit (供应商审计)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| supplier_id | INTEGER | FK→supplier(id) | 供应商ID |
| audit_date | DATE | NOT NULL | 审计日期 |
| audit_type | VARCHAR(20) | | 审计类型: initial(初审)/regular(定期)/follow_up(跟踪) |
| auditor_id | INTEGER | FK→employee(id) | 审计人 |
| score | DECIMAL(5,2) | | 评分 |
| result | VARCHAR(20) | | 结果: pass/conditional_pass/fail |
| conclusion | TEXT | | 审计结论 |
| next_audit_date | DATE | | 下次审计日期 |

## 5. 设备管理 (Equipment Management) — 15表

#### equipment_maintain_plan (保养计划)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| plan_code | VARCHAR(30) | NOT NULL | 计划编码 |
| maintain_type | VARCHAR(20) | NOT NULL | 保养类型: daily(日常)/weekly(周保)/monthly(月保)/quarterly(季保)/yearly(年保) |
| maintain_cycle_days | INTEGER | | 周期(天) |
| cycle_type | VARCHAR(10) | DEFAULT 'interval' | 周期类型: interval(间隔)/fixed(固定日期) |
| last_maintain_date | DATE | | 上次保养日期 |
| next_maintain_date | DATE | | 下次保养日期 |
| is_active | BOOLEAN | DEFAULT 1 |
| responsible_person | INTEGER | FK→employee(id) | 负责人 |

#### maintain_plan_item (保养计划项目)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| plan_id | INTEGER | FK→equipment_maintain_plan(id) | 保养计划ID |
| item_content | VARCHAR(200) | NOT NULL | 保养内容 |
| standard | VARCHAR(200) | | 保养标准 |
| sort_order | INTEGER | DEFAULT 0 |

#### maintain_record (保养/维修记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| record_type | VARCHAR(20) | NOT NULL | 类型: maintain(保养)/repair(维修)/inspect(点检) |
| plan_id | INTEGER | FK→equipment_maintain_plan(id) | 关联计划ID |
| record_no | VARCHAR(30) | NOT NULL UNIQUE | 记录编号 |
| description | TEXT | | 工作描述 |
| start_time | DATETIME | NOT NULL | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| operator_id | INTEGER | FK→employee(id) | 操作人 |
| supervisor_id | INTEGER | FK→employee(id) | 监督人 |
| result | VARCHAR(20) | | 结果: completed(完成)/pending(待处理)/partial(部分完成) |
| downtime_hours | DECIMAL(6,2) | | 停机时长(小时) |
| cost_estimate | DECIMAL(10,2) | | 费用预估 |
| remark | TEXT | | 备注 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### maintain_record_detail (维修保养明细)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| record_id | INTEGER | FK→maintain_record(id) | 记录ID |
| item_content | VARCHAR(200) | | 项目内容 |
| result_status | VARCHAR(10) | | 结果: ok/ng/na |
| actual_value | VARCHAR(100) | | 实际值 |
| remark | VARCHAR(200) | | |

#### spare_part (备件管理)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| part_no | VARCHAR(30) | NOT NULL UNIQUE | 备件编码 |
| part_name | VARCHAR(100) | NOT NULL | 备件名称 |
| spec | VARCHAR(100) | | 规格 |
| unit | VARCHAR(10) | | 单位 |
| location | VARCHAR(50) | | 存放位置 |
| min_stock | INTEGER | DEFAULT 0 | 最低库存 |
| max_stock | INTEGER | DEFAULT 0 | 最高库存 |
| current_stock | INTEGER | DEFAULT 0 | 当前库存 |
| is_active | BOOLEAN | DEFAULT 1 |

#### spare_part_usage (备件使用记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| part_id | INTEGER | FK→spare_part(id) | 备件ID |
| maintain_record_id | INTEGER | FK→maintain_record(id) | 维修记录ID |
| quantity | INTEGER | NOT NULL | 数量 |
| used_by | INTEGER | FK→employee(id) | 领用人 |
| used_time | DATETIME | DEFAULT CURRENT_TIMESTAMP | 领用时间 |

#### equipment_calibration (校准管理)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID(仪表类) |
| calibration_cycle_days | INTEGER | | 校准周期(天) |
| last_calibration_date | DATE | | 上次校准日期 |
| next_calibration_date | DATE | | 下次校准日期 |
| calibration_standard | VARCHAR(100) | | 校准标准 |
| calibration_method | VARCHAR(200) | | 校准方法 |

#### calibration_record (校准记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| calibration_date | DATE | NOT NULL | 校准日期 |
| calibrator | VARCHAR(50) | | 校准人 |
| calibration_org | VARCHAR(100) | | 校准机构 |
| result | VARCHAR(20) | | 结果: pass/fail |
| before_value | VARCHAR(50) | | 校准前值 |
| after_value | VARCHAR(50) | | 校准后值 |
| cert_no | VARCHAR(50) | | 证书编号 |
| cert_expire_date | DATE | | 证书有效期 |
| remark | VARCHAR(200) | | |

#### equipment_runtime (设备运行记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| start_time | DATETIME | NOT NULL | 启动时间 |
| end_time | DATETIME | | 停止时间 |
| total_minutes | INTEGER | | 运行时长(分钟) |
| operator_id | INTEGER | FK→employee(id) | 操作人 |
| batch_id | INTEGER | FK→batch_record(id) | 关联批次 |
| remark | VARCHAR(200) | | |

#### equipment_fault (设备故障记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| fault_time | DATETIME | NOT NULL | 故障时间 |
| fault_desc | TEXT | NOT NULL | 故障描述 |
| fault_type | VARCHAR(30) | | 故障类型: mechanical(机械)/electrical(电气)/instrument(仪表)/leakage(泄漏)/other |
| severity | VARCHAR(10) | | 严重程度: low/mid/high/critical |
| report_by | INTEGER | FK→employee(id) | 报告人 |
| repair_record_id | INTEGER | FK→maintain_record(id) | 维修记录ID |
| downtime_minutes | INTEGER | | 停机时间(分钟) |
| status | VARCHAR(20) | DEFAULT 'reported' | 状态: reported/repairing/resolved/closed |

#### equipment_daily_check (设备点检记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| equipment_id | INTEGER | FK→equipment(id) | 设备ID |
| check_date | DATE | NOT NULL | 点检日期 |
| check_time | TIME | | 点检时间 |
| check_person | INTEGER | FK→employee(id) | 点检人 |
| check_items | TEXT | | 点检项目(JSON) |
| overall_result | VARCHAR(10) | | 总结果: ok/ng |
| remark | VARCHAR(200) | | |

## 6. 仓储物流 (Warehouse & Logistics) — 10表

#### warehouse (仓库)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| warehouse_code | VARCHAR(20) | NOT NULL UNIQUE | 仓库编码 |
| name | VARCHAR(100) | NOT NULL | 仓库名称 |
| warehouse_type | VARCHAR(20) | NOT NULL | 类型: raw_material(原料库)/packaging(包材库)/semi(中间品库)/finished(成品库)/consumable(耗材库)/cold(冷库)/quarantine(待检库)/rejected(不合格库) |
| location | VARCHAR(200) | | 位置 |
| temp_min | DECIMAL(5,2) | | 最低温度(℃) |
| temp_max | DECIMAL(5,2) | | 最高温度(℃) |
| humidity_min | DECIMAL(5,2) | | 最低湿度(%) |
| humidity_max | DECIMAL(5,2) | | 最高湿度(%) |
| is_active | BOOLEAN | DEFAULT 1 |

#### storage_location (库位)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| warehouse_id | INTEGER | FK→warehouse(id) | 仓库ID |
| location_code | VARCHAR(30) | NOT NULL | 库位编码: A-01-01 |
| area | VARCHAR(20) | | 区域 |
| shelf | VARCHAR(20) | | 货架 |
| layer | VARCHAR(10) | | 层 |
| max_capacity | DECIMAL(12,3) | | 最大容量 |
| capacity_unit | VARCHAR(10) | | 容量单位 |
| is_active | BOOLEAN | DEFAULT 1 |
| UNIQUE(warehouse_id, location_code) | | |

#### inventory (库存台账)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| material_id | INTEGER | FK→material(id) | 物料ID |
| warehouse_id | INTEGER | FK→warehouse(id) | 仓库ID |
| location_id | INTEGER | FK→storage_location(id) | 库位ID |
| batch_no | VARCHAR(50) | | 物料批号 |
| quantity | DECIMAL(12,3) | NOT NULL DEFAULT 0 | 当前库存量 |
| unit | VARCHAR(10) | NOT NULL | 单位 |
| frozen_qty | DECIMAL(12,3) | DEFAULT 0 | 冻结数量 |
| available_qty | DECIMAL(12,3) | | 可用数量(计算字段) |
| production_date | DATE | | 生产日期 |
| expire_date | DATE | | 失效日期 |
| status | VARCHAR(20) | DEFAULT 'normal' | 状态: normal(正常)/quarantine(待检)/frozen(冻结)/rejected(不合格) |
| last_update_time | DATETIME | DEFAULT CURRENT_TIMESTAMP | 最后更新时间 |
| UNIQUE(material_id, warehouse_id, location_id, batch_no) | | |

#### inventory_transaction (出入库记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| trans_no | VARCHAR(30) | NOT NULL UNIQUE | 事务编号 |
| trans_type | VARCHAR(20) | NOT NULL | 事务类型: purchase_in(采购入库)/production_in(生产入库)/return_in(退料入库)/issue_out(领料出库)/sale_out(销售出库)/scrap_out(报废出库)/transfer(移库)/adjust(调整) |
| material_id | INTEGER | FK→material(id) | 物料ID |
| batch_no | VARCHAR(50) | | 批号 |
| quantity | DECIMAL(12,3) | NOT NULL | 数量 |
| unit | VARCHAR(10) | NOT NULL | 单位 |
| unit_price | DECIMAL(10,4) | | 单价 |
| total_price | DECIMAL(14,2) | | 总金额 |
| from_warehouse_id | INTEGER | FK→warehouse(id) | 源仓库 |
| from_location_id | INTEGER | FK→storage_location(id) | 源库位 |
| to_warehouse_id | INTEGER | FK→warehouse(id) | 目标仓库 |
| to_location_id | INTEGER | FK→storage_location(id) | 目标库位 |
| reference_no | VARCHAR(30) | | 关联单据号(工单/采购单/销售单) |
| operator_id | INTEGER | FK→employee(id) | 操作人 |
| trans_time | DATETIME | DEFAULT CURRENT_TIMESTAMP | 事务时间 |
| remark | VARCHAR(200) | | 备注 |

#### inventory_check (盘点记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| check_no | VARCHAR(30) | NOT NULL UNIQUE | 盘点编号 |
| warehouse_id | INTEGER | FK→warehouse(id) | 仓库ID |
| check_type | VARCHAR(20) | NOT NULL | 类型: full(全盘)/cycle(循环)/daily(每日) |
| check_date | DATE | NOT NULL | 盘点日期 |
| status | VARCHAR(20) | DEFAULT 'draft' | 状态: draft(草稿)/in_progress(进行中)/completed(完成)/approved(已审核) |
| checker_id | INTEGER | FK→employee(id) | 盘点人 |
| reviewer_id | INTEGER | FK→employee(id) | 审核人 |
| remark | VARCHAR(200) | | |

#### inventory_check_detail (盘点明细)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| check_id | INTEGER | FK→inventory_check(id) | 盘点ID |
| material_id | INTEGER | FK→material(id) | 物料ID |
| location_id | INTEGER | FK→storage_location(id) | 库位ID |
| batch_no | VARCHAR(50) | | 批号 |
| book_qty | DECIMAL(12,3) | NOT NULL | 账面数量 |
| actual_qty | DECIMAL(12,3) | NOT NULL | 实际数量 |
| diff_qty | DECIMAL(12,3) | | 差异数量 |
| unit | VARCHAR(10) | | 单位 |
| remark | VARCHAR(200) | | |

#### inventory_reservation (库存预留)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| material_id | INTEGER | FK→material(id) | 物料ID |
| batch_no | VARCHAR(50) | | 批号 |
| quantity | DECIMAL(12,3) | NOT NULL | 预留数量 |
| unit | VARCHAR(10) | | 单位 |
| reference_type | VARCHAR(20) | NOT NULL | 关联类型: work_order/sales_order |
| reference_id | INTEGER | | 关联ID |
| reference_no | VARCHAR(30) | | 关联编号 |
| reserved_by | INTEGER | FK→employee(id) | 预留人 |
| reserved_time | DATETIME | DEFAULT CURRENT_TIMESTAMP |
| status | VARCHAR(20) | DEFAULT 'active' | 状态: active/consumed/released |

## 7. 公用工程 (Utility Engineering) — 5表

#### utility_system (公用工程系统)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| system_code | VARCHAR(20) | NOT NULL UNIQUE | 系统编码 |
| system_name | VARCHAR(100) | NOT NULL | 系统名称 |
| system_type | VARCHAR(20) | NOT NULL | 类型: purified_water(纯化水)/steam(蒸汽)/compressed_air(压缩空气)/wastewater(污水处理)/chilled_water(冷冻水)/cooling(循环冷却)/electricity(配电) |
| location | VARCHAR(100) | | 位置 |
| capacity | VARCHAR(50) | | 设计能力 |
| is_active | BOOLEAN | DEFAULT 1 |

#### purified_water_record (纯化水系统记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| record_time | DATETIME | NOT NULL | 记录时间 |
| conductivity | DECIMAL(8,3) | | 电导率(μS/cm) |
| ph_value | DECIMAL(4,2) | | pH值 |
| flow_rate | DECIMAL(8,2) | | 产水流量(m³/h) |
| total_flow | DECIMAL(12,2) | | 累计产水量(m³) |
| tank_level | DECIMAL(6,2) | | 纯水箱液位(%) |
| inlet_pressure | DECIMAL(6,3) | | 进水压力(MPa) |
| outlet_pressure | DECIMAL(6,3) | | 出水压力(MPa) |
| temperature | DECIMAL(5,2) | | 温度(℃) |
| operator_id | INTEGER | FK→employee(id) | 操作人 |
| remark | VARCHAR(200) | | |

#### steam_system_record (蒸汽系统记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| record_time | DATETIME | NOT NULL | 记录时间 |
| boiler_no | VARCHAR(30) | | 锅炉编号 |
| steam_pressure | DECIMAL(6,3) | | 蒸汽压力(MPa) |
| steam_temp | DECIMAL(6,2) | | 蒸汽温度(℃) |
| flow_rate | DECIMAL(10,2) | | 流量(t/h) |
| total_flow | DECIMAL(12,2) | | 累计流量(t) |
| fuel_consumption | DECIMAL(10,2) | | 燃料消耗 |
| feed_water_temp | DECIMAL(5,2) | | 给水温度(℃) |
| operator_id | INTEGER | FK→employee(id) | |

#### compressed_air_record (压缩空气记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| record_time | DATETIME | NOT NULL | 记录时间 |
| compressor_no | VARCHAR(30) | | 空压机编号 |
| discharge_pressure | DECIMAL(6,3) | | 排气压力(MPa) |
| discharge_temp | DECIMAL(6,2) | | 排气温度(℃) |
| flow_rate | DECIMAL(10,2) | | 流量(m³/min) |
| dew_point | DECIMAL(6,2) | | 露点温度(℃) |
| oil_level | DECIMAL(6,2) | | 油位 |
| current_a | DECIMAL(6,2) | | 电流(A) |
| run_status | VARCHAR(10) | | 运行状态: running/stopped |
| operator_id | INTEGER | FK→employee(id) | |

#### wastewater_record (污水处理记录)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| record_time | DATETIME | NOT NULL | 记录时间 |
| inflow_volume | DECIMAL(10,2) | | 进水流量(m³/h) |
| outflow_volume | DECIMAL(10,2) | | 出水流量(m³/h) |
| inflow_ph | DECIMAL(4,2) | | 进水pH |
| outflow_ph | DECIMAL(4,2) | | 出水pH |
| inflow_cod | DECIMAL(8,2) | | 进水COD(mg/L) |
| outflow_cod | DECIMAL(8,2) | | 出水COD(mg/L) |
| inflow_ammonia | DECIMAL(8,2) | | 进水氨氮(mg/L) |
| outflow_ammonia | DECIMAL(8,2) | | 出水氨氮(mg/L) |
| inflow_ss | DECIMAL(8,2) | | 进水悬浮物(mg/L) |
| outflow_ss | DECIMAL(8,2) | | 出水悬浮物(mg/L) |
| do_level | DECIMAL(5,2) | | 曝气池溶氧(mg/L) |
| mlss | DECIMAL(6,2) | | MLSS(g/L) |
| operator_id | INTEGER | FK→employee(id) | |
| remark | VARCHAR(200) | | |

---

## 表数量统计

| 模块 | 表数量 | 说明 |
|------|--------|------|
| 1. 基础数据 | 22 | 组织架构4 + 人员5 + 物料6 + 设备7 |
| 2. 工艺管理 | 16 | 产品/BOM4 + 工艺路线2 + 参数1 + 批号2 + 配方3 + SOP1 + 其他3 |
| 3. 生产过程 | 28 | 工单2 + 批次核心13 + 取样/标签/能耗/日志/分配15 |
| 4. 质量管理 | 17 | 标准2 + 检验3 + 不合格/偏差/变更/稳定性/供应商审计12 |
| 5. 设备管理 | 15 | 保养5 + 维修2 + 备件2 + 校准2 + 运行/故障/点检4 |
| 6. 仓储物流 | 10 | 仓库2 + 库存3 + 出入库1 + 盘点2 + 预留1 + 调整1 |
| 7. 公用工程 | 5 | 系统1 + 纯化水1 + 蒸汽1 + 压缩空气1 + 污水1 |
| **合计** | **113** | |

---

*设计日期: 2026-04-27*
*适用企业: 内蒙古科为博生物科技有限公司 (CRVAB)*
