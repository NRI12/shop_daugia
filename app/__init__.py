# __init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_apscheduler import APScheduler
from functools import partial

db = SQLAlchemy()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)
    CORS(app, supports_credentials=True)
    scheduler.init_app(app)
    
    from app.utils import update_auction_status
    
    # Create wrapper function with app context
    def scheduled_task():
        with app.app_context():
            update_auction_status()
    
    # Start scheduler with wrapped function
    scheduler.start()
    scheduler.add_job(
        id='update_auction_status_job',
        func=scheduled_task,  # Use the wrapper function
        trigger='interval', 
        seconds=5
    )

    # Register blueprints
    from app.routes import api_bp
    app.register_blueprint(api_bp)

    return app