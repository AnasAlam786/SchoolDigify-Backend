# src/__init__.py

import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
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

    print("=== FLASK CREATED ===", flush=True)

    CORS(
        app,
        supports_credentials=True,
        origins=[
            "http://localhost:5173",  # Vite
            "http://localhost:3000",  # CRA
            "https://schooldigify.com",
            "https://schooldigify.vercel.app/",
            "https://schooldigify-git-main-schooldigify.vercel.app/login",
            
        ]
    )

    # ——— Make getattr available in Jinja2 templates ———
    app.jinja_env.globals['getattr'] = getattr

    # ——— App configuration ———
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config['SECRET_KEY'] = os.getenv('SESSION_KEY')


    # ——— DATABASE CONFIG (Supabase-safe) ———
    uri = os.getenv('URI')
    if uri:
        # Ensure Postgres schema is selected explicitly to prevent "no schema has been selected to create in".
        if 'options=' not in uri:
            sep = '&' if '?' in uri else '?'
            uri = f"{uri}{sep}options=-c%20search_path%3Dpublic"
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 🔴 CRITICAL: Supabase connection pool limits
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 10,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
        'connect_args': {
            'options': '-c search_path=public'
        }
    }

    # ——— SESSION CONFIGURATION (Flask-Session) ———
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
    app.config['SESSION_FILE_THRESHOLD'] = 500
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 7  # 7 days
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = not app.debug    
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True

    # ——— Initialize extensions ———
    sess.init_app(app)
    db.metadata.schema = 'public'
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


    # ——— Register blueprints ———
    from .controller import register_blueprints
    register_blueprints(app)

    # ——— Ensure models are imported and tables exist in DB ———
    # NOTE: For production, prefer Alembic migrations instead of create_all().
    with app.app_context():
        import src.model  # ensure model modules are imported and SQLAlchemy metadata is populated

    # ——— Inject permissions globally in templates ———
    from src.controller.permissions.has_permission import has_permission

    @app.context_processor
    def inject_permissions():
        return dict(has_permission=has_permission)

    return app
