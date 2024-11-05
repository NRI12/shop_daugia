from app import db, create_app
from app.models import Auction, Product, Notification, Bid
from datetime import datetime
import pytz

def get_current_time_in_vietnam():
    """Lấy thời gian hiện tại theo múi giờ Việt Nam."""
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(vn_tz).replace(tzinfo=None)

def close_expired_auctions():
    """Task để đóng các phiên đấu giá đã hết hạn."""
    
    app = create_app()  # Khởi tạo app để dùng app_context
    with app.app_context():
        current_time = get_current_time_in_vietnam()

        # Lấy các phiên đấu giá đã hết hạn và đang trong trạng thái 'ongoing'
        expired_auctions = Auction.query.filter(
            Auction.end_time < current_time, 
            Auction.status == 'ongoing'
        ).all()

        for auction in expired_auctions:
            winner_bid = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc()).first()

            if not winner_bid:
                # Không có giá thầu, đặt trạng thái là 'expired'
                auction.status = 'expired'
                product = Product.query.get(auction.product_id)
                notification = Notification(
                    message=f"No bids were placed for '{product.name}'. The auction has expired.",
                    user_id=auction.seller_id,
                    auction_id=auction.id
                )
                db.session.add(notification)
            else:
                # Có giá thầu, đặt trạng thái là 'completed'
                auction.status = 'completed'

        db.session.commit()
        print(f"Closed {len(expired_auctions)} expired auctions.")
