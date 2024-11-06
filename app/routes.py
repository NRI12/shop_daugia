import os
from flask import Blueprint, app, request, jsonify, render_template
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
    unset_jwt_cookies, set_access_cookies
)
from app.models import User, Auction, Bid, Transaction, Notification, db, Category, Product,ProductImage
from datetime import datetime, timedelta
import bcrypt
from app.schemas import UserSchema, LoginSchema, AuctionSchema, BidSchema
from marshmallow import ValidationError
import pytz
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app as app

api_bp = Blueprint('', __name__)
def get_current_time_in_vietnam():
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    vn_time = datetime.now(vn_tz)
    return vn_time.replace(tzinfo=None)

def validate_input(schema, data):
    try:
        schema.load(data)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

@api_bp.route('/', methods=['GET'])
def index():
    categories = Category.query.all()
    # Lấy các phiên đấu giá mới nhất, sắp xếp theo ID giảm dần
    latest_auctions = Auction.query.filter(Auction.end_time > datetime.utcnow()).order_by(Auction.id.desc()).limit(10).all()
    return render_template('index.html', categories=categories, latest_auctions=latest_auctions)


# 1. Đăng nhập và lấy JWT
@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400
    
    try:
        validated_data = LoginSchema().load(data)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400
    
    user = User.query.filter_by(email=validated_data['email']).first()
    if not user or not bcrypt.checkpw(validated_data['password'].encode('utf-8'), 
                                    user.password.encode('utf-8')):
        return jsonify({"message": "Sai tài khoản hoặc mật khẩu"}), 401
    
    access_token = create_access_token(
        identity=user.id,
        expires_delta=timedelta(days=30)
    )
    
    response = jsonify({
        "message": "Login successful",
        "user": {
            "email": user.email
        }
    })
    
    set_access_cookies(
        response, 
        access_token,
        max_age=30*24*60*60
    )
    
    return response, 200

@api_bp.route('/check-auth', methods=['GET'])
@jwt_required(optional=True)
def check_auth():
    current_user_id = get_jwt_identity()
    
    if current_user_id is None:
        return jsonify({"authenticated": False, "message": "User not logged in"}), 200

    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    return jsonify({
        "authenticated": True,
        "user": {
            "email": user.email
        }
    }), 200

@api_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(response)
    return response, 200

# 2. Đăng ký tài khoản người dùng
@api_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate input
    validation_result = validate_input(UserSchema(), data)
    if validation_result:
        return validation_result
        
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({
            "message": "Email đã được sử dụng"
        }), 409

    # Hash password
    hashed_password = bcrypt.hashpw(
        data['password'].encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')
    
    # Create new user
    new_user = User(
        name=data['name'],
        email=data['email'],
        password=hashed_password,
        phone_number=data.get('phone_number', ''),
        role='user'  # Thêm role nếu cần
    )
    
    db.session.add(new_user)
    db.session.commit()

    # Trả về phản hồi sau khi đăng ký thành công
    return jsonify({"message": "Đăng ký thành công!"}), 201

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


@api_bp.route('/sell-product', methods=['GET'])
@jwt_required()
def sell_product():
    # Lấy danh sách danh mục
    categories = Category.query.all()
    return render_template('create_auction.html', categories=categories)
@api_bp.route('/product/<int:auction_id>', methods=['GET'])
def product_details(auction_id):
    auction = Auction.query.get_or_404(auction_id)
    return render_template('product_details.html', auction=auction)

# 5. Tạo phiên đấu giá mới
@api_bp.route('/auctions', methods=['POST'])
@jwt_required()
def create_product_and_auction():
    try:
        user_id = get_jwt_identity()
        data = request.form

        # Kiểm tra dữ liệu đầu vào
        required_fields = ['product_name', 'category_id', 'start_price', 'end_time']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"message": f"{field} is required"}), 400

        # Chuyển đổi category_id thành số nguyên
        try:
            category_id = int(data.get('category_id'))
        except ValueError:
            return jsonify({"message": "Invalid category_id"}), 400

        # Kiểm tra xem danh mục có tồn tại không
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"message": "Category not found"}), 404

        # Tạo sản phẩm mới
        product = Product(
            name=data['product_name'],
            description=data.get('description', ''),
            category_id=category.id
        )
        db.session.add(product)
        db.session.flush()  # Đảm bảo product.id được tạo trước khi tiếp tục

        # Xử lý hình ảnh nếu có
        if 'product_images' in request.files:
            images = request.files.getlist('product_images')
            for image_file in images:
                if image_file.filename != '':
                    filename = secure_filename(image_file.filename)
                    # Tạo đường dẫn lưu trữ tệp
                    image_folder = os.path.join(app.root_path, 'static', 'uploads', 'products')
                    os.makedirs(image_folder, exist_ok=True)
                    file_path = os.path.join(image_folder, filename)
                    image_file.save(file_path)

                   # Lưu đường dẫn hình ảnh vào bảng ProductImage
                    relative_path = os.path.join('uploads', 'products', filename).replace("\\", "/")
                    product_image = ProductImage(
                        url=relative_path,
                        product_id=product.id
                    )
                    db.session.add(product_image)


        # Chuyển đổi end_time thành đối tượng datetime
        try:
            end_time_str = data['end_time']
            end_time_format = '%Y-%m-%d %H:%M:%S'
            end_time = datetime.strptime(end_time_str, end_time_format)
        except ValueError:
            return jsonify({"message": "Invalid end_time format. Use 'YYYY-MM-DD HH:MM:SS'"}), 400

        # Kiểm tra xem end_time có lớn hơn thời gian hiện tại không
        if end_time <= datetime.utcnow():
            return jsonify({"message": "End time must be in the future"}), 400

        # Chuyển đổi start_price thành float
        try:
            start_price = float(data['start_price'])
        except ValueError:
            return jsonify({"message": "Invalid start_price"}), 400

        # Tạo phiên đấu giá liên kết với sản phẩm vừa tạo
        auction = Auction(
            product_id=product.id,
            start_price=start_price,
            current_price=start_price,
            end_time=end_time,
            seller_id=user_id
        )
        db.session.add(auction)
        db.session.commit()

        return jsonify({
            "message": "Product and auction created successfully",
            "product_id": product.id,
            "auction_id": auction.id
        }), 201

    except Exception as e:
        app.logger.error(f"Error in create_product_and_auction: {e}")

        # Ghi log lỗi
        return jsonify({"message": "Internal server error"}), 500
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
