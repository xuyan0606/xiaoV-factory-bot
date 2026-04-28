#!/usr/bin/env python3
"""
科为博生物科技 MES 数据库核心表 DDL
SQLite 实现 - 适用于内蒙古科为博生物科技有限公司

包含114个表的完整Schema定义
"""
import sqlite3
import os

SCHEMA_VERSION = "1.0"
DB_PATH = os.path.join(os.path.dirname(__file__), "mes_core.db")


# ========== 1. 基础数据 - 组织架构 ==========

CREATE_ORG_COMPANY = """
CREATE TABLE IF NOT EXISTS org_company (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(200),
    tel VARCHAR(20),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ORG_DEPARTMENT = """
CREATE TABLE IF NOT EXISTS org_department (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    dept_type VARCHAR(20) NOT NULL,
    parent_id INTEGER REFERENCES org_department(id),
    manager_id INTEGER REFERENCES employee(id),
    company_id INTEGER REFERENCES org_company(id),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_ORG_WORK_CENTER = """
CREATE TABLE IF NOT EXISTS org_work_center (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    work_center_type VARCHAR(20) NOT NULL,
    department_id INTEGER REFERENCES org_department(id),
    leader_id INTEGER REFERENCES employee(id),
    is_active BOOLEAN DEFAULT 1
);
"""

# ========== 1. 基础数据 - 人员 ==========

CREATE_EMPLOYEE = """
CREATE TABLE IF NOT EXISTS employee (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_no VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL,
    gender VARCHAR(4),
    birth_date DATE,
    id_card VARCHAR(18),
    phone VARCHAR(20),
    email VARCHAR(100),
    hire_date DATE,
    department_id INTEGER REFERENCES org_department(id),
    work_center_id INTEGER REFERENCES org_work_center(id),
    position VARCHAR(50),
    job_title VARCHAR(50),
    education VARCHAR(20),
    major VARCHAR(50),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_EMPLOYEE_CERTIFICATION = """
CREATE TABLE IF NOT EXISTS employee_certification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employee(id),
    cert_type VARCHAR(30) NOT NULL,
    cert_name VARCHAR(100) NOT NULL,
    cert_no VARCHAR(50),
    issue_date DATE,
    expire_date DATE,
    issuing_authority VARCHAR(100),
    is_active BOOLEAN DEFAULT 1,
    remark VARCHAR(200)
);
"""

CREATE_EMPLOYEE_TRAINING = """
CREATE TABLE IF NOT EXISTS employee_training (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employee(id),
    training_type VARCHAR(30) NOT NULL,
    training_name VARCHAR(100) NOT NULL,
    trainer VARCHAR(50),
    training_date DATE NOT NULL,
    duration_hours DECIMAL(5,1),
    result VARCHAR(20),
    score DECIMAL(5,2),
    remark VARCHAR(200)
);
"""

CREATE_EMPLOYEE_SHIFT = """
CREATE TABLE IF NOT EXISTS employee_shift (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employee(id),
    shift_date DATE NOT NULL,
    shift_type VARCHAR(10) NOT NULL,
    work_center_id INTEGER REFERENCES org_work_center(id),
    is_active BOOLEAN DEFAULT 1
);
"""

# ========== 1. 基础数据 - 物料 ==========

CREATE_MATERIAL_CATEGORY = """
CREATE TABLE IF NOT EXISTS material_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES material_category(id),
    level INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0
);
"""

CREATE_MATERIAL = """
CREATE TABLE IF NOT EXISTS material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code VARCHAR(30) NOT NULL UNIQUE,
    old_code VARCHAR(30),
    name VARCHAR(100) NOT NULL,
    english_name VARCHAR(100),
    category_id INTEGER REFERENCES material_category(id),
    material_type VARCHAR(20) NOT NULL,
    spec VARCHAR(100),
    unit VARCHAR(10) NOT NULL,
    unit_weight DECIMAL(10,3),
    density DECIMAL(10,4),
    cas_no VARCHAR(20),
    storage_condition VARCHAR(200),
    shelf_life_days INTEGER,
    is_active BOOLEAN DEFAULT 1,
    is_controlled BOOLEAN DEFAULT 0,
    min_stock_qty DECIMAL(12,3),
    max_stock_qty DECIMAL(12,3),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SUPPLIER = """
CREATE TABLE IF NOT EXISTS supplier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    contact_person VARCHAR(50),
    phone VARCHAR(20),
    address VARCHAR(200),
    tax_no VARCHAR(30),
    bank_info VARCHAR(200),
    supply_category VARCHAR(50),
    grade VARCHAR(10),
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_MATERIAL_SUPPLIER = """
CREATE TABLE IF NOT EXISTS material_supplier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES material(id),
    supplier_id INTEGER NOT NULL REFERENCES supplier(id),
    supplier_material_code VARCHAR(30),
    is_preferred BOOLEAN DEFAULT 0,
    approval_status VARCHAR(20) DEFAULT 'pending'
);
"""

CREATE_CUSTOMER = """
CREATE TABLE IF NOT EXISTS customer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    contact_person VARCHAR(50),
    phone VARCHAR(20),
    address VARCHAR(200),
    grade VARCHAR(10),
    is_active BOOLEAN DEFAULT 1
);
"""

# ========== 1. 基础数据 - 设备 ==========

CREATE_EQUIPMENT_CATEGORY = """
CREATE TABLE IF NOT EXISTS equipment_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES equipment_category(id)
);
"""

CREATE_EQUIPMENT = """
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equip_no VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    category_id INTEGER REFERENCES equipment_category(id),
    equip_type VARCHAR(30) NOT NULL,
    model VARCHAR(50),
    spec VARCHAR(100),
    manufacturer VARCHAR(100),
    serial_no VARCHAR(50),
    voltage VARCHAR(20),
    power_kw DECIMAL(8,2),
    capacity VARCHAR(50),
    install_date DATE,
    commission_date DATE,
    department_id INTEGER REFERENCES org_department(id),
    work_center_id INTEGER REFERENCES org_work_center(id),
    location VARCHAR(100),
    equipment_status VARCHAR(20) DEFAULT 'idle',
    run_status VARCHAR(20) DEFAULT 'stopped',
    asset_no VARCHAR(30),
    scrap_date DATE,
    is_active BOOLEAN DEFAULT 1,
    remark VARCHAR(200)
);
"""

CREATE_EQUIPMENT_PARAMETER = """
CREATE TABLE IF NOT EXISTS equipment_parameter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    param_code VARCHAR(30) NOT NULL,
    param_name VARCHAR(50) NOT NULL,
    unit VARCHAR(20),
    standard_min DECIMAL(12,4),
    standard_max DECIMAL(12,4),
    alarm_min DECIMAL(12,4),
    alarm_max DECIMAL(12,4),
    precision INTEGER DEFAULT 2
);
"""

CREATE_EQUIPMENT_DOCUMENT = """
CREATE TABLE IF NOT EXISTS equipment_document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    doc_type VARCHAR(30) NOT NULL,
    doc_name VARCHAR(100) NOT NULL,
    file_path VARCHAR(200),
    upload_date DATE
);
"""

# ========== 2. 工艺管理 ==========

CREATE_PRODUCT = """
CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code VARCHAR(30) NOT NULL UNIQUE,
    product_name VARCHAR(100) NOT NULL,
    product_type VARCHAR(20) NOT NULL,
    spec VARCHAR(100),
    unit VARCHAR(10) NOT NULL,
    yield_unit VARCHAR(10),
    shelf_life_days INTEGER,
    storage_condition VARCHAR(200),
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_PRODUCT_BOM = """
CREATE TABLE IF NOT EXISTS product_bom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES product(id),
    material_id INTEGER NOT NULL REFERENCES material(id),
    bom_version VARCHAR(20) NOT NULL,
    sequence_no INTEGER,
    quantity_per_unit DECIMAL(12,4) NOT NULL,
    unit VARCHAR(10),
    loss_rate DECIMAL(5,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    effective_date DATE,
    expire_date DATE,
    UNIQUE(product_id, material_id, bom_version)
);
"""

