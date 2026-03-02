# src/__init__.py

import os
from dotenv import load_dotenv
from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
import redis

# ——— Load environment variables ———
load_dotenv()

# ——— Instantiate extensions (DO NOT bind app here) ———
db = SQLAlchemy()
sess = Session()
r = None  # Redis instance


def create_app():
    global r

    app = Flask(
        __name__,
        template_folder='view/templates',
        static_folder='view/static'
    )

    # ——— Make getattr available in Jinja2 templates ———
    app.jinja_env.globals['getattr'] = getattr

    # ——— App configuration ———
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config['SECRET_KEY'] = os.getenv('SESSION_KEY')

    # app.config.update(
    #     SERVER_NAME="schooldigify.com",
    #     SESSION_COOKIE_DOMAIN=".schooldigify.com",
    #     SESSION_COOKIE_SAMESITE="Lax",
    # )

    # ——— DATABASE CONFIG (Supabase-safe) ———
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 🔴 CRITICAL: Supabase connection pool limits
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 10,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }

    # ——— SESSION CONFIGURATION (Flask-Session) ———
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
    app.config['SESSION_FILE_THRESHOLD'] = 500
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 7  # 7 days
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True   # False for localhost
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True

    # ——— Initialize extensions ———
    sess.init_app(app)
    db.init_app(app)

    # 🔴 CRITICAL: ALWAYS release DB session after request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    # ——— Redis Cloud setup (independent of DB) ———
    r = redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT')),
        username=os.getenv('REDIS_USERNAME', 'default'),
        password=os.getenv('REDIS_PASSWORD'),
        decode_responses=True
    )

    try:
        r.ping()
        print("✅ Connected to Redis Cloud successfully.")
    except redis.exceptions.ConnectionError as e:
        print("❌ Redis connection failed:", e)

    # # ——— Subdomain Management ———
    # from .controller.utils.subdomain_helper import (
    #     extract_school_id_from_request,
    #     is_authenticated_for_subdomain,
    #     url_for_school
    # )

    # @app.before_request
    # def validate_subdomain_access():
    #     from flask import request, redirect, url_for, session

    #     # Skip non-subdomain routes
    #     if not request.blueprint or not request.blueprint.endswith('tenant_bp'):
    #         return

    #     school_id = extract_school_id_from_request()

    #     if not is_authenticated_for_subdomain(school_id):
    #         session.clear()
    #         return redirect(url_for('login_bp.login'))

    # @app.context_processor
    # def inject_subdomain_helpers():
    #     """Inject subdomain utilities into all templates"""
    #     return dict(url_for_school=url_for_school, school_id=extract_school_id_from_request())

    # ——— Register blueprints ———
    from .controller import register_blueprints
    register_blueprints(app)

    # ——— Inject permissions globally in templates ———
    from src.controller.permissions.has_permission import has_permission

    @app.context_processor
    def inject_permissions():
        return dict(has_permission=has_permission)

    return app
