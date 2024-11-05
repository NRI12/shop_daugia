from datetime import timedelta

class Config:
    SECRET_KEY = 'nothing-my-love-for-you'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/auction_system'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'nothing-my-love-for-you'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)  # JWT token hết hạn sau 1 giờ
