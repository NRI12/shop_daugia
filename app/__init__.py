from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_wtf import CSRFProtect
from flask_apscheduler import APScheduler

db = SQLAlchemy()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Khởi tạo các extension
    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)
    CORS(app, supports_credentials=True)
    #CSRFProtect(app)
    scheduler.init_app(app)
    scheduler.start() 

    # Đăng ký blueprint routes
    from app.routes import api_bp
    app.register_blueprint(api_bp)

    return app