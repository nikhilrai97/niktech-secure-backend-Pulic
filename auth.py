import jwt
import datetime
import os
import bcrypt
from dotenv import load_dotenv

load_dotenv()

SECRET = os.getenv("SECRET_KEY")

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def create_token(data):
    payload = {
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1),
        "data": data
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")