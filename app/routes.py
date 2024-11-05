from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import User, Auction, Bid, Transaction, Notification, db, Category, Product
from datetime import datetime
import bcrypt
from app.schemas import UserSchema, LoginSchema, AuctionSchema, BidSchema
from marshmallow import ValidationError
import pytz
from datetime import datetime

api_bp = Blueprint('api', __name__)

def get_current_time_in_vietnam():
    """Lấy thời gian hiện tại theo giờ Việt Nam và loại bỏ timezone."""
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    vn_time = datetime.now(vn_tz)  # Thời gian với timezone GMT+7
    return vn_time.replace(tzinfo=None)  # Loại bỏ timezone
def validate_input(schema, data):
    """Hàm tiện ích để xác thực đầu vào"""
    try:
        schema.load(data)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

# 1. Đăng nhập và lấy JWT
@api_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    validation_result = validate_input(LoginSchema(), data)
    if validation_result:
        return validation_result

    user = User.query.filter_by(email=data['email']).first()
    if not user or not bcrypt.checkpw(data['password'].encode('utf-8'), user.password.encode('utf-8')):
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({'access_token': access_token}), 200
# 2. Đăng ký tài khoản người dùng
@api_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    validation_result = validate_input(UserSchema(), data)
    if validation_result:
        return validation_result

    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    new_user = User(
        name=data['name'], email=data['email'], 
        password=hashed_password.decode('utf-8'), 
        phone_number=data.get('phone_number', '')
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created successfully"}), 201
@api_bp.route('/categories', methods=['POST'])
@jwt_required()
def create_category():
    data = request.json
    if 'name' not in data:
        return jsonify({"message": "Category name is required"}), 400

    category = Category(name=data['name'])
    db.session.add(category)
    db.session.commit()
    return jsonify({"message": "Category created successfully", "category_id": category.id}), 201

# 3. Lấy danh sách các phiên đấu giá
@api_bp.route('/auctions', methods=['POST'])
@jwt_required()
def create_product_and_auction():
    user_id = get_jwt_identity()
    data = request.json

    # Kiểm tra xem danh mục có tồn tại không
    category = Category.query.get(data.get('category_id'))
    if not category:
        return jsonify({"message": "Category not found"}), 404

    # Tạo sản phẩm mới
    product = Product(
        name=data['product_name'],
        description=data.get('description', ''),
        image_url=data.get('image_url', ''),
        category_id=category.id
    )
    db.session.add(product)
    db.session.flush()  # Đảm bảo product.id được tạo trước khi tiếp tục

    # Tạo phiên đấu giá liên kết với sản phẩm vừa tạo
    auction = Auction(
        product_id=product.id,
        start_price=data['start_price'],
        current_price=data['start_price'],
        end_time=datetime.strptime(data['end_time'], '%Y-%m-%d %H:%M:%S'),
        seller_id=user_id
    )
    db.session.add(auction)
    db.session.commit()

    return jsonify({
        "message": "Product and auction created successfully",
        "product_id": product.id,
        "auction_id": auction.id
    }), 201

# 4. Lấy thông tin chi tiết của một phiên đấu giá
@api_bp.route('/auctions/<int:auction_id>', methods=['GET'])
def get_auction(auction_id):
    auction = Auction.query.get_or_404(auction_id)
    return jsonify({
        'id': auction.id,
        'title': auction.title,
        'description': auction.description,
        'current_price': auction.current_price,
        'end_time': auction.end_time,
        'status': auction.status
    }), 200

# 5. Tạo phiên đấu giá mới
@api_bp.route('/auctions', methods=['POST'])
@jwt_required()
def create_auction():
    user_id = get_jwt_identity()
    data = request.json
    validation_result = validate_input(AuctionSchema(), data)
    if validation_result:
        return validation_result

    auction = Auction(
        title=data['title'], description=data.get('description', ''),
        start_price=data['start_price'], 
        current_price=data['start_price'], 
        end_time=datetime.strptime(data['end_time'], '%Y-%m-%d %H:%M:%S'), 
        seller_id=user_id
    )
    db.session.add(auction)
    db.session.commit()
    return jsonify({"message": "Auction created successfully"}), 201

# 6. Đặt giá thầu
@api_bp.route('/bids', methods=['POST'])
@jwt_required()
def create_bid():
    user_id = get_jwt_identity()
    data = request.json
    validation_result = validate_input(BidSchema(), data)
    if validation_result:
        return validation_result

    auction = Auction.query.get(data['auction_id'])
    if not auction or auction.status != 'ongoing' or auction.end_time < datetime.utcnow():
        return jsonify({"message": "Invalid auction"}), 400

    if data['amount'] <= auction.current_price:
        return jsonify({"message": "Bid amount must be greater than current price"}), 400

    bid = Bid(amount=data['amount'], auction_id=data['auction_id'], user_id=user_id)
    auction.current_price = data['amount']
    db.session.add(bid)
    db.session.commit()
    return jsonify({"message": "Bid placed successfully"}), 201

# 7. Xác định người thắng cuộc của phiên đấu giá
@api_bp.route('/auctions/<int:auction_id>/winner', methods=['POST'])
@jwt_required()
def determine_winner(auction_id):
    current_time = get_current_time_in_vietnam()
    auction = Auction.query.get(auction_id)

    # Kiểm tra phiên đấu giá tồn tại
    if not auction:
        return jsonify({"message": "Auction not found"}), 404

    # Kiểm tra nếu phiên đấu giá đã hoàn thành
    if auction.status == 'completed':
        return jsonify({"message": "Auction already completed"}), 400

    # Kiểm tra nếu thời gian hiện tại chưa quá thời gian kết thúc
    if current_time < auction.end_time:
        return jsonify({"message": "Auction has not ended yet"}), 400

    # Lấy giá thầu cao nhất
    winner_bid = Bid.query.filter_by(auction_id=auction_id).order_by(Bid.amount.desc()).first()
    if not winner_bid:
        return jsonify({"message": "No bids found for this auction"}), 404

    # Lấy thông tin người thắng và sản phẩm
    winner = User.query.get(winner_bid.user_id)
    product = Product.query.get(auction.product_id)

    # Cập nhật trạng thái phiên đấu giá
    auction.status = 'completed'

    # Kiểm tra nếu người mua và người bán là cùng một người
    if winner_bid.user_id == auction.seller_id:
        message_for_both = (
            f"You won your own auction for '{product.name}' with a bid of {winner_bid.amount}."
        )
        notification = Notification(
            message=message_for_both,
            user_id=winner_bid.user_id,
            auction_id=auction_id
        )
        db.session.add(notification)
    else:
        # Tạo thông báo cho người thắng nếu chưa có
        winner_notification = Notification.query.filter_by(
            auction_id=auction_id, user_id=winner_bid.user_id
        ).first()
        if not winner_notification:
            winner_notification = Notification(
                message=f"Congratulations! You won the auction for '{product.name}' with a bid of {winner_bid.amount}.",
                user_id=winner_bid.user_id,
                auction_id=auction_id
            )
            db.session.add(winner_notification)

        # Tạo thông báo cho người bán nếu chưa có
        seller_notification = Notification.query.filter_by(
            auction_id=auction_id, user_id=auction.seller_id
        ).first()
        if not seller_notification:
            seller_notification = Notification(
                message=f"Your auction for '{product.name}' has ended. The winning bid was {winner_bid.amount}.",
                user_id=auction.seller_id,
                auction_id=auction_id
            )
            db.session.add(seller_notification)

    # Lưu thay đổi vào cơ sở dữ liệu
    db.session.commit()

    return jsonify({
        "message": "Winner determined successfully",
        "winner": winner.name,
        "winning_bid": winner_bid.amount
    }), 200

# 8. Tạo giao dịch cho người thắng cuộc
@api_bp.route('/transactions', methods=['POST'])
@jwt_required()
def create_transaction():
    user_id = get_jwt_identity()
    data = request.json
    auction = Auction.query.get(data['auction_id'])

    if auction.status != 'completed':
        return jsonify({"message": "Auction not completed"}), 400

    winner_bid = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc()).first()
    if winner_bid.user_id != user_id:
        return jsonify({"message": "You are not the winner"}), 403

    transaction = Transaction(
        auction_id=auction.id,
        buyer_id=user_id,
        amount=auction.current_price,
        status='completed'
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({"message": "Transaction created successfully"}), 201

# 9. Lấy danh sách thông báo của người dùng
@api_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = get_jwt_identity()
    notifications = Notification.query.filter_by(user_id=user_id).all()
    result = [
        {
            'id': notification.id,
            'message': notification.message,
            'auction_id': notification.auction_id,
            'created_at': notification.created_at
        } for notification in notifications
    ]
    return jsonify(result), 200
