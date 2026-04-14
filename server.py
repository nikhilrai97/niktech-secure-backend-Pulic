from fastapi import FastAPI, HTTPException
from database import users_collection, attendance_collection
from models import user_model, attendance_model
from auth import hash_password, verify_password, create_token
from bson import ObjectId
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Connection
client = MongoClient("mongodb://localhost:27017")
db = client["attendance_db"]
attendance_collection = db["attendance"]

# -------------------------
# REGISTER USER
# -------------------------
@app.post("/register")
def register(user: dict):
    user["role"] ="user"
    if users_collection.find_one({"email": user["email"]}):
        raise HTTPException(status_code=400, detail="Email already exists")

    user["password"] = hash_password(user["password"])
    users_collection.insert_one(user)
    return {"message": "User registered"}

# -------------------------
# LOGIN
# -------------------------
@app.post("/login")
def login(data: dict):
    user = users_collection.find_one({"email": data["email"]})

    if not user or not verify_password(data["password"], user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"id": str(user["_id"])})
    return {"token": token, "user": user_model(user)}

# -------------------------
# GET USERS (ADMIN)
# -------------------------
@app.get("/users")
def get_users():
    users = users_collection.find()
    return [user_model(u) for u in users]

# -------------------------
# CHECK IN (ESP32 / APP)
# -------------------------
@app.post("/attendance/checkin")
def check_in(data: dict):
    fingerprint_id = data.get("fingerprint_id")

    user = users_collection.find_one({"fingerprint_id": fingerprint_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    record = {
        "user_id": str(user["_id"]),
        "check_in": datetime.now(),
        "status": "present"
    }

    attendance_collection.insert_one(record)
    return {"message": "Checked in"}

# -------------------------
# CHECK OUT
# -------------------------
@app.post("/attendance/checkout")
def check_out(data: dict):
    record = attendance_collection.find_one({"_id": ObjectId(data["attendance_id"])})

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    attendance_collection.update_one(
        {"_id": record["_id"]},
        {"$set": {"check_out": datetime.now()}}
    )

    return {"message": "Checked out"}

# -------------------------
# TODAY ATTENDANCE
# -------------------------
@app.get("/attendance/today")
def today_attendance():
    today = datetime.now().date()

    records = attendance_collection.find()

    result = []
    for r in records:
        if r["check_in"].date() == today:
            result.append(attendance_model(r))

    return result

# -------------------------
# TODAY STATS
# -------------------------
@app.get("/stats/today")
def today_stats():
    today = datetime.now().date()
    records = attendance_collection.find()

    present = 0
    for r in records:
        if r["check_in"].date() == today:
            present += 1

    total = users_collection.count_documents({})

    return {
        "present_today": present,
        "absent_today": total - present,
        "total_employees": total
        }
@app.get("/attendance/{user_id}")
def get_user_attendance(user_id: str):

    records = attendance_collection.find({"user_id": user_id})

    result = []
    for r in records:
        result.append(attendance_model(r))

    return result
@app.delete("/users/{user_id}")
def delete_user(user_id: str):
 result = users_collection.delete_one({"_id":ObjectId(user_id)})
 if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
 return {"message": "User deleted"}
 
 
 
@app.put("/profile/{email}")
def update_profile(email: str, data:dict):
    users_collection.update_one(
        {"email": email},
        {"$set": {"name": data.get("name"),
        }})
    return {"message": "Profile updated"}




@app.get("/users/{id}")
def get_user(id: str):
    user = users_collection.find_one({"_id": ObjectId(id)})

    if user:
        user["_id"] = str(user["_id"]) # convert ObjectId to string
        return user

    return {"error": "User not found"}

    from pydantic import BaseModel
from bson import ObjectId

class UserUpdate(BaseModel):
    name: str
    email: str
    role: str
    Phone: str

    
    
@app.put("/users/{id}")
def update_user(id: str, user: UserUpdate):
    data = user.dict()

    result = users_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": data}
    )

    return {"message": "User updated"}

@app.post("/login")
def login(data: dict):
    user = users_collection.find_one({"email": data["email"]})

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email")

    user["_id"] = str(user["_id"])

    return {
        "user": user,
        "token": "dummy"
    }

    from datetime import datetime

@app.get("/attendance/user/{user_id}")
def get_user_attendance(user_id: str):
    records = list(attendance_collection.find({"user_id": user_id}))

    for r in records:
        r["_id"] = str(r["_id"])
        r["check_in"] = r["check_in"].strftime("%Y-%m-%d %H:%M")

    return records

# =========================
# 📊 WEEKLY ATTENDANCE
# =========================
@app.get("/attendance/weekly/{user_id}")
def weekly_attendance(user_id: str):
    
    today = datetime.now()
    last_7_days = today - timedelta(days=7)

    records = list(attendance_collection.find({
        "user_id": user_id,
        "check_in": {"$gte": last_7_days}
    }))

    data = []

    for r in records:
        if r.get("check_in") and r.get("check_out"):
            hours = (r["check_out"] - r["check_in"]).total_seconds() / 3600
        else:
            hours = 0

        data.append({
            "date": r["check_in"].strftime("%d"),
            "hours": round(hours, 2)
        })

    return data


# =========================
# 📅 MONTHLY ATTENDANCE
# =========================
@app.get("/attendance/monthly/{user_id}")
def monthly_attendance(user_id: str):
    
    today = datetime.now()
    last_30_days = today - timedelta(days=30)

    records = list(attendance_collection.find({
        "user_id": user_id,
        "check_in": {"$gte": last_30_days}
    }))

    data = []

    for r in records:
        if r.get("check_in") and r.get("check_out"):
            hours = (r["check_out"] - r["check_in"]).total_seconds() / 3600
        else:
            hours = 0

        data.append({
            "day": r["check_in"].strftime("%d"),
            "hours": round(hours, 2)
        })

    return data


# =========================
# 📌 STATS (Present/Absent)
# =========================
@app.get("/attendance/stats/{user_id}")
def attendance_stats(user_id: str):

    records = list(attendance_collection.find({
        "user_id": user_id
    }))

    present = 0
    absent = 0

    for r in records:
        if r.get("status") == "present":
            present += 1
        else:
            absent += 1

    return {
        "present": present,
        "absent": absent
    }

@app.post("/attendance")
def mark_attendance(data: dict):
    fingerprint_id = data.get("fingerprint_id")

    user = users_collection.find_one({"fingerprint_id": fingerprint_id})

    if not user:
        return {"error": "User not found"}

    attendance = {
        "user_id": str(user["_id"]),
        "check_in": datetime.now(),
        "status": "present"
    }

    attendance_collection.insert_one(attendance)

    return {"message": "Attendance marked"}


from pymongo import MongoClient
import os

MONGO_URL = os.getenv("MONGO_URL")

client = MongoClient(MONGO_URL)
db = client["niktech"]
collection = db["attendance"]

@app.get("/test")
def test_insert():
    collection.insert_one({
        "name": "Nikhil",
        "status": "Present"
    })
    return {"message": "Data inserted"}
