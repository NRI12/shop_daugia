from datetime import datetime
from app import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password = db.Column(db.String(128))
    phone_number = db.Column(db.String(15))
    role = db.Column(db.String(10))  # role for admin/user
    
    auctions = db.relationship('Auction', backref='seller', lazy=True)
    bids = db.relationship('Bid', backref='bidder', lazy=True)
    transactions = db.relationship('Transaction', backref='buyer', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.name}>'

class Auction(db.Model):
    __tablename__ = 'auctions'

    id = db.Column(db.Integer, primary_key=True)
    start_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, default=0)
    end_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='ongoing')  # pending, completed

    # Quan hệ với người bán và sản phẩm
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), unique=True, nullable=False)

    # Quan hệ với các giá thầu và giao dịch
    bids = db.relationship('Bid', backref='auction', lazy=True)
    transactions = db.relationship('Transaction', backref='auction', lazy=True)

    def __repr__(self):
        return f'<Auction {self.id}>'


class Bid(db.Model):
    __tablename__ = 'bids'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Bid {self.amount}>'

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(64))
    image_url = db.Column(db.String(256))
    create_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Khóa ngoại liên kết với Category
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    auction = db.relationship('Auction', backref='product', uselist=False)

    def __repr__(self):
        return f'<Product {self.name}>'


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)

    # Quan hệ 1-nhiều với Product
    products = db.relationship('Product', backref='product_category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'



class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.id'))
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    create_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Transaction {self.id}>'

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(256))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.message}>'