import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template, current_app as app
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
    unset_jwt_cookies, set_access_cookies
)
from werkzeug.utils import secure_filename
from sqlalchemy import desc, asc,func
from marshmallow import ValidationError
from app.models import User, Auction, Bid, Transaction, Notification, db, Category, Product, ProductImage
from app.schemas import UserSchema, LoginSchema, BidSchema
from app.utils import *
from sqlalchemy.exc import SQLAlchemyError

api_bp = Blueprint('', __name__)

now_time = get_current_time_in_vietnam()

@api_bp.route('/', methods=['GET'])
def index():
    categories = Category.query.all()
    latest_auctions = Auction.query.filter(Auction.end_time > now_time, Auction.status == 'ongoing').order_by(Auction.id.desc()).limit(10).all()
    return render_template('index.html', categories=categories, latest_auctions=latest_auctions)

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400
    
    try:
        validated_data = LoginSchema().load(data)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400
    
    user = get_user_by_email(validated_data['email'])
    if not user or not check_password(validated_data['password'], user.password):
        return jsonify({"message": "Sai tài khoản hoặc mật khẩu"}), 401
    
    user.update_last_login()
    access_token = create_access_token(identity=user.id, expires_delta=timedelta(hours=2))
    
    # Truyền role của người dùng
    is_admin = get_admin_user(user.id)  # Kiểm tra xem user có phải admin không
    role = "admin" if is_admin else "user"
    
    response = jsonify({
        "message": "Đăng nhập thành công", 
        "user": {"email": user.email, "role": role}, 
        "access_token": access_token
    })
    set_access_cookies(response, access_token, max_age=30*24*60*60)
    
    return response, 200


@api_bp.route('/check-auth', methods=['GET'])
@jwt_required(optional=True)
def check_auth():
    current_user_id = get_jwt_identity()
    
    if current_user_id is None:
        return jsonify({"authenticated": False, "message": "Người dùng chưa đăng nhập"}), 200

    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"message": "Không tìm thấy người dùng"}), 404

    return jsonify({"authenticated": True, "user": {"email": user.email}}), 200

@api_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({"message": "Đăng xuất thành công"})
    unset_jwt_cookies(response)
    return response, 200

@api_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    validation_result = validate_input(UserSchema(), data)
    if validation_result:
        return validation_result
        
    if get_user_by_email(data['email']):
        return jsonify({"message": "Email đã được sử dụng"}), 409

    hashed_password = hash_password(data['password'])
    
    new_user = User(
        name=data['name'],
        email=data['email'],
        password=hashed_password,
        phone_number=data.get('phone_number', ''),
        role='user',
        created_at=now_time,
        last_login=now_time
    )
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "Đăng ký thành công!"}), 201

@api_bp.route('/products', methods=['GET'])
def get_filtered_products():
    category_id = request.args.get('category', type=int)
    min_price = request.args.get('min_price', type=float, default=0)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = 9
    location = request.args.get('location')

    query = db.session.query(Product, Auction).join(Auction, Product.id == Auction.product_id)

    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if min_price is not None:
        query = query.filter(Auction.current_price >= min_price)
    if max_price is not None:
        query = query.filter(Auction.current_price <= max_price)
    
    if location:
        query = query.filter(Product.location == location)

    locations = [loc[0] for loc in db.session.query(Product.location).distinct().filter(Product.location != None).all()]

    if sort_by == 'price_low':
        query = query.order_by(asc(Auction.current_price))
    elif sort_by == 'price_high':
        query = query.order_by(desc(Auction.current_price))
    elif sort_by == 'oldest':
        query = query.order_by(asc(Product.created_at))
    else:
        query = query.order_by(desc(Product.created_at))
    
    total = query.count()
    products_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    categories = Category.query.all()
    price_range = db.session.query(db.func.min(Auction.current_price), db.func.max(Auction.current_price)).first()
    
    return render_template(
        'shop.html',
        products=products_pagination.items,
        locations=locations,
        categories=categories,
        current_category=category_id,
        price_range=price_range,
        current_min_price=min_price,
        current_max_price=max_price,
        current_sort=sort_by,
        pagination=products_pagination,
        total_products=total
    )

@api_bp.route('/api/filter-products', methods=['GET'])
def api_filter_products():
    pass