CREATE_ROUTE = """
CREATE TABLE IF NOT EXISTS route (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES product(id),
    route_code VARCHAR(30) NOT NULL UNIQUE,
    route_name VARCHAR(100) NOT NULL,
    route_version VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    effective_date DATE,
    expire_date DATE,
    remark VARCHAR(200)
);
"""

CREATE_ROUTE_STEP = """
CREATE TABLE IF NOT EXISTS route_step (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL REFERENCES route(id),
    step_no INTEGER NOT NULL,
    step_code VARCHAR(20),
    step_name VARCHAR(100) NOT NULL,
    step_type VARCHAR(20) NOT NULL,
    work_center_id INTEGER REFERENCES org_work_center(id),
    equipment_type VARCHAR(30),
    standard_duration_min INTEGER,
    is_hold_point BOOLEAN DEFAULT 0,
    is_critical BOOLEAN DEFAULT 0
);
"""

CREATE_PROCESS_PARAM_TEMPLATE = """
CREATE TABLE IF NOT EXISTS process_param_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_step_id INTEGER NOT NULL REFERENCES route_step(id),
    param_code VARCHAR(30) NOT NULL,
    param_name VARCHAR(50) NOT NULL,
    unit VARCHAR(20),
    standard_min DECIMAL(12,4),
    standard_max DECIMAL(12,4),
    alarm_min DECIMAL(12,4),
    alarm_max DECIMAL(12,4),
    sample_interval_sec INTEGER DEFAULT 300,
    is_required BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);
"""

