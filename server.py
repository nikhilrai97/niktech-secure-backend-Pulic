from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_token, hash_password, verify_password
from database import attendance_collection, users_collection
from models import attendance_model, user_model

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserUpdate(BaseModel):
    name: str
    email: str
    role: str
    Phone: str


@app.get("/")
def home():
    return {"status": "server running"}


@app.post("/register")
def register(user: dict):
    if users_collection.find_one({"email": user.get("email")}):
        raise HTTPException(status_code=400, detail="Email already exists")

    user["role"] = "user"
    user["password"] = hash_password(user.get("password", ""))

    result = users_collection.insert_one(user)

    return {
        "message": "User registered successfully",
        "id": str(result.inserted_id)
    }


@app.post("/login")
def login(data: dict):
    user = users_collection.find_one({"email": data.get("email")})

    if not user or not verify_password(data.get("password", ""), user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"id": str(user["_id"])})

    return {
        "token": token,
        "user": user_model(user)
    }


@app.get("/users")
def get_users():
    users = []

    for user in users_collection.find():
        user["_id"] = str(user["_id"])
        user.pop("password", None)
        users.append(user)

    return users


@app.get("/users/{id}")
def get_user(id: str):
    user = users_collection.find_one({"_id": ObjectId(id)})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user["_id"] = str(user["_id"])
    user.pop("password", None)

    return user


@app.put("/users/{id}")
def update_user(id: str, user: UserUpdate):
    result = users_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": user.dict()}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated"}


@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    result = users_collection.delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted"}


@app.put("/profile/{email}")
def update_profile(email: str, data: dict):
    result = users_collection.update_one(
        {"email": email},
        {"$set": {"name": data.get("name")}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Profile updated"}


@app.put("/add-user/{user_id}")
def add_user(user_id: str, data: dict):
    fingerprint_id = data.get("fingerprint_id")

    if fingerprint_id is None:
        raise HTTPException(status_code=400, detail="fingerprint_id required")

    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "fingerprint_id": int(fingerprint_id),
                "enroll": True
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "fingerprint linked"}


@app.get("/check-enroll")
def check_enroll():
    user = users_collection.find_one({"enroll": True})

    if not user:
        return {"status": "none"}

    return {
        "status": "found",
        "id": str(user["_id"]),
        "fingerprint_id": int(user["fingerprint_id"]),
        "name": user.get("name", "")
    }


@app.post("/enroll-done")
def enroll_done(data: dict):
    user_id = data.get("id")

    if not user_id:
        return {"status": "error", "message": "id required"}

    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"enroll": False}}
    )

    if result.matched_count == 0:
        return {"status": "error", "message": "User not found"}

    return {"status": "done"}


@app.post("/attendance")
def attendance(data: dict):
    try:
        fingerprint_id = data.get("fingerprint_id")

        if fingerprint_id is None:
            return {
                "name": "ERROR",
                "action": "error",
                "message": "fingerprint_id required"
            }

        fingerprint_id = int(fingerprint_id)

        user = users_collection.find_one({
            "$or": [
                {"fingerprint_id": fingerprint_id},
                {"fingerprint_id": str(fingerprint_id)}
            ]
        })

        if not user:
            return {
                "name": "ERROR",
                "action": "error",
                "message": "User not found"
            }

        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
        today_end = datetime(now.year, now.month, now.day, 23, 59, 59)

        today_record = attendance_collection.find_one(
            {
                "user_id": str(user["_id"]),
                "check_in": {
                    "$gte": today_start,
                    "$lte": today_end
                }
            },
            sort=[("check_in", -1)]
        )

        if not today_record:
            attendance_collection.insert_one({
                "user_id": str(user["_id"]),
                "fingerprint_id": fingerprint_id,
                "name": user.get("name", ""),
                "check_in": now,
                "status": "present"
            })

            return {
                "name": user.get("name", "User"),
                "action": "in_punch",
                "message": "In Punch Done"
            }

        if today_record.get("check_out"):
            return {
                "name": user.get("name", "User"),
                "action": "already_done",
                "message": "Already Done Today"
            }

        check_in_time = today_record.get("check_in")
        diff_minutes = (now - check_in_time).total_seconds() / 60

        if diff_minutes < 60:
            return {
                "name": user.get("name", "User"),
                "action": "duplicate",
                "message": "Duplicate Punch"
            }

        attendance_collection.update_one(
            {"_id": today_record["_id"]},
            {
                "$set": {
                    "check_out": now,
                    "status": "completed"
                }
            }
        )

        return {
            "name": user.get("name", "User"),
            "action": "out_punch",
            "message": "Out Punch Done"
        }

    except Exception as e:
        return {
            "name": "ERROR",
            "action": "error",
            "message": str(e)
        }


