from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

users_collection = db["users"]
attendance_collection = db["attendance"]
settings_collection = db["settings"]
leave_collection = db["leaves"]
holiday_collection = db["holidays"]