CREATE_BATCH_RULE = """
CREATE TABLE IF NOT EXISTS batch_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES product(id),
    rule_name VARCHAR(50) NOT NULL,
    prefix VARCHAR(10),
    date_format VARCHAR(20),
    seq_length INTEGER DEFAULT 4,
    separator VARCHAR(5),
    sample_rule VARCHAR(50),
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_BATCH_NUMBER_SEQ = """
CREATE TABLE IF NOT EXISTS batch_number_seq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL REFERENCES batch_rule(id),
    date_key VARCHAR(10) NOT NULL,
    current_seq INTEGER DEFAULT 0,
    UNIQUE(rule_id, date_key)
);
"""

CREATE_FERMENTATION_FORMULA = """
CREATE TABLE IF NOT EXISTS fermentation_formula (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES product(id),
    formula_code VARCHAR(30) NOT NULL UNIQUE,
    formula_name VARCHAR(100) NOT NULL,
    batch_size DECIMAL(12,3),
    target_yield DECIMAL(12,3),
    formula_version VARCHAR(20),
    is_active BOOLEAN DEFAULT 1,
    effective_date DATE,
    remark VARCHAR(200)
);
"""

CREATE_FERMENTATION_FORMULA_DETAIL = """
CREATE TABLE IF NOT EXISTS fermentation_formula_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    formula_id INTEGER NOT NULL REFERENCES fermentation_formula(id),
    material_id INTEGER NOT NULL REFERENCES material(id),
    sequence_no INTEGER,
    quantity DECIMAL(12,4) NOT NULL,
    unit VARCHAR(10),
    add_method VARCHAR(30),
    add_time_point VARCHAR(50),
    remark VARCHAR(200)
);
"""

CREATE_SOP_DOCUMENT = """
CREATE TABLE IF NOT EXISTS sop_document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_code VARCHAR(30) NOT NULL UNIQUE,
    doc_name VARCHAR(100) NOT NULL,
    doc_type VARCHAR(20) NOT NULL,
    relate_type VARCHAR(20),
    relate_id INTEGER,
    version VARCHAR(10),
    content TEXT,
    is_active BOOLEAN DEFAULT 1,
    effective_date DATE,
    review_cycle_days INTEGER
);
"""

# ========== 3. 生产过程 ==========

CREATE_WORK_ORDER = """
CREATE TABLE IF NOT EXISTS work_order (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    product_id INTEGER NOT NULL REFERENCES product(id),
    planned_qty DECIMAL(12,3) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    route_id INTEGER REFERENCES route(id),
    formula_id INTEGER REFERENCES fermentation_formula(id),
    status VARCHAR(20) DEFAULT 'draft',
    priority INTEGER DEFAULT 5,
    plan_start_time DATETIME,
    plan_end_time DATETIME,
    actual_start_time DATETIME,
    actual_end_time DATETIME,
    department_id INTEGER REFERENCES org_department(id),
    created_by INTEGER REFERENCES employee(id),
    approved_by INTEGER REFERENCES employee(id),
    is_active BOOLEAN DEFAULT 1,
    remark VARCHAR(200),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_BATCH_RECORD = """
CREATE TABLE IF NOT EXISTS batch_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_no VARCHAR(50) NOT NULL UNIQUE,
    work_order_id INTEGER REFERENCES work_order(id),
    product_id INTEGER REFERENCES product(id),
    product_name VARCHAR(100),
    batch_qty DECIMAL(12,3),
    batch_unit VARCHAR(10),
    route_id INTEGER REFERENCES route(id),
    formula_id INTEGER REFERENCES fermentation_formula(id),
    equipment_id INTEGER REFERENCES equipment(id),
    status VARCHAR(20) DEFAULT 'pending',
    fermenter_no VARCHAR(30),
    strain_name VARCHAR(100),
    strain_batch VARCHAR(50),
    inoculum_volume DECIMAL(10,2),
    start_time DATETIME,
    end_time DATETIME,
    actual_yield DECIMAL(12,3),
    yield_unit VARCHAR(10),
    yield_value DECIMAL(12,2),
    operator_id INTEGER REFERENCES employee(id),
    supervisor_id INTEGER REFERENCES employee(id),
    qc_status VARCHAR(20) DEFAULT 'pending',
    is_closed BOOLEAN DEFAULT 0,
    remark VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_BATCH_FEEDING_RECORD = """
CREATE TABLE IF NOT EXISTS batch_feeding_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    material_id INTEGER NOT NULL REFERENCES material(id),
    material_code VARCHAR(30),
    material_name VARCHAR(100),
    material_batch_no VARCHAR(50),
    planned_qty DECIMAL(12,4),
    actual_qty DECIMAL(12,4) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    feed_time DATETIME NOT NULL,
    operator_id INTEGER REFERENCES employee(id),
    checker_id INTEGER REFERENCES employee(id),
    feeding_method VARCHAR(30),
    is_verified BOOLEAN DEFAULT 0,
    remark VARCHAR(200)
);
"""

CREATE_BATCH_FERMENT_PARAM = """
CREATE TABLE IF NOT EXISTS batch_ferment_param (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    record_time DATETIME NOT NULL,
    temperature DECIMAL(6,2),
    ph_value DECIMAL(4,2),
    do_value DECIMAL(5,2),
    stir_speed DECIMAL(6,1),
    tank_pressure DECIMAL(6,3),
    foam_level VARCHAR(10),
    air_flow DECIMAL(8,2),
    od_value DECIMAL(6,3),
    glucose_conc DECIMAL(6,2),
    nh3_addition DECIMAL(8,2),
    oil_addition DECIMAL(8,2),
    feed_rate DECIMAL(8,2),
    power_consumption DECIMAL(10,2),
    remark VARCHAR(200),
    UNIQUE(batch_id, record_time)
);
"""

CREATE_BATCH_EXTRACT_RECORD = """
CREATE TABLE IF NOT EXISTS batch_extract_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    step_name VARCHAR(50) NOT NULL,
    equipment_id INTEGER REFERENCES equipment(id),
    start_time DATETIME,
    end_time DATETIME,
    feed_volume DECIMAL(12,2),
    feed_temp DECIMAL(6,2),
    outlet_temp DECIMAL(6,2),
    pressure_in DECIMAL(6,3),
    pressure_out DECIMAL(6,3),
    flow_rate DECIMAL(8,2),
    ph_value DECIMAL(4,2),
    added_solvent VARCHAR(50),
    solvent_volume DECIMAL(10,2),
    output_volume DECIMAL(12,2),
    yield_pct DECIMAL(5,2),
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_BATCH_DRY_RECORD = """
CREATE TABLE IF NOT EXISTS batch_dry_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    equipment_id INTEGER REFERENCES equipment(id),
    start_time DATETIME,
    end_time DATETIME,
    inlet_temp DECIMAL(6,2),
    outlet_temp DECIMAL(6,2),
    feed_rate DECIMAL(8,2),
    atomizer_speed DECIMAL(8,2),
    air_pressure DECIMAL(6,3),
    feed_volume DECIMAL(10,2),
    feed_concentration DECIMAL(5,2),
    output_weight DECIMAL(10,2),
    moisture_pct DECIMAL(5,2),
    yield_pct DECIMAL(5,2),
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_BATCH_MIX_RECORD = """
CREATE TABLE IF NOT EXISTS batch_mix_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    step_type VARCHAR(20) NOT NULL,
    equipment_id INTEGER REFERENCES equipment(id),
    start_time DATETIME,
    end_time DATETIME,
    material_amount DECIMAL(10,2),
    mixing_time_min INTEGER,
    mixing_speed DECIMAL(8,2),
    granule_size VARCHAR(20),
    binder_name VARCHAR(50),
    binder_amount DECIMAL(10,2),
    moisture_after DECIMAL(5,2),
    output_weight DECIMAL(10,2),
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_BATCH_CIP_RECORD = """
CREATE TABLE IF NOT EXISTS batch_cip_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES batch_record(id),
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    cip_type VARCHAR(20) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    tank_temp DECIMAL(6,2),
    return_temp DECIMAL(6,2),
    flow_rate DECIMAL(8,2),
    pressure DECIMAL(6,3),
    alkali_conc DECIMAL(6,2),
    acid_conc DECIMAL(6,2),
    rinse_volume DECIMAL(10,2),
    conductivity DECIMAL(8,2),
    ph_return DECIMAL(4,2),
    is_pass BOOLEAN DEFAULT 0,
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_BATCH_STERILIZE_RECORD = """
CREATE TABLE IF NOT EXISTS batch_sterilize_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES batch_record(id),
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    sterilize_type VARCHAR(20) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    sterilize_temp DECIMAL(6,2),
    sterilize_pressure DECIMAL(6,3),
    hold_time_min INTEGER,
    is_pass BOOLEAN DEFAULT 0,
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_BATCH_INTERMEDIATE = """
CREATE TABLE IF NOT EXISTS batch_intermediate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    material_id INTEGER REFERENCES material(id),
    material_batch_no VARCHAR(50),
    production_step VARCHAR(30) NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    test_result VARCHAR(20),
    potency_value DECIMAL(12,2),
    storage_location VARCHAR(50),
    storage_temp DECIMAL(5,2),
    hold_start_time DATETIME,
    hold_end_time DATETIME,
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_BATCH_OPERATION_LOG = """
CREATE TABLE IF NOT EXISTS batch_operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    operation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    operator_id INTEGER REFERENCES employee(id),
    action_type VARCHAR(30) NOT NULL,
    action_detail TEXT,
    old_value VARCHAR(100),
    new_value VARCHAR(100)
);
"""

CREATE_BATCH_TANK_ASSIGNMENT = """
CREATE TABLE IF NOT EXISTS batch_tank_assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    assignment_type VARCHAR(20) DEFAULT 'primary',
    start_time DATETIME,
    end_time DATETIME,
    status VARCHAR(20) DEFAULT 'active'
);
"""

CREATE_SAMPLING_RECORD = """
CREATE TABLE IF NOT EXISTS sampling_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES batch_record(id),
    sample_no VARCHAR(30) NOT NULL UNIQUE,
    sample_type VARCHAR(20) NOT NULL,
    sample_point VARCHAR(50),
    sample_time DATETIME NOT NULL,
    sample_qty DECIMAL(8,2),
    sample_person INTEGER REFERENCES employee(id),
    sample_purpose VARCHAR(100),
    test_status VARCHAR(20) DEFAULT 'pending'
);
"""

CREATE_BATCH_LABEL = """
CREATE TABLE IF NOT EXISTS batch_label (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    label_type VARCHAR(20) NOT NULL,
    label_content VARCHAR(200),
    print_time DATETIME,
    printed_by INTEGER REFERENCES employee(id)
);
"""

CREATE_BATCH_ENERGY_CONSUMPTION = """
CREATE TABLE IF NOT EXISTS batch_energy_consumption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batch_record(id),
    energy_type VARCHAR(20) NOT NULL,
    meter_no VARCHAR(30),
    start_reading DECIMAL(12,2),
    end_reading DECIMAL(12,2),
    consumption DECIMAL(12,2),
    unit VARCHAR(10)
);
"""

# ========== 4. 质量管理 ==========

CREATE_QC_STANDARD = """
CREATE TABLE IF NOT EXISTS qc_standard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_code VARCHAR(30) NOT NULL UNIQUE,
    standard_name VARCHAR(100) NOT NULL,
    standard_type VARCHAR(20) NOT NULL,
    material_id INTEGER REFERENCES material(id),
    product_id INTEGER REFERENCES product(id),
    version VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    effective_date DATE,
    expire_date DATE
);
"""

CREATE_QC_STANDARD_ITEM = """
CREATE TABLE IF NOT EXISTS qc_standard_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id INTEGER NOT NULL REFERENCES qc_standard(id),
    item_code VARCHAR(20) NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    test_method VARCHAR(100),
    standard_value VARCHAR(100),
    standard_min DECIMAL(12,4),
    standard_max DECIMAL(12,4),
    unit VARCHAR(20),
    data_type VARCHAR(20) DEFAULT 'numeric',
    options VARCHAR(200),
    sort_order INTEGER DEFAULT 0
);
"""

CREATE_QC_TEST_RECORD = """
CREATE TABLE IF NOT EXISTS qc_test_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_no VARCHAR(30) NOT NULL UNIQUE,
    batch_id INTEGER REFERENCES batch_record(id),
    sample_id INTEGER REFERENCES sampling_record(id),
    standard_id INTEGER REFERENCES qc_standard(id),
    test_type VARCHAR(20) NOT NULL,
    test_time DATETIME NOT NULL,
    tester_id INTEGER REFERENCES employee(id),
    reviewer_id INTEGER REFERENCES employee(id),
    overall_result VARCHAR(20) DEFAULT 'pending',
    test_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_QC_TEST_DETAIL = """
CREATE TABLE IF NOT EXISTS qc_test_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_record_id INTEGER NOT NULL REFERENCES qc_test_record(id),
    item_id INTEGER NOT NULL REFERENCES qc_standard_item(id),
    test_value VARCHAR(100),
    numeric_value DECIMAL(12,4),
    is_pass BOOLEAN,
    remark VARCHAR(200)
);
"""

