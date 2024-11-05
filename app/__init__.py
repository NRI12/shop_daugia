from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_wtf import CSRFProtect
from flask_marshmallow import Marshmallow
from flask_apscheduler import APScheduler

db = SQLAlchemy()
ma = Marshmallow()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Khởi tạo các extension
    db.init_app(app)
    ma.init_app(app)
    Migrate(app, db)
    JWTManager(app)
    CORS(app)
    CSRFProtect(app)
    scheduler.init_app(app)

    # Đăng ký blueprint routes
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Đăng ký task sau khi ứng dụng đã được tạo
    from app.scheduler_tasks import close_expired_auctions
    scheduler.add_job(
        id='close_expired_auctions',
        func=close_expired_auctions,
        trigger='interval',
        seconds=3  # Chạy mỗi phút
    )
    if not scheduler.running:
        scheduler.init_app(app)
        scheduler.start()
    return app