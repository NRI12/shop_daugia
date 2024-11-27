from datetime import timedelta

class Config:
    SECRET_KEY = 'nothing-my-love-for-you'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/auction_system'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = 'nothing-my-love-for-you'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=30)  # JWT token hết hạn sau 30 giây
    JWT_TOKEN_LOCATION = ['cookies']  # Đặt token trong cookie
    JWT_SESSION_COOKIE = False  # Đảm bảo cookie không bị giới hạn theo phiên trình duyệt
    JWT_COOKIE_SECURE = False  # Đặt thành True trong production nếu dùng HTTPS
    JWT_COOKIE_SAMESITE = 'Lax'  # Hoặc 'None' nếu cần chia sẻ cookie giữa các domain
    JWT_COOKIE_CSRF_PROTECT = False  # Đặt True nếu muốn bảo vệ CSRF