CREATE_NONCONFORMANCE = """
CREATE TABLE IF NOT EXISTS nonconformance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nc_no VARCHAR(30) NOT NULL UNIQUE,
    batch_id INTEGER REFERENCES batch_record(id),
    test_record_id INTEGER REFERENCES qc_test_record(id),
    material_id INTEGER REFERENCES material(id),
    nc_type VARCHAR(20) NOT NULL,
    nc_level VARCHAR(10) NOT NULL,
    nc_description TEXT NOT NULL,
    discover_time DATETIME NOT NULL,
    discoverer_id INTEGER REFERENCES employee(id),
    disposition VARCHAR(30),
    disposition_detail TEXT,
    disposition_by INTEGER REFERENCES employee(id),
    disposition_time DATETIME,
    status VARCHAR(20) DEFAULT 'open',
    is_closed BOOLEAN DEFAULT 0
);
"""

CREATE_DEVIATION = """
CREATE TABLE IF NOT EXISTS deviation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deviation_no VARCHAR(30) NOT NULL UNIQUE,
    batch_id INTEGER REFERENCES batch_record(id),
    deviation_type VARCHAR(30) NOT NULL,
    deviation_level VARCHAR(10) NOT NULL,
    description TEXT NOT NULL,
    discover_time DATETIME,
    reporter_id INTEGER REFERENCES employee(id),
    impact_analysis TEXT,
    root_cause TEXT,
    corrective_action TEXT,
    preventive_action TEXT,
    reviewer_id INTEGER REFERENCES employee(id),
    review_time DATETIME,
    approver_id INTEGER REFERENCES employee(id),
    approve_time DATETIME,
    status VARCHAR(20) DEFAULT 'open',
    is_closed BOOLEAN DEFAULT 0
);
"""

CREATE_CHANGE_MANAGEMENT = """
CREATE TABLE IF NOT EXISTS change_management (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_no VARCHAR(30) NOT NULL UNIQUE,
    change_type VARCHAR(30) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    reason TEXT,
    risk_assessment TEXT,
    proposed_by INTEGER REFERENCES employee(id),
    proposed_time DATETIME,
    reviewer_id INTEGER REFERENCES employee(id),
    approver_id INTEGER REFERENCES employee(id),
    effective_date DATE,
    status VARCHAR(20) DEFAULT 'draft'
);
"""

CREATE_STABILITY_STUDY = """
CREATE TABLE IF NOT EXISTS stability_study (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_no VARCHAR(30) NOT NULL UNIQUE,
    batch_id INTEGER REFERENCES batch_record(id),
    product_id INTEGER REFERENCES product(id),
    study_type VARCHAR(20) NOT NULL,
    condition_temp VARCHAR(20),
    condition_humidity VARCHAR(20),
    start_date DATE NOT NULL,
    planned_duration_months INTEGER,
    status VARCHAR(20) DEFAULT 'active'
);
"""

