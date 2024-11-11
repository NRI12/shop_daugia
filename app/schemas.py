from marshmallow import fields, validate, Schema, ValidationError

class UserSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=64))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))
    phone_number = fields.String(validate=validate.Regexp(r'^\+?\d{10,15}$'))

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)

class AuctionSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=128))
    description = fields.String()
    start_price = fields.Float(required=True)
    end_time = fields.DateTime(required=True)

class BidSchema(Schema):
    auction_id = fields.Integer(required=True)
    amount = fields.Float(required=True, validate=lambda x: x > 0)
