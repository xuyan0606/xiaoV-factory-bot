"""
MES 认证 & 权限模块
Flask-JWT-Extended + RBAC

角色：
  admin    — 全权限（用户管理/系统配置）
  manager  — 班长（所有数据读写+审核）
  operator — 操作员（报工/投料/只读订单批次）
  viewer   — 访客（只读）
"""

import os
import functools
from datetime import timedelta
from flask import jsonify, request
from flask_jwt_extended import (
    JWTManager, create_access_token, get_jwt_identity,
    get_jwt, verify_jwt_in_request
)

# ─── 配置 ────────────────────────────────────────────────

SECRET_KEY = os.environ.get("MES_SECRET_KEY", "mes-2026-change-in-production")

jwt = JWTManager()

# 权限矩阵：role -> set of allowed prefixes
ROLE_PERMISSIONS = {
    "admin":   "*",   # 所有
    "manager": {"orders", "batches", "quality", "equipment",
                "maintenance", "alerts", "work", "shifts", "handover",
                "dashboard"},
    "operator": {"orders", "batches", "work", "shifts", "dashboard"},
    "viewer":  {"orders", "batches", "quality", "equipment",
                "dashboard"},
}


def init_auth(app):
    app.config["JWT_SECRET_KEY"] = SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
    jwt.init_app(app)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return jsonify({"code": 401, "error": "token已过期，请重新登录"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"code": 401, "error": "无效token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"code": 401, "error": "需要登录才能访问"}), 401


# ─── 权限检查 ───────────────────────────────────────────

def _get_user_db():
    """读取用户数据的独立 SQLite 连接（不走 mes_core 的共享连接）"""
    import sqlite3
    conn = sqlite3.connect("/Users/xuyan/software/hermesWorkspace/mes.db")
    conn.row_factory = sqlite3.Row
    return conn



def require_role(*allowed_roles):
    """装饰器：限制访问的 role"""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            # identity = "1" (user_id 字符串)
            user_id = get_jwt_identity()
            db = _get_user_db()
            try:
                row = db.execute(
                    "SELECT role FROM users WHERE user_id=? AND status='active'",
                    (int(user_id),)
                ).fetchone()
                if not row:
                    return jsonify({"code": 401, "error": "用户不存在或已禁用"}), 401
                role = row[0]
            finally:
                db.close()
            if role not in allowed_roles:
                return jsonify({"code": 403, "error": f"需要角色 {allowed_roles}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(prefix):
    """装饰器：限制访问的 resource prefix"""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            db = _get_user_db()
            try:
                row = db.execute(
                    "SELECT role FROM users WHERE user_id=? AND status='active'",
                    (int(user_id),)
                ).fetchone()
                if not row:
                    return jsonify({"code": 401, "error": "用户不存在或已禁用"}), 401
                role = row[0]
            finally:
                db.close()
            perms = ROLE_PERMISSIONS.get(role, set())
            if "*" not in perms and prefix not in perms:
                return jsonify({"code": 403, "error": f"角色 {role} 无权访问 {prefix}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─── 登录/注册 ───────────────────────────────────────────

def auth_routes(app, db_module):
    """
    在 Flask app 上注册认证路由。
    db_module: mes_core 模块（直接操作 SQLite，不走 mes_db 抽象）
    """

    @app.route("/api/auth/login", methods=["POST"])
    def auth_login():
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"code": 400, "error": "用户名和密码不能为空"}), 400

        with db_module.use_db() as db:
            row = db.execute(
                "SELECT user_id, username, password_hash, role, full_name "
                "FROM users WHERE username=? AND status='active'",
                (username,)
            ).fetchone()

        if not row:
            return jsonify({"code": 401, "error": "用户名或密码错误"}), 401

        import bcrypt
        pw_hash = row["password_hash"]
        if not bcrypt.checkpw(password.encode(), pw_hash.encode()):
            return jsonify({"code": 401, "error": "用户名或密码错误"}), 401

        token = create_access_token(identity=str(row["user_id"]))

        return jsonify({
            "code": 0,
            "token": token,
            "user": {
                "user_id":  row["user_id"],
                "username": row["username"],
                "full_name": row["full_name"] or row["username"],
                "role":     row["role"],
            }
        })

    @app.route("/api/auth/me", methods=["GET"])
    @require_permission("*")
    def auth_me():
        user_id = get_jwt_identity()
        db = _get_user_db()
        try:
            row = db.execute(
                "SELECT user_id, username, full_name, role, department, phone "
                "FROM users WHERE user_id=? AND status='active'",
                (int(user_id),)
            ).fetchone()
            if not row:
                return jsonify({"code": 401, "error": "用户不存在"}), 401
            return jsonify({"code": 0, "user": dict(row)})
        finally:
            db.close()

    @app.route("/api/auth/register", methods=["POST"])
    @require_role("admin")
    def auth_register():
        """仅管理员可创建用户"""
        data = request.get_json() or {}
        username  = (data.get("username") or "").strip()
        password  = data.get("password") or ""
        full_name = data.get("full_name") or ""
        role      = data.get("role") or "operator"
        department = data.get("department") or ""
        phone     = data.get("phone") or ""

        if not username or len(password) < 6:
            return jsonify({"code": 400, "error": "用户名不能为空，密码至少6位"}), 400

        if role not in ROLE_PERMISSIONS:
            return jsonify({"code": 400, "error": f"无效角色 {role}"}), 400

        import bcrypt
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        with db_module.use_db() as db:
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, department, phone) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (username, pw_hash, full_name, role, department, phone)
                )
                return jsonify({"code": 0, "message": "用户创建成功"})
            except Exception as e:
                if "UNIQUE" in str(e):
                    return jsonify({"code": 409, "error": "用户名已存在"}), 409
                return jsonify({"code": 500, "error": str(e)}), 500

    @app.route("/api/auth/users", methods=["GET"])
    @require_role("admin", "manager")
    def auth_list_users():
        """列出所有用户（密码已脱敏）"""
        with db_module.use_db() as db:
            rows = db.execute(
                "SELECT user_id, username, full_name, role, department, phone, status, created_at "
                "FROM users ORDER BY created_at DESC"
            ).fetchall()
        return jsonify({
            "code": 0,
            "users": [dict(r) for r in rows]
        })

    @app.route("/api/auth/users/<int:user_id>", methods=["PUT"])
    @require_role("admin")
    def auth_update_user(user_id):
        data = request.get_json() or {}
        role  = data.get("role")
        status = data.get("status")
        with db_module.use_db() as db:
            if role:
                db.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
            if status:
                db.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        return jsonify({"code": 0, "message": "更新成功"})

    @app.route("/api/auth/password", methods=["PUT"])
    @require_permission("*")
    def auth_change_password():
        """修改当前用户密码"""
        data = request.get_json() or {}
        old_pw = data.get("old_password") or ""
        new_pw = data.get("new_password") or ""
        if len(new_pw) < 6:
            return jsonify({"code": 400, "error": "新密码至少6位"}), 400

        identity = get_jwt_identity()
        with db_module.use_db() as db:
            row = db.execute(
                "SELECT password_hash FROM users WHERE user_id=?",
                (identity["user_id"],)
            ).fetchone()
        if not bcrypt.checkpw(old_pw.encode(), row["password_hash"].encode()):
            return jsonify({"code": 401, "error": "原密码错误"}), 401

        import bcrypt
        new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        with db_module.use_db() as db:
            db.execute("UPDATE users SET password_hash=? WHERE user_id=?",
                       (new_hash, identity["user_id"]))
        return jsonify({"code": 0, "message": "密码已更新"})