CREATE_STABILITY_TEST_POINT = """
CREATE TABLE IF NOT EXISTS stability_test_point (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stability_id INTEGER NOT NULL REFERENCES stability_study(id),
    month_point INTEGER NOT NULL,
    planned_test_date DATE,
    actual_test_date DATE,
    test_record_id INTEGER REFERENCES qc_test_record(id),
    status VARCHAR(20) DEFAULT 'pending'
);
"""

CREATE_SUPPLIER_AUDIT = """
CREATE TABLE IF NOT EXISTS supplier_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES supplier(id),
    audit_date DATE NOT NULL,
    audit_type VARCHAR(20),
    auditor_id INTEGER REFERENCES employee(id),
    score DECIMAL(5,2),
    result VARCHAR(20),
    conclusion TEXT,
    next_audit_date DATE
);
"""

# ========== 5. 设备管理 ==========

CREATE_EQUIPMENT_MAINTAIN_PLAN = """
CREATE TABLE IF NOT EXISTS equipment_maintain_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    plan_code VARCHAR(30) NOT NULL,
    maintain_type VARCHAR(20) NOT NULL,
    maintain_cycle_days INTEGER,
    cycle_type VARCHAR(10) DEFAULT 'interval',
    last_maintain_date DATE,
    next_maintain_date DATE,
    is_active BOOLEAN DEFAULT 1,
    responsible_person INTEGER REFERENCES employee(id)
);
"""

CREATE_MAINTAIN_PLAN_ITEM = """
CREATE TABLE IF NOT EXISTS maintain_plan_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES equipment_maintain_plan(id),
    item_content VARCHAR(200) NOT NULL,
    standard VARCHAR(200),
    sort_order INTEGER DEFAULT 0
);
"""

CREATE_MAINTAIN_RECORD = """
CREATE TABLE IF NOT EXISTS maintain_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    record_type VARCHAR(20) NOT NULL,
    plan_id INTEGER REFERENCES equipment_maintain_plan(id),
    record_no VARCHAR(30) NOT NULL UNIQUE,
    description TEXT,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    operator_id INTEGER REFERENCES employee(id),
    supervisor_id INTEGER REFERENCES employee(id),
    result VARCHAR(20),
    downtime_hours DECIMAL(6,2),
    cost_estimate DECIMAL(10,2),
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_MAINTAIN_RECORD_DETAIL = """
CREATE TABLE IF NOT EXISTS maintain_record_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES maintain_record(id),
    item_content VARCHAR(200),
    result_status VARCHAR(10),
    actual_value VARCHAR(100),
    remark VARCHAR(200)
);
"""

CREATE_SPARE_PART = """
CREATE TABLE IF NOT EXISTS spare_part (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_no VARCHAR(30) NOT NULL UNIQUE,
    part_name VARCHAR(100) NOT NULL,
    spec VARCHAR(100),
    unit VARCHAR(10),
    location VARCHAR(50),
    min_stock INTEGER DEFAULT 0,
    max_stock INTEGER DEFAULT 0,
    current_stock INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_SPARE_PART_USAGE = """
CREATE TABLE IF NOT EXISTS spare_part_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES spare_part(id),
    maintain_record_id INTEGER REFERENCES maintain_record(id),
    quantity INTEGER NOT NULL,
    used_by INTEGER REFERENCES employee(id),
    used_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_EQUIPMENT_CALIBRATION = """
CREATE TABLE IF NOT EXISTS equipment_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    calibration_cycle_days INTEGER,
    last_calibration_date DATE,
    next_calibration_date DATE,
    calibration_standard VARCHAR(100),
    calibration_method VARCHAR(200)
);
"""

CREATE_CALIBRATION_RECORD = """
CREATE TABLE IF NOT EXISTS calibration_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    calibration_date DATE NOT NULL,
    calibrator VARCHAR(50),
    calibration_org VARCHAR(100),
    result VARCHAR(20),
    before_value VARCHAR(50),
    after_value VARCHAR(50),
    cert_no VARCHAR(50),
    cert_expire_date DATE,
    remark VARCHAR(200)
);
"""

CREATE_EQUIPMENT_RUNTIME = """
CREATE TABLE IF NOT EXISTS equipment_runtime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    total_minutes INTEGER,
    operator_id INTEGER REFERENCES employee(id),
    batch_id INTEGER REFERENCES batch_record(id),
    remark VARCHAR(200)
);
"""

CREATE_EQUIPMENT_FAULT = """
CREATE TABLE IF NOT EXISTS equipment_fault (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    fault_time DATETIME NOT NULL,
    fault_desc TEXT NOT NULL,
    fault_type VARCHAR(30),
    severity VARCHAR(10),
    report_by INTEGER REFERENCES employee(id),
    repair_record_id INTEGER REFERENCES maintain_record(id),
    downtime_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'reported'
);
"""

CREATE_EQUIPMENT_DAILY_CHECK = """
CREATE TABLE IF NOT EXISTS equipment_daily_check (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    check_date DATE NOT NULL,
    check_time TIME,
    check_person INTEGER REFERENCES employee(id),
    check_items TEXT,
    overall_result VARCHAR(10),
    remark VARCHAR(200)
);
"""

# ========== 6. 仓储物流 ==========

CREATE_WAREHOUSE = """
CREATE TABLE IF NOT EXISTS warehouse (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    warehouse_type VARCHAR(20) NOT NULL,
    location VARCHAR(200),
    temp_min DECIMAL(5,2),
    temp_max DECIMAL(5,2),
    humidity_min DECIMAL(5,2),
    humidity_max DECIMAL(5,2),
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_STORAGE_LOCATION = """
CREATE TABLE IF NOT EXISTS storage_location (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL REFERENCES warehouse(id),
    location_code VARCHAR(30) NOT NULL,
    area VARCHAR(20),
    shelf VARCHAR(20),
    layer VARCHAR(10),
    max_capacity DECIMAL(12,3),
    capacity_unit VARCHAR(10),
    is_active BOOLEAN DEFAULT 1,
    UNIQUE(warehouse_id, location_code)
);
"""

CREATE_INVENTORY = """
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES material(id),
    warehouse_id INTEGER NOT NULL REFERENCES warehouse(id),
    location_id INTEGER REFERENCES storage_location(id),
    batch_no VARCHAR(50),
    quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    unit VARCHAR(10) NOT NULL,
    frozen_qty DECIMAL(12,3) DEFAULT 0,
    production_date DATE,
    expire_date DATE,
    status VARCHAR(20) DEFAULT 'normal',
    last_update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(material_id, warehouse_id, location_id, batch_no)
);
"""

CREATE_INVENTORY_TRANSACTION = """
CREATE TABLE IF NOT EXISTS inventory_transaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trans_no VARCHAR(30) NOT NULL UNIQUE,
    trans_type VARCHAR(20) NOT NULL,
    material_id INTEGER NOT NULL REFERENCES material(id),
    batch_no VARCHAR(50),
    quantity DECIMAL(12,3) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    unit_price DECIMAL(10,4),
    total_price DECIMAL(14,2),
    from_warehouse_id INTEGER REFERENCES warehouse(id),
    from_location_id INTEGER REFERENCES storage_location(id),
    to_warehouse_id INTEGER REFERENCES warehouse(id),
    to_location_id INTEGER REFERENCES storage_location(id),
    reference_no VARCHAR(30),
    operator_id INTEGER REFERENCES employee(id),
    trans_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    remark VARCHAR(200)
);
"""

CREATE_INVENTORY_CHECK = """
CREATE TABLE IF NOT EXISTS inventory_check (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_no VARCHAR(30) NOT NULL UNIQUE,
    warehouse_id INTEGER NOT NULL REFERENCES warehouse(id),
    check_type VARCHAR(20) NOT NULL,
    check_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    checker_id INTEGER REFERENCES employee(id),
    reviewer_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_INVENTORY_CHECK_DETAIL = """
CREATE TABLE IF NOT EXISTS inventory_check_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id INTEGER NOT NULL REFERENCES inventory_check(id),
    material_id INTEGER NOT NULL REFERENCES material(id),
    location_id INTEGER REFERENCES storage_location(id),
    batch_no VARCHAR(50),
    book_qty DECIMAL(12,3) NOT NULL,
    actual_qty DECIMAL(12,3) NOT NULL,
    diff_qty DECIMAL(12,3),
    unit VARCHAR(10),
    remark VARCHAR(200)
);
"""

CREATE_INVENTORY_RESERVATION = """
CREATE TABLE IF NOT EXISTS inventory_reservation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES material(id),
    batch_no VARCHAR(50),
    quantity DECIMAL(12,3) NOT NULL,
    unit VARCHAR(10),
    reference_type VARCHAR(20) NOT NULL,
    reference_id INTEGER,
    reference_no VARCHAR(30),
    reserved_by INTEGER REFERENCES employee(id),
    reserved_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active'
);
"""

# ========== 7. 公用工程 ==========

CREATE_UTILITY_SYSTEM = """
CREATE TABLE IF NOT EXISTS utility_system (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_code VARCHAR(20) NOT NULL UNIQUE,
    system_name VARCHAR(100) NOT NULL,
    system_type VARCHAR(20) NOT NULL,
    location VARCHAR(100),
    capacity VARCHAR(50),
    is_active BOOLEAN DEFAULT 1
);
"""

CREATE_PURIFIED_WATER_RECORD = """
CREATE TABLE IF NOT EXISTS purified_water_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_time DATETIME NOT NULL,
    conductivity DECIMAL(8,3),
    ph_value DECIMAL(4,2),
    flow_rate DECIMAL(8,2),
    total_flow DECIMAL(12,2),
    tank_level DECIMAL(6,2),
    inlet_pressure DECIMAL(6,3),
    outlet_pressure DECIMAL(6,3),
    temperature DECIMAL(5,2),
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