@app.post("/attendance/checkin")
def check_in(data: dict):
    fingerprint_id = data.get("fingerprint_id")

    user = users_collection.find_one({
        "$or": [
            {"fingerprint_id": fingerprint_id},
            {"fingerprint_id": str(fingerprint_id)}
        ]
    })

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    record = {
        "user_id": str(user["_id"]),
        "fingerprint_id": fingerprint_id,
        "name": user.get("name", ""),
        "check_in": datetime.now(),
        "status": "present"
    }

    attendance_collection.insert_one(record)

    return {"message": "Checked in"}


@app.post("/attendance/checkout")
def check_out(data: dict):
    attendance_id = data.get("attendance_id")

    if not attendance_id:
        raise HTTPException(status_code=400, detail="attendance_id required")

    record = attendance_collection.find_one({"_id": ObjectId(attendance_id)})

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    attendance_collection.update_one(
        {"_id": record["_id"]},
        {
            "$set": {
                "check_out": datetime.now(),
                "status": "completed"
            }
        }
    )

    return {"message": "Checked out"}


@app.get("/attendance/today")
def today_attendance():
    today = datetime.now().date()
    result = []

    for record in attendance_collection.find():
        check_in_time = record.get("check_in")

        if check_in_time and check_in_time.date() == today:
            result.append(attendance_model(record))

    return result


@app.get("/stats/today")
def today_stats():
    today = datetime.now().date()
    present = 0

    for record in attendance_collection.find():
        check_in_time = record.get("check_in")

        if check_in_time and check_in_time.date() == today:
            present += 1

    total = users_collection.count_documents({})

    return {
        "present_today": present,
        "absent_today": total - present,
        "total_employees": total
    }


@app.get("/attendance/user/{user_id}")
def get_user_attendance_records(user_id: str):
    records = list(attendance_collection.find({"user_id": user_id}))
    result = []

    for record in records:
        record["_id"] = str(record["_id"])

        if record.get("check_in"):
            record["check_in"] = record["check_in"].strftime("%Y-%m-%d %H:%M")

        if record.get("check_out"):
            record["check_out"] = record["check_out"].strftime("%Y-%m-%d %H:%M")

        result.append(record)

    return result


@app.get("/attendance/weekly/{user_id}")
def weekly_attendance(user_id: str):
    today = datetime.now()
    last_7_days = today - timedelta(days=7)

    records = list(attendance_collection.find({
        "user_id": user_id,
        "check_in": {"$gte": last_7_days}
    }))

    data = []

    for record in records:
        check_in_time = record.get("check_in")
        check_out_time = record.get("check_out")

        if check_in_time and check_out_time:
            hours = (check_out_time - check_in_time).total_seconds() / 3600
        else:
            hours = 0

        data.append({
            "date": check_in_time.strftime("%d") if check_in_time else "",
            "hours": round(hours, 2)
        })

    return data


@app.get("/attendance/monthly/{user_id}")
def monthly_attendance(user_id: str):
    today = datetime.now()
    last_30_days = today - timedelta(days=30)

    records = list(attendance_collection.find({
        "user_id": user_id,
        "check_in": {"$gte": last_30_days}
    }))

    data = []

    for record in records:
        check_in_time = record.get("check_in")
        check_out_time = record.get("check_out")

        if check_in_time and check_out_time:
            hours = (check_out_time - check_in_time).total_seconds() / 3600
        else:
            hours = 0

        data.append({
            "day": check_in_time.strftime("%d") if check_in_time else "",
            "hours": round(hours, 2)
        })

    return data


@app.get("/attendance/stats/{user_id}")
def attendance_stats(user_id: str):
    records = list(attendance_collection.find({"user_id": user_id}))

    present = 0
    absent = 0

    for record in records:
        if record.get("status") == "present":
            present += 1
        else:
            absent += 1

    return {
        "present": present,
        "absent": absent
    }


@app.get("/attendance/{user_id}")
def get_attendance_by_user_id(user_id: str):
    records = attendance_collection.find({"user_id": user_id})
    result = []

    for record in records:
        result.append(attendance_model(record))

    return result