@api_bp.route('/categories', methods=['POST'])
@jwt_required()
def create_category():
    data = request.json
    if 'name' not in data:
        return jsonify({"message": "Tên danh mục là bắt buộc"}), 400

    category = Category(name=data['name'])
    db.session.add(category)
    db.session.commit()
    return jsonify({"message": "Tạo danh mục thành công", "category_id": category.id}), 201

@api_bp.route('/sell_product', methods=['GET'])
@jwt_required()
def sell_product():
    categories = Category.query.all()
    return render_template('create_auction.html', categories=categories)

@api_bp.route('/product/<int:auction_id>', methods=['GET'])
def product_details(auction_id):
    auction = get_auction_by_id(auction_id)
    now = get_current_time_in_vietnam()
    unique_bidders = db.session.query(func.count(func.distinct(Bid.user_id))).filter(Bid.auction_id == auction.id).scalar()

    # Truy vấn Transaction để lấy thông tin người thắng cuộc
    winning_transaction = Transaction.query.filter_by(auction_id=auction.id, status='completed').first()
    winner = winning_transaction.buyer_id if winning_transaction else None

    return render_template('product_details.html', auction=auction, now=now, winner=winner,        unique_bidders=unique_bidders
)


@api_bp.route('/auctions', methods=['POST'])
@jwt_required()
def create_product_and_auction():
    try:
        user_id = get_jwt_identity()
        data = request.form

        required_fields = ['product_name', 'category_id', 'start_price', 'end_time']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"message": f"{field} là bắt buộc"}), 400

        try:
            category_id = int(data.get('category_id'))
        except ValueError:
            return jsonify({"message": "category_id không hợp lệ"}), 400

        category = get_category_by_id(category_id)
        if not category:
            return jsonify({"message": "Không tìm thấy danh mục"}), 404

        product = Product(
            name=data['product_name'],
            description=data.get('description', ''),
            category_id=category.id
        )
        db.session.add(product)
        db.session.flush()

        if 'product_images' in request.files:
            images = request.files.getlist('product_images')
            for image_file in images:
                if image_file.filename != '':
                    filename = secure_filename(image_file.filename)
                    image_folder = os.path.join(app.root_path, 'static', 'uploads', 'products')
                    os.makedirs(image_folder, exist_ok=True)
                    file_path = os.path.join(image_folder, filename)
                    image_file.save(file_path)

                    relative_path = os.path.join('uploads', 'products', filename).replace("\\", "/")
                    product_image = ProductImage(url=relative_path, product_id=product.id)
                    db.session.add(product_image)

        try:
            end_time = datetime.strptime(data['end_time'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({"message": "Định dạng end_time không hợp lệ. Sử dụng 'YYYY-MM-DD HH:MM:SS'"}), 400

        if end_time <= now_time:
            return jsonify({"message": "Thời gian kết thúc phải lớn hơn thời gian hiện tại"}), 400

        try:
            start_price = float(data['start_price'])
        except ValueError:
            return jsonify({"message": "start_price không hợp lệ"}), 400

        auction = Auction(
            product_id=product.id,
            start_price=start_price,
            current_price=start_price,
            end_time=end_time,
            seller_id=user_id,
        )
        db.session.add(auction)
        db.session.commit()

        return jsonify({"message": "Phiên đấu giá đã được tạo và đang chờ phê duyệt", "product_id": product.id, "auction_id": auction.id}), 201

    except Exception as e:
        app.logger.error(f"Lỗi trong create_product_and_auction: {e}")
        return jsonify({"message": "Lỗi máy chủ nội bộ"}), 500

@api_bp.route('/auctions/<int:auction_id>/current_price', methods=['GET'])
def get_current_price(auction_id):
    auction = get_auction_by_id(auction_id)
    return jsonify({'current_price': auction.current_price})

@api_bp.route('/bids', methods=['POST'])
@jwt_required()
def create_bid():
    user_id = get_jwt_identity()
    data = request.json
    validation_result = validate_input(BidSchema(), data)
    if validation_result:
        return validation_result

    auction = get_auction_by_id(data['auction_id'])
    current_time = get_current_time_in_vietnam()
    
    if not auction or auction.status != 'ongoing' or auction.end_time < current_time:
        return jsonify({"message": "Phiên đấu giá không hợp lệ hoặc đã kết thúc"}), 400

    if auction.seller_id == user_id:
        return jsonify({"message": "Bạn không thể đặt giá thầu cho phiên đấu giá của chính mình"}), 400

    if data['amount'] <= auction.current_price:
        return jsonify({"message": "Số tiền đặt giá thầu phải lớn hơn giá hiện tại"}), 400

    bid = Bid(amount=data['amount'], auction_id=data['auction_id'], user_id=user_id)
    auction.current_price = data['amount']
    db.session.add(bid)
    db.session.commit()
    return jsonify({"message": "Đặt giá thầu thành công"}), 201

@api_bp.route('/auctions/<int:auction_id>/winner', methods=['POST'])
@jwt_required()
def determine_winner(auction_id):
    current_time = get_current_time_in_vietnam()
    auction = get_auction_by_id(auction_id)

    if not auction:
        return jsonify({"message": "Không tìm thấy phiên đấu giá"}), 404

    if auction.status == 'completed':
        return jsonify({"message": "Phiên đấu giá đã hoàn thành"}), 400

    if current_time < auction.end_time:
        return jsonify({"message": "Phiên đấu giá chưa kết thúc"}), 400

    winner_bid = get_winner_bid(auction_id)
    if not winner_bid:
        return jsonify({"message": "Không có giá thầu nào cho phiên đấu giá này"}), 404

    winner = User.query.get(winner_bid.user_id)
    product = get_product_by_id(auction.product_id)
    auction.status = 'completed'

    if winner_bid.user_id == auction.seller_id:
        message_for_both = f"Bạn đã thắng phiên đấu giá của chính mình cho '{product.name}' với giá thầu {winner_bid.amount}."
        create_notification(message_for_both, winner_bid.user_id, auction_id)
    else:
        winner_notification = Notification.query.filter_by(auction_id=auction_id, user_id=winner_bid.user_id).first()
        if not winner_notification:
            create_notification(
                f"Chúc mừng! Bạn đã thắng phiên đấu giá cho '{product.name}' với giá thầu {winner_bid.amount}.",
                winner_bid.user_id,
                auction_id
            )

        seller_notification = Notification.query.filter_by(auction_id=auction_id, user_id=auction.seller_id).first()
        if not seller_notification:
            create_notification(
                f"Phiên đấu giá của bạn cho '{product.name}' đã kết thúc. Giá thầu thắng là {winner_bid.amount}.",
                auction.seller_id,
                auction_id
            )

    db.session.commit()

    return jsonify({"message": "Xác định người thắng thành công", "winner": winner.name, "winning_bid": winner_bid.amount}), 200

@api_bp.route('/transactions', methods=['POST'])
@jwt_required()
def create_transaction():
    user_id = get_jwt_identity()
    data = request.json
    auction = get_auction_by_id(data['auction_id'])

    if auction.status != 'completed':
        return jsonify({"message": "Phiên đấu giá chưa hoàn thành"}), 400

    winner_bid = get_winner_bid(auction.id)
    if winner_bid.user_id != user_id:
        return jsonify({"message": "Bạn không phải là người thắng"}), 403

    transaction = Transaction(
        auction_id=auction.id,
        buyer_id=user_id,
        amount=auction.current_price,
        status='completed'
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({"message": "Tạo giao dịch thành công"}), 201
@api_bp.route('/cart', methods=['GET'])
@jwt_required()
def get_user_auction():
    user_id = get_jwt_identity()

    # Truy vấn các phiên đấu giá đang diễn ra hoặc đã hoàn thành mà người dùng đã thắng, chỉ lấy phiên đấu giá mới nhất
    latest_user_bids_subquery = db.session.query(
        Bid.auction_id.label('auction_id'),
        db.func.max(Bid.id).label('latest_bid_id')
    ).filter(Bid.user_id == user_id).group_by(Bid.auction_id).subquery()

    active_auctions = db.session.query(
        Auction, Product, Bid, Category
    ).join(Product, Auction.product_id == Product.id
    ).join(latest_user_bids_subquery, latest_user_bids_subquery.c.auction_id == Auction.id
    ).join(Bid, Bid.id == latest_user_bids_subquery.c.latest_bid_id
    ).outerjoin(Category, Product.category_id == Category.id
    ).filter((Auction.end_time > now_time) | (Auction.status == 'completed')
    ).order_by(Auction.end_time.asc()).all()

    items = []
    total_bid_value = 0

    for auction, product, bid, category in active_auctions:
        product_image = product.images[0].url if product.images else None
        current_time = get_current_time_in_vietnam()
        time_remaining = auction.end_time - current_time if auction.status == 'ongoing' else None

        # Tính thời gian còn lại nếu phiên đấu giá đang diễn ra
        if time_remaining:
            days = time_remaining.days
            hours, remainder = divmod(time_remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_remaining_str = f"{days} ngày, {hours} giờ, {minutes} phút"
        else:
            time_remaining_str = "Phiên đấu giá đã kết thúc"

        highest_bid = db.session.query(db.func.max(Bid.amount)).filter(Bid.auction_id == auction.id).scalar() or 0

        # Kiểm tra trạng thái của phiên đấu giá cho người dùng
        status = {
            'is_winning': bid.amount >= highest_bid,
            'is_tied': bid.amount == highest_bid,
            'is_outbid': bid.amount < highest_bid
        }

        # Kiểm tra nếu cần thanh toán cho các phiên đấu giá đã thắng và chưa thanh toán
        transaction = Transaction.query.filter_by(auction_id=auction.id, buyer_id=user_id, status='pending').first()
        payment_required = transaction is not None

        # Kiểm tra xem tất cả giao dịch của phiên đấu giá đã hoàn thành hay chưa
        all_paid = Transaction.query.filter_by(auction_id=auction.id, buyer_id=user_id, status='completed').count() > 0

        items.append({
            'auction_id': auction.id,
            'product_name': product.name,
            'product_image': product_image,
            'current_price': auction.current_price,
            'my_bid': bid.amount,
            'end_time': auction.end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'time_remaining': time_remaining_str,
            'category': category.name if category else 'Không rõ',
            'status': status,
            'payment_required': payment_required,
            'auction_status': auction.status,
            'paid_status': all_paid
        })
        total_bid_value += bid.amount

    total_auctions = len(items)
    winning_auctions = sum(1 for item in items if item['status']['is_winning'])

    return render_template(
        'cart.html',
        items=items,
        total_bid_value=total_bid_value,
        total_auctions=total_auctions,
        winning_auctions=winning_auctions
    )

@api_bp.route('/pay_transaction/<int:auction_id>', methods=['POST'])
@jwt_required()
def pay_transaction(auction_id):
    user_id = get_jwt_identity()

    transaction = Transaction.query.filter_by(auction_id=auction_id, buyer_id=user_id, status='pending').first()

    if transaction:
        transaction.status = 'completed'
        db.session.commit()
        return jsonify({"success": True, "message": "Thanh toán thành công!", "bid_amount": transaction.amount})
    else:
        print("No pending transaction found for auction:", auction_id, "and user:", user_id)  # Debug
        return jsonify({"success": False, "message": "Không tìm thấy giao dịch cần thanh toán."})


@api_bp.route('/api/auction_updates', methods=['GET'])
@jwt_required()
def auction_updates():
    updates = []
    ongoing_auctions = Auction.query.filter(Auction.status == 'ongoing').all()
    current_time = get_current_time_in_vietnam()

    for auction in ongoing_auctions:
        time_remaining = auction.end_time - current_time
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_remaining_str = f"{days} ngày, {hours} giờ, {minutes} phút"

        updates.append({
            'auction_id': auction.id,
            'current_price': auction.current_price,
            'time_remaining': time_remaining_str,
            'status_text': 'Đang diễn ra' if auction.end_time > current_time else 'Kết thúc',
            'status_class': 'status-active' if auction.end_time > current_time else 'status-completed'
        })

    return jsonify(updates), 200


@api_bp.route('/admin', methods=['GET'])
@jwt_required()
def get_admin_stats():
    # Ensure the user is an admin
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    # Get current time in Vietnam
    now = get_current_time_in_vietnam()

    # Basic statistics
    total_users = User.query.count()
    total_auctions = Auction.query.count()
    total_bids = Bid.query.count()
    total_transactions = Transaction.query.filter_by(status='completed').count()

    # Calculate revenue (sum of completed transactions)
    revenue = db.session.query(func.sum(Transaction.amount))\
        .filter_by(status='completed').scalar() or 0

    # Active auctions
    active_auctions = Auction.query.filter(
        Auction.end_time > now,
        Auction.status == 'ongoing'
    ).count()

    # Get monthly sales data for the chart
    six_months_ago = now - timedelta(days=180)

    monthly_sales = db.session.query(
        func.DATE_FORMAT(Transaction.created_at, '%Y-%m-01').label('month'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.status == 'completed',
        Transaction.created_at >= six_months_ago
    ).group_by(
        func.DATE_FORMAT(Transaction.created_at, '%Y-%m-01')
    ).order_by(
        func.DATE_FORMAT(Transaction.created_at, '%Y-%m-01')
    ).all()

    # Format monthly sales data
    sales_data = [
        {
            'month': datetime.strptime(month, '%Y-%m-%d').strftime('%B %Y'),
            'amount': float(total)
        }
        for month, total in monthly_sales
    ]

    # Get top categories by auction count
    top_categories = db.session.query(
        Category.name,
        func.count(Auction.id).label('count')
    ).select_from(Category)\
    .join(Product, Product.category_id == Category.id)\
    .join(Auction, Auction.product_id == Product.id)\
    .group_by(Category.id, Category.name)\
    .order_by(func.count(Auction.id).desc())\
    .limit(5).all()

    # Get recent transactions
    recent_transactions_query = db.session.query(
        Transaction,
        User,
        Product
    ).select_from(Transaction)\
    .join(User, User.id == Transaction.buyer_id)\
    .join(Auction, Auction.id == Transaction.auction_id)\
    .join(Product, Product.id == Auction.product_id)\
    .filter(Transaction.status == 'completed')\
    .order_by(Transaction.created_at.desc())\
    .limit(5)

    recent_transactions = recent_transactions_query.all()

    latest_orders = [
        {
            'id': t.Transaction.id,
            'buyer': t.User.name,
            'product': t.Product.name,
            'amount': float(t.Transaction.amount),
            'date': t.Transaction.created_at.strftime('%Y-%m-%d %H:%M')
        }
        for t in recent_transactions
    ]

    # User activity metrics
    active_users_24h = User.query.filter(
        User.last_login >= (now - timedelta(hours=24))
    ).count()

    new_users_7d = User.query.filter(
        User.created_at >= (now - timedelta(days=7))
    ).count()

    # Prepare the data to pass to the template
    basic_stats = {
        'total_users': total_users,
        'total_auctions': total_auctions,
        'total_bids': total_bids,
        'total_transactions': total_transactions,
        'active_auctions': active_auctions,
        'total_revenue': float(revenue)
    }

    user_metrics = {
        'active_24h': active_users_24h,
        'new_7d': new_users_7d
    }

    return render_template(
        'admin/index.html',
        basic_stats=basic_stats,
        sales_data=sales_data,
        top_categories=top_categories,
        latest_orders=latest_orders,
        user_metrics=user_metrics
    )



@api_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def admin_users():
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.phone_number.ilike(f'%{search}%')
            )
        )

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users, search=search)
@api_bp.route('/admin/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_details(user_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    user = User.query.get_or_404(user_id)
    stats = get_user_statistics(user_id)
    user_data = format_user_data(user)
    user_data["stats"] = stats

    return jsonify(user_data)
@api_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user_id = get_jwt_identity()
    admin = get_admin_user(current_user_id)
    if not admin:
        return jsonify({"message": "Unauthorized"}), 403

    user = User.query.get_or_404(user_id)
    data = request.json

    if 'email' in data:
        existing_user = User.query.filter(User.email == data['email'], User.id != user_id).first()
        if existing_user:
            return jsonify({"message": "Email đã tồn tại"}), 400

    if user_id == current_user_id and data.get('role') != 'admin':
        return jsonify({"message": "Không thể thay đổi quyền admin của chính mình"}), 400

    for key in ['name', 'email', 'phone_number', 'role']:
        if key in data:
            setattr(user, key, data[key])

    db.session.commit()
    return jsonify({"message": "Cập nhật thành công"})
@api_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    current_user_id = get_jwt_identity()
    admin = get_admin_user(current_user_id)
    if not admin:
        return jsonify({"message": "Unauthorized"}), 403

    if user_id == current_user_id:
        return jsonify({"message": "Không thể xóa tài khoản của chính mình"}), 400

    try:
        delete_user_data(user_id)
    except SQLAlchemyError as e:
        return jsonify({"message": f"Lỗi khi xóa người dùng: {str(e)}"}), 500

    return jsonify({"message": "Xóa người dùng thành công"})
@api_bp.route('/admin/users/export', methods=['GET'])
@jwt_required()
def export_users():
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    users_data = export_all_users()
    return jsonify(users_data)
@api_bp.route('/admin/users', methods=['POST'])
@jwt_required()
def add_user():
    current_user_id = get_jwt_identity()
    admin = get_admin_user(current_user_id)
    if not admin:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Kiểm tra các trường bắt buộc
    required_fields = ['name', 'email', 'password', 'role']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"message": f"Thiếu trường bắt buộc: {field}"}), 400

    # Kiểm tra email đã tồn tại
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Email đã tồn tại"}), 400

    # Hash mật khẩu
    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(data['password'])

    # Tạo người dùng mới
    new_user = User(
        name=data['name'],
        email=data['email'],
        password=hashed_password,
        phone_number=data.get('phone_number'),
        role=data['role']
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "Người dùng mới đã được tạo thành công"})
@api_bp.route('/admin/auctions', methods=['GET'])
@jwt_required()
def admin_auctions():
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    # Lấy tham số tìm kiếm và phân trang
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Auction.query.join(Product).join(User)

    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                User.name.ilike(f'%{search}%')
            )
        )

    if status_filter:
        query = query.filter(Auction.status == status_filter)

    auctions = query.order_by(Auction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('admin/auctions.html', auctions=auctions, search=search, status_filter=status_filter)
@api_bp.route('/admin/auctions/<int:auction_id>/approve', methods=['POST'])
@jwt_required()
def approve_auction(auction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    auction = Auction.query.get_or_404(auction_id)

    if auction.status != 'pending':
        return jsonify({"message": "Phiên đấu giá này không ở trạng thái chờ phê duyệt"}), 400

    auction.status = 'ongoing'
    db.session.commit()

    return jsonify({"message": "Phiên đấu giá đã được phê duyệt và chuyển sang trạng thái đang diễn ra"})

@api_bp.route('/admin/auctions/<int:auction_id>', methods=['DELETE'])
@jwt_required()
def delete_auction(auction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    auction = Auction.query.get_or_404(auction_id)
    # Thực hiện kiểm tra và xóa các liên kết liên quan nếu cần
    db.session.delete(auction)
    db.session.commit()

    return jsonify({"message": "Phiên đấu giá đã được xóa thành công"})
@api_bp.route('/admin/auctions/<int:auction_id>', methods=['GET'])
@jwt_required()
def view_auction(auction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    auction = Auction.query.get_or_404(auction_id)
    auction_data = {
        "id": auction.id,
        "product": auction.product.name,
        "seller": auction.seller.name,
        "start_price": auction.start_price,
        "current_price": auction.current_price,
        "created_at": auction.created_at.strftime("%Y-%m-%d %H:%M:%S") if auction.created_at else "N/A",
        "end_time": auction.end_time.strftime("%Y-%m-%d %H:%M:%S") if auction.end_time else "N/A",
        "status": auction.status,
        # Định dạng `end_time` cho input `datetime-local`
        "end_time_local": auction.end_time.strftime("%Y-%m-%dT%H:%M") if auction.end_time else "",
        # Thêm các thông tin khác nếu cần
    }
    return jsonify(auction_data)

@api_bp.route('/admin/auctions/<int:auction_id>/edit', methods=['POST'])
@jwt_required()
def edit_auction(auction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    auction = Auction.query.get_or_404(auction_id)
    data = request.json

    if 'start_price' in data:
        auction.start_price = data['start_price']
    if 'end_time' in data:
        try:
            auction.end_time = datetime.strptime(data['end_time'], '%Y-%m-%dT%H:%M')
        except ValueError:
            return jsonify({"message": "Định dạng thời gian kết thúc không hợp lệ"}), 400
    # Cập nhật các trường khác nếu cần

    db.session.commit()
    return jsonify({"message": "Cập nhật phiên đấu giá thành công"})



@api_bp.route('/admin/transactions', methods=['GET'])
@jwt_required()
def admin_transactions():
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    # Lấy tham số tìm kiếm và phân trang
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Transaction.query.join(Auction).join(User, Transaction.buyer)

    if search:
        query = query.filter(
            db.or_(
                Auction.product.has(Product.name.ilike(f'%{search}%')),
                User.name.ilike(f'%{search}%')
            )
        )

    if status_filter:
        query = query.filter(Transaction.status == status_filter)

    transactions = query.order_by(Transaction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('admin/transactions.html', transactions=transactions, search=search, status_filter=status_filter)
@api_bp.route('/admin/transactions/<int:transaction_id>', methods=['GET'])
@jwt_required()
def view_transaction(transaction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    transaction = Transaction.query.get_or_404(transaction_id)
    transaction_data = {
        "id": transaction.id,
        "auction_id": transaction.auction_id,
        "product_name": transaction.auction.product.name,
        "buyer_name": transaction.buyer.name,
        "amount": transaction.amount,
        "status": transaction.status,
        "created_at": transaction.created_at.strftime("%Y-%m-%d %H:%M:%S") if transaction.created_at else "N/A",
        "updated_at": transaction.updated_at.strftime("%Y-%m-%d %H:%M:%S") if transaction.updated_at else "N/A",
        # Thêm các thông tin khác nếu cần
    }
    return jsonify(transaction_data)
@api_bp.route('/admin/transactions/<int:transaction_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_transaction(transaction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    transaction = Transaction.query.get_or_404(transaction_id)

    if transaction.status != 'pending':
        return jsonify({"message": "Giao dịch không ở trạng thái chờ xác nhận"}), 400

    transaction.status = 'confirmed'
    transaction.updated_at = get_current_time_in_vietnam()
    db.session.commit()

    return jsonify({"message": "Giao dịch đã được xác nhận thành công"})
@api_bp.route('/admin/transactions/<int:transaction_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_transaction(transaction_id):
    current_user_id = get_jwt_identity()
    if not get_admin_user(current_user_id):
        return jsonify({"message": "Unauthorized"}), 403

    transaction = Transaction.query.get_or_404(transaction_id)

    if transaction.status != 'pending':
        return jsonify({"message": "Giao dịch không ở trạng thái chờ xác nhận"}), 400

    transaction.status = 'canceled'
    transaction.updated_at = get_current_time_in_vietnam()
    db.session.commit()

    return jsonify({"message": "Giao dịch đã được hủy thành công"})

# Route để hiển thị trang thông báo
@api_bp.route('/notifications')
def notifications_page():
    return render_template('notifications.html')

# API để lấy thông báo
@api_bp.route('/api/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = get_jwt_identity()
    notifications = Notification.query.filter_by(user_id=user_id)\
        .order_by(Notification.created_at.desc())\
        .all()
    
    return jsonify([{
        'id': n.id,
        'message': n.message,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'auction_id': n.auction_id
    } for n in notifications]), 200

# API để đánh dấu thông báo đã đọc 
@api_bp.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    user_id = get_jwt_identity()
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=user_id
    ).first_or_404()
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Thông báo đã được đánh dấu là đã đọc'}), 200

# API để xóa thông báo
@api_bp.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@jwt_required()
def delete_notification(notification_id):
    user_id = get_jwt_identity()
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=user_id
    ).first_or_404()
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({'message': 'Thông báo đã được xóa'}), 200

# API để đánh dấu tất cả thông báo là đã đọc
@api_bp.route('/api/notifications/mark-all-read', methods=['PUT'])
@jwt_required()
def mark_all_notifications_read():
    user_id = get_jwt_identity()
    Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).update({Notification.is_read: True})
    
    db.session.commit()
    return jsonify({'message': 'Tất cả thông báo đã được đánh dấu là đã đọc'}), 200

@api_bp.route('/profile')
@jwt_required()
def profile_page():
    user_id = get_jwt_identity()
    current_user = User.query.get_or_404(user_id)
    return render_template('profile.html', current_user=current_user)

@api_bp.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    
    return jsonify({
        'email': user.email,
        'name': user.name,  # Sử dụng trường `name` thay vì `first_name` và `last_name`
        'phone': user.phone_number,
        'address': user.address
    }), 200
@api_bp.route('/api/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    
    # Validate current password
    current_password = request.form.get('current_password')
    if not check_password(current_password, user.password):
        return jsonify({'success': False, 'message': 'Mật khẩu không chính xác'}), 400
    
    # Update profile fields
    user.name = request.form.get('name', user.name)  # Cập nhật trường `name`
    user.phone_number = request.form.get('phone', user.phone_number)
    user.address = request.form.get('address', user.address)
    
    # Update password if new password provided
    new_password = request.form.get('new_password')
    if new_password:
        user.password = hash_password(new_password)
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': 'Cập nhật thông tin thành công',
    }), 200