CREATE_STEAM_SYSTEM_RECORD = """
CREATE TABLE IF NOT EXISTS steam_system_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_time DATETIME NOT NULL,
    boiler_no VARCHAR(30),
    steam_pressure DECIMAL(6,3),
    steam_temp DECIMAL(6,2),
    flow_rate DECIMAL(10,2),
    total_flow DECIMAL(12,2),
    fuel_consumption DECIMAL(10,2),
    feed_water_temp DECIMAL(5,2),
    operator_id INTEGER REFERENCES employee(id)
);
"""

CREATE_COMPRESSED_AIR_RECORD = """
CREATE TABLE IF NOT EXISTS compressed_air_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_time DATETIME NOT NULL,
    compressor_no VARCHAR(30),
    discharge_pressure DECIMAL(6,3),
    discharge_temp DECIMAL(6,2),
    flow_rate DECIMAL(10,2),
    dew_point DECIMAL(6,2),
    oil_level DECIMAL(6,2),
    current_a DECIMAL(6,2),
    run_status VARCHAR(10),
    operator_id INTEGER REFERENCES employee(id)
);
"""

CREATE_WASTEWATER_RECORD = """
CREATE TABLE IF NOT EXISTS wastewater_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_time DATETIME NOT NULL,
    inflow_volume DECIMAL(10,2),
    outflow_volume DECIMAL(10,2),
    inflow_ph DECIMAL(4,2),
    outflow_ph DECIMAL(4,2),
    inflow_cod DECIMAL(8,2),
    outflow_cod DECIMAL(8,2),
    inflow_ammonia DECIMAL(8,2),
    outflow_ammonia DECIMAL(8,2),
    inflow_ss DECIMAL(8,2),
    outflow_ss DECIMAL(8,2),
    do_level DECIMAL(5,2),
    mlss DECIMAL(6,2),
    operator_id INTEGER REFERENCES employee(id),
    remark VARCHAR(200)
);
"""

# ========== 索引 ==========

