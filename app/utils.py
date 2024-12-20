# utils.py
from datetime import datetime
import bcrypt
from flask import current_app, jsonify
from marshmallow import ValidationError
from app.models import Auction, Bid, Category, Notification, Product, Transaction, User, db
import pytz

def get_current_time_in_vietnam():
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    vn_time = datetime.now(vn_tz)
    return vn_time.replace(tzinfo=None)

def validate_input(schema, data):
    try:
        schema.load(data)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_auction_by_id(auction_id):
    return Auction.query.get(auction_id)

def get_winner_bid(auction_id):
    return Bid.query.filter_by(auction_id=auction_id).order_by(Bid.amount.desc()).first()

def get_product_by_id(product_id):
    return Product.query.get(product_id)

def get_category_by_id(category_id):
    return Category.query.get(category_id)

def create_notification(message, user_id, auction_id):
    notification = Notification(message=message, user_id=user_id, auction_id=auction_id)
    db.session.add(notification)
    db.session.commit()

def update_auction_status():
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time = datetime.now(vn_tz).replace(tzinfo=None)

    # Lấy tất cả các phiên đấu giá đã hết hạn nhưng vẫn ở trạng thái 'ongoing'
    expired_auctions = Auction.query.filter(
        Auction.status == 'ongoing', 
        Auction.end_time < current_time
    ).all()

    for auction in expired_auctions:
        # Cập nhật trạng thái đấu giá thành 'completed'
        auction.status = 'completed'

        # Tìm giá thầu cao nhất để xác định người thắng cuộc
        highest_bid = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc()).first()
        if highest_bid:
            # Tạo giao dịch nếu có người thắng cuộc
            transaction = Transaction(
                auction_id=auction.id,
                buyer_id=highest_bid.user_id,
                amount=highest_bid.amount,
                status='pending'  # Đặt trạng thái giao dịch thành 'completed'
            )
            db.session.add(transaction)

            # Gửi thông báo tới người thắng cuộc và người bán
            winner_message = f"Chúc mừng! Bạn đã thắng phiên đấu giá cho '{auction.product.name}' với giá {highest_bid.amount} VND."
            seller_message = f"Phiên đấu giá của bạn cho '{auction.product.name}' đã kết thúc. Giá thầu thắng là {highest_bid.amount} VND."

            create_notification(winner_message, highest_bid.user_id, auction.id)
            create_notification(seller_message, auction.seller_id, auction.id)

        db.session.commit()
        print(f"Phiên đấu giá {auction.id} đã được cập nhật và giao dịch thành công được tạo.")

def get_admin_user(current_user_id):
    user = User.query.get(current_user_id)
    if not user or user.role != 'admin':
        return None
    return user

def format_user_data(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None,
        "last_login": user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else None
    }

def get_user_statistics(user_id):
    total_auctions = Auction.query.filter_by(seller_id=user_id).count()
    total_bids = Bid.query.filter_by(user_id=user_id).count()
    total_transactions = Transaction.query.filter_by(buyer_id=user_id).count()
    return {
        "total_auctions": total_auctions,
        "total_bids": total_bids,
        "total_transactions": total_transactions
    }

def delete_user_data(user_id):
    Notification.query.filter_by(user_id=user_id).delete()
    Bid.query.filter_by(user_id=user_id).delete()
    Transaction.query.filter_by(buyer_id=user_id).delete()

    auctions = Auction.query.filter_by(seller_id=user_id).all()
    for auction in auctions:
        Bid.query.filter_by(auction_id=auction.id).delete()
        Transaction.query.filter_by(auction_id=auction.id).delete()
        Notification.query.filter_by(auction_id=auction.id).delete()
        db.session.delete(auction)

    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()

def export_all_users():
    users_data = []
    users = User.query.all()
    for user in users:
        stats = get_user_statistics(user.id)
        users_data.append({
            "ID": user.id,
            "Tên": user.name,
            "Email": user.email,
            "Số điện thoại": user.phone_number or "",
            "Vai trò": user.role,
            "Ngày tạo": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
            "Lần đăng nhập cuối": user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else "",
            "Số phiên đấu giá": stats["total_auctions"],
            "Số lượt đặt giá": stats["total_bids"],
            "Số giao dịch": stats["total_transactions"]
        })
    return users_data