CREATE_INDEXES = """
-- 生产过程索引
CREATE INDEX IF NOT EXISTS idx_batch_record_batch_no ON batch_record(batch_no);
CREATE INDEX IF NOT EXISTS idx_batch_record_status ON batch_record(status);
CREATE INDEX IF NOT EXISTS idx_batch_record_product_id ON batch_record(product_id);
CREATE INDEX IF NOT EXISTS idx_batch_record_equipment_id ON batch_record(equipment_id);
CREATE INDEX IF NOT EXISTS idx_batch_feeding_batch_id ON batch_feeding_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_ferment_param_batch_time ON batch_ferment_param(batch_id, record_time);
CREATE INDEX IF NOT EXISTS idx_batch_extract_batch_id ON batch_extract_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_dry_batch_id ON batch_dry_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_mix_batch_id ON batch_mix_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_cip_batch_id ON batch_cip_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_sterilize_batch_id ON batch_sterilize_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_intermediate_batch_id ON batch_intermediate(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_operation_log_batch_id ON batch_operation_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_work_order_status ON work_order(status);
CREATE INDEX IF NOT EXISTS idx_work_order_no ON work_order(order_no);

-- 质量索引
CREATE INDEX IF NOT EXISTS idx_qc_test_record_batch_id ON qc_test_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_qc_test_record_sample_id ON qc_test_record(sample_id);
CREATE INDEX IF NOT EXISTS idx_nonconformance_batch_id ON nonconformance(batch_id);
CREATE INDEX IF NOT EXISTS idx_deviation_batch_id ON deviation(batch_id);
CREATE INDEX IF NOT EXISTS idx_sampling_record_batch_id ON sampling_record(batch_id);

-- 设备索引
CREATE INDEX IF NOT EXISTS idx_equipment_equip_no ON equipment(equip_no);
CREATE INDEX IF NOT EXISTS idx_equipment_dept_id ON equipment(department_id);
CREATE INDEX IF NOT EXISTS idx_equipment_equip_type ON equipment(equip_type);
CREATE INDEX IF NOT EXISTS idx_maintain_record_equip_id ON maintain_record(equipment_id);
CREATE INDEX IF NOT EXISTS idx_equipment_runtime_equip_id ON equipment_runtime(equipment_id);
CREATE INDEX IF NOT EXISTS idx_equipment_fault_equip_id ON equipment_fault(equipment_id);

-- 仓储索引
CREATE INDEX IF NOT EXISTS idx_inventory_material_id ON inventory(material_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse_id ON inventory(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_inventory_batch_no ON inventory(batch_no);
CREATE INDEX IF NOT EXISTS idx_inventory_trans_material ON inventory_transaction(material_id);
CREATE INDEX IF NOT EXISTS idx_inventory_trans_time ON inventory_transaction(trans_time);

-- 公用工程索引
CREATE INDEX IF NOT EXISTS idx_purified_water_time ON purified_water_record(record_time);
CREATE INDEX IF NOT EXISTS idx_steam_system_time ON steam_system_record(record_time);
CREATE INDEX IF NOT EXISTS idx_compressed_air_time ON compressed_air_record(record_time);
CREATE INDEX IF NOT EXISTS idx_wastewater_time ON wastewater_record(record_time);
"""

# ========== 视图 ==========

CREATE_VIEWS = """
CREATE VIEW IF NOT EXISTS v_batch_summary AS
SELECT
    br.id,
    br.batch_no,
    br.product_name,
    br.batch_qty,
    br.batch_unit,
    br.fermenter_no,
    br.strain_name,
    br.status,
    br.qc_status,
    br.start_time,
    br.end_time,
    br.actual_yield,
    br.yield_value,
    br.yield_unit,
    e.name AS operator_name,
    e2.name AS supervisor_name,
    wo.order_no AS work_order_no
FROM batch_record br
LEFT JOIN employee e ON br.operator_id = e.id
LEFT JOIN employee e2 ON br.supervisor_id = e2.id
LEFT JOIN work_order wo ON br.work_order_id = wo.id;

CREATE VIEW IF NOT EXISTS v_inventory_available AS
SELECT
    i.id,
    m.material_code,
    m.name AS material_name,
    m.spec,
    i.batch_no,
    i.quantity,
    i.frozen_qty,
    (i.quantity - i.frozen_qty) AS available_qty,
    i.unit,
    w.name AS warehouse_name,
    sl.location_code,
    i.expire_date,
    i.status,
    (CASE WHEN i.expire_date IS NOT NULL AND i.expire_date < DATE('now') THEN 1 ELSE 0 END) AS is_expired
FROM inventory i
JOIN material m ON i.material_id = m.id
JOIN warehouse w ON i.warehouse_id = w.id
LEFT JOIN storage_location sl ON i.location_id = sl.id;

CREATE VIEW IF NOT EXISTS v_equipment_status AS
SELECT
    e.id,
    e.equip_no,
    e.name,
    e.equip_type,
    e.equipment_status,
    e.run_status,
    d.name AS department_name,
    wc.name AS work_center_name,
    e.location,
    ec.name AS category_name
FROM equipment e
LEFT JOIN org_department d ON e.department_id = d.id
LEFT JOIN org_work_center wc ON e.work_center_id = wc.id
LEFT JOIN equipment_category ec ON e.category_id = ec.id;
"""

# ========== 初始化数据 ==========

INIT_DATA_SQL = """
-- 初始化公司
INSERT OR IGNORE INTO org_company (id, code, name, address) VALUES
(1, 'CRVAB', '内蒙古科为博生物科技有限公司', '内蒙古自治区');

-- 初始化物料分类
INSERT OR IGNORE INTO material_category (id, code, name, level) VALUES
(1, 'RAW', '原料', 0),
(2, 'AUX', '辅料', 0),
(3, 'PKG', '包材', 0),
(4, 'SEMI', '中间品', 0),
(5, 'FIN', '成品', 0),
(6, 'CONS', '耗材', 0);

-- 初始化设备分类
INSERT OR IGNORE INTO equipment_category (id, code, name) VALUES
(1, 'FERMENTER', '发酵罐'),
(2, 'EXTRACTOR', '提取罐'),
(3, 'DRYER', '干燥塔'),
(4, 'CENTRIFUGE', '离心机'),
(5, 'COMPRESSOR', '空压机'),
(6, 'HEAT_EX', '换热器'),
(7, 'PUMP', '泵'),
(8, 'VALVE', '阀门'),
(9, 'INSTRUMENT', '仪表'),
(10, 'MIXER', '混合机'),
(11, 'GRANULATOR', '制粒机'),
(12, 'TANK', '储罐'),
(13, 'BOILER', '锅炉'),
(14, 'PURIFIER', '纯化水'),
(15, 'SEED', '种子罐');

-- 初始化仓库
INSERT OR IGNORE INTO warehouse (id, warehouse_code, name, warehouse_type) VALUES
(1, 'WH-RAW', '原料库', 'raw_material'),
(2, 'WH-PKG', '包材库', 'packaging'),
(3, 'WH-SEMI', '中间品库', 'semi'),
(4, 'WH-FIN', '成品库', 'finished'),
(5, 'WH-COLD', '冷库', 'cold'),
(6, 'WH-QTN', '待检库', 'quarantine'),
(7, 'WH-REJ', '不合格品库', 'rejected');

-- 初始化公用工程系统
INSERT OR IGNORE INTO utility_system (id, system_code, system_name, system_type) VALUES
(1, 'PW-001', '纯化水系统', 'purified_water'),
(2, 'STM-001', '蒸汽系统', 'steam'),
(3, 'CA-001', '压缩空气系统', 'compressed_air'),
(4, 'WW-001', '污水处理系统', 'wastewater'),
(5, 'CW-001', '冷却循环水', 'cooling');
"""


def get_all_ddl():
    """返回所有DDL语句的列表"""
    ddl_statements = [
        # 1. 基础数据
        CREATE_ORG_COMPANY,
        CREATE_ORG_DEPARTMENT,
        CREATE_ORG_WORK_CENTER,
        CREATE_EMPLOYEE,
        CREATE_EMPLOYEE_CERTIFICATION,
        CREATE_EMPLOYEE_TRAINING,
        CREATE_EMPLOYEE_SHIFT,
        CREATE_MATERIAL_CATEGORY,
        CREATE_MATERIAL,
        CREATE_SUPPLIER,
        CREATE_MATERIAL_SUPPLIER,
        CREATE_CUSTOMER,
        CREATE_EQUIPMENT_CATEGORY,
        CREATE_EQUIPMENT,
        CREATE_EQUIPMENT_PARAMETER,
        CREATE_EQUIPMENT_DOCUMENT,
        # 2. 工艺管理
        CREATE_PRODUCT,
        CREATE_PRODUCT_BOM,
        CREATE_ROUTE,
        CREATE_ROUTE_STEP,
        CREATE_PROCESS_PARAM_TEMPLATE,
        CREATE_BATCH_RULE,
        CREATE_BATCH_NUMBER_SEQ,
        CREATE_FERMENTATION_FORMULA,
        CREATE_FERMENTATION_FORMULA_DETAIL,
        CREATE_SOP_DOCUMENT,
        # 3. 生产过程
        CREATE_WORK_ORDER,
        CREATE_BATCH_RECORD,
        CREATE_BATCH_FEEDING_RECORD,
        CREATE_BATCH_FERMENT_PARAM,
        CREATE_BATCH_EXTRACT_RECORD,
        CREATE_BATCH_DRY_RECORD,
        CREATE_BATCH_MIX_RECORD,
        CREATE_BATCH_CIP_RECORD,
        CREATE_BATCH_STERILIZE_RECORD,
        CREATE_BATCH_INTERMEDIATE,
        CREATE_BATCH_OPERATION_LOG,
        CREATE_BATCH_TANK_ASSIGNMENT,
        CREATE_SAMPLING_RECORD,
        CREATE_BATCH_LABEL,
        CREATE_BATCH_ENERGY_CONSUMPTION,
        # 4. 质量管理
        CREATE_QC_STANDARD,
        CREATE_QC_STANDARD_ITEM,
        CREATE_QC_TEST_RECORD,
        CREATE_QC_TEST_DETAIL,
        CREATE_NONCONFORMANCE,
        CREATE_DEVIATION,
        CREATE_CHANGE_MANAGEMENT,
        CREATE_STABILITY_STUDY,
        CREATE_STABILITY_TEST_POINT,
        CREATE_SUPPLIER_AUDIT,
        # 5. 设备管理
        CREATE_EQUIPMENT_MAINTAIN_PLAN,
        CREATE_MAINTAIN_PLAN_ITEM,
        CREATE_MAINTAIN_RECORD,
        CREATE_MAINTAIN_RECORD_DETAIL,
        CREATE_SPARE_PART,
        CREATE_SPARE_PART_USAGE,
        CREATE_EQUIPMENT_CALIBRATION,
        CREATE_CALIBRATION_RECORD,
        CREATE_EQUIPMENT_RUNTIME,
        CREATE_EQUIPMENT_FAULT,
        CREATE_EQUIPMENT_DAILY_CHECK,
        # 6. 仓储物流
        CREATE_WAREHOUSE,
        CREATE_STORAGE_LOCATION,
        CREATE_INVENTORY,
        CREATE_INVENTORY_TRANSACTION,
        CREATE_INVENTORY_CHECK,
        CREATE_INVENTORY_CHECK_DETAIL,
        CREATE_INVENTORY_RESERVATION,
        # 7. 公用工程
        CREATE_UTILITY_SYSTEM,
        CREATE_PURIFIED_WATER_RECORD,
        CREATE_STEAM_SYSTEM_RECORD,
        CREATE_COMPRESSED_AIR_RECORD,
        CREATE_WASTEWATER_RECORD,
    ]
    return ddl_statements


def create_database(db_path=None):
    """创建完整的MES数据库"""
    if db_path is None:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    cursor = conn.cursor()

    print(f"[MES DDL] 创建数据库: {db_path}")
    print(f"[MES DDL] Schema版本: {SCHEMA_VERSION}")

    # 创建所有表
    table_count = 0
    for ddl in get_all_ddl():
        try:
            cursor.execute(ddl)
            table_count += 1
        except sqlite3.Error as e:
            print(f"[ERROR] DDL执行失败: {e}")

    print(f"[MES DDL] 已创建 {table_count} 张表")

    # 创建索引
    for stmt in CREATE_INDEXES.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt + ';')
            except sqlite3.Error as e:
                print(f"[ERROR] 索引创建失败: {e}")

    print("[MES DDL] 索引创建完成")

    # 创建视图
    for stmt in CREATE_VIEWS.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt + ';')
            except sqlite3.Error as e:
                print(f"[ERROR] 视图创建失败: {e}")

    print("[MES DDL] 视图创建完成")

    # 初始化数据
    for stmt in INIT_DATA_SQL.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt + ';')
            except sqlite3.Error as e:
                print(f"[ERROR] 初始化数据失败: {e}")

    conn.commit()
    print("[MES DDL] 初始化数据完成")

    # 验证
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
    tbl_count = cursor.fetchone()[0]
    print(f"[MES DDL] 数据库中实际表数量: {tbl_count}")

    conn.close()
    return tbl_count


def list_all_tables(db_path=None):
    """列出数据库中所有表"""
    if db_path is None:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        print(f"[MES DDL] 数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()

    print(f"\n{'='*60}")
    print(f"MES数据库完整表清单 ({len(tables)} 张表)")
    print(f"{'='*60}")
    for i, (name,) in enumerate(tables, 1):
        print(f"  {i:3d}. {name}")

    conn.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = DB_PATH

    count = create_database(db_path)
    print(f"\n✅ MES核心数据库创建成功！共 {count} 张表。")

    list_all_tables(db_path)
