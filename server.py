from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_token, hash_password, verify_password
from database import (
    attendance_collection,
    holiday_collection,
    leave_collection,
    settings_collection,
    users_collection,
)
from models import attendance_model, user_model

IST = ZoneInfo("Asia/Kolkata")


def now_ist():
    return datetime.now(IST).replace(tzinfo=None)


def object_id(id_value: str):
    try:
        return ObjectId(id_value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


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
    role: str = "user"
    phone: str = ""
    department: str = ""


@app.get("/")
def home():
    return {"status": "server running", "time": now_ist()}


@app.post("/register")
def register(user: dict):
    if users_collection.find_one({"email": user.get("email")}):
        raise HTTPException(status_code=400, detail="Email already exists")

    user["role"] = user.get("role", "user")
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
        user["id"] = str(user["_id"])
        user["_id"] = str(user["_id"])
        user.pop("password", None)
        users.append(user)

    return users


@app.get("/users/{id}")
def get_user(id: str):
    user = users_collection.find_one({"_id": object_id(id)})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user["id"] = str(user["_id"])
    user["_id"] = str(user["_id"])
    user.pop("password", None)

    return user


@app.put("/users/{id}")
def update_user(id: str, user: UserUpdate):
    result = users_collection.update_one(
        {"_id": object_id(id)},
        {"$set": user.dict()}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated"}


@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    result = users_collection.delete_one({"_id": object_id(user_id)})

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
        {"_id": object_id(user_id)},
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
        {"_id": object_id(user_id)},
        {"$set": {"enroll": False}}
    )

    if result.matched_count == 0:
        return {"status": "error", "message": "User not found"}

    return {"status": "done"}


def get_attendance_settings():
    settings = settings_collection.find_one({"type": "attendance"})

    if not settings:
        return {
            "duplicate_punch_minutes": 60,
            "report_days": 30,
            "late_after": "10:00",
            "working_hours": 8
        }

    return {
        "duplicate_punch_minutes": int(settings.get("duplicate_punch_minutes", 60)),
        "report_days": int(settings.get("report_days", 30)),
        "late_after": settings.get("late_after", "10:00"),
        "working_hours": int(settings.get("working_hours", 8))
    }


def date_range(start_date, end_date):
    days = []
    current = start_date

    while current <= end_date:
        days.append(current)
        current = current + timedelta(days=1)

    return days


def get_holiday_dates(start_date, end_date):
    holidays = list(holiday_collection.find())
    holiday_dates = set()

    for holiday in holidays:
        try:
            holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()

            if start_date <= holiday_date <= end_date:
                holiday_dates.add(holiday_date)
        except Exception:
            pass

    return holiday_dates


def get_approved_leave_dates(user_id, start_date, end_date):
    leaves = list(leave_collection.find({
        "user_id": user_id,
        "status": "approved"
    }))

    leave_dates = set()

    for leave in leaves:
        try:
            start = datetime.strptime(leave["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(leave["end_date"], "%Y-%m-%d").date()

            for day in date_range(start, end):
                if start_date <= day <= end_date:
                    leave_dates.add(day)
        except Exception:
            pass

    return leave_dates


@app.get("/settings/attendance")
def get_settings():
    return get_attendance_settings()


@app.put("/settings/attendance")
def update_settings(data: dict):
    settings = {
        "type": "attendance",
        "duplicate_punch_minutes": int(data.get("duplicate_punch_minutes", 60)),
        "report_days": int(data.get("report_days", 30)),
        "late_after": data.get("late_after", "10:00"),
        "working_hours": int(data.get("working_hours", 8))
    }

    settings_collection.update_one(
        {"type": "attendance"},
        {"$set": settings},
        upsert=True
    )

    return {
        "message": "Attendance settings updated",
        "settings": settings
    }


@app.post("/leave/apply")
def apply_leave(data: dict):
    user_id = data.get("user_id")
    reason = data.get("reason")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not user_id or not reason or not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Missing fields")

    user = users_collection.find_one({"_id": object_id(user_id)})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = leave_collection.insert_one({
        "user_id": user_id,
        "name": user.get("name", ""),
        "reason": reason,
        "start_date": start_date,
        "end_date": end_date,
        "status": "pending",
        "applied_at": now_ist()
    })

    return {
        "message": "Leave applied successfully",
        "leave_id": str(result.inserted_id)
    }


@app.get("/leave/my/{user_id}")
def my_leaves(user_id: str):
    leaves = list(leave_collection.find({"user_id": user_id}).sort("applied_at", -1))

    for leave in leaves:
        leave["id"] = str(leave["_id"])
        leave["_id"] = str(leave["_id"])

    return leaves


@app.get("/leave/all")
def all_leaves():
    leaves = list(leave_collection.find().sort("applied_at", -1))

    for leave in leaves:
        leave["id"] = str(leave["_id"])
        leave["_id"] = str(leave["_id"])

    return leaves


@app.put("/leave/status/{leave_id}")
def update_leave_status(leave_id: str, data: dict):
    status = data.get("status")

    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = leave_collection.update_one(
        {"_id": object_id(leave_id)},
        {"$set": {"status": status, "updated_at": now_ist()}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Leave not found")

    return {"message": f"Leave {status}"}


@app.post("/holiday/add")
def add_holiday(data: dict):
    name = data.get("name")
    date = data.get("date")

    if not name or not date:
        raise HTTPException(status_code=400, detail="name and date required")

    if holiday_collection.find_one({"date": date}):
        raise HTTPException(status_code=400, detail="Holiday already exists")

    result = holiday_collection.insert_one({
        "name": name,
        "date": date,
        "created_at": now_ist()
    })

    return {
        "message": "Holiday added",
        "holiday_id": str(result.inserted_id)
    }


@app.get("/holiday/all")
def get_holidays():
    holidays = list(holiday_collection.find().sort("date", 1))

    for holiday in holidays:
        holiday["id"] = str(holiday["_id"])
        holiday["_id"] = str(holiday["_id"])

    return holidays


@app.delete("/holiday/{holiday_id}")
def delete_holiday(holiday_id: str):
    result = holiday_collection.delete_one({"_id": object_id(holiday_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Holiday not found")

    return {"message": "Holiday deleted"}


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

        settings = get_attendance_settings()
        duplicate_minutes = settings["duplicate_punch_minutes"]

        now = now_ist()
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
                "message": "In Punch Done",
                "time": now
            }

        if today_record.get("check_out"):
            return {
                "name": user.get("name", "User"),
                "action": "already_done",
                "message": "Already Done Today",
                "time": now
            }

        check_in_time = today_record.get("check_in")
        diff_minutes = (now - check_in_time).total_seconds() / 60

        if diff_minutes < duplicate_minutes:
            return {
                "name": user.get("name", "User"),
                "action": "duplicate",
                "message": "Duplicate Punch",
                "time": now
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
            "message": "Out Punch Done",
            "time": now
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
        "check_in": now_ist(),
        "status": "present"
    }

    attendance_collection.insert_one(record)

    return {"message": "Checked in"}


@app.post("/attendance/checkout")
def check_out(data: dict):
    attendance_id = data.get("attendance_id")

    if not attendance_id:
        raise HTTPException(status_code=400, detail="attendance_id required")

    record = attendance_collection.find_one({"_id": object_id(attendance_id)})

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    attendance_collection.update_one(
        {"_id": record["_id"]},
        {
            "$set": {
                "check_out": now_ist(),
                "status": "completed"
            }
        }
    )

    return {"message": "Checked out"}


@app.get("/attendance/calendar/{user_id}")
def attendance_calendar(user_id: str, days: int = 30):
    try:
        today = now_ist().date()
        start_date = today - timedelta(days=days - 1)

        holiday_dates = get_holiday_dates(start_date, today)
        leave_dates = get_approved_leave_dates(user_id, start_date, today)

        start_day = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
        end_day = datetime(today.year, today.month, today.day, 23, 59, 59)

        records = list(attendance_collection.find({
            "user_id": user_id,
            "check_in": {"$gte": start_day, "$lte": end_day}
        }).sort("check_in", -1))

        record_map = {}

        for record in records:
            check_in = record.get("check_in")

            if not check_in:
                continue

            key = check_in.strftime("%Y-%m-%d")
            existing = record_map.get(key)

            if not existing:
                record_map[key] = record
                continue

            if record.get("check_out") and not existing.get("check_out"):
                record_map[key] = record

        result = []

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            key = current_date.strftime("%Y-%m-%d")
            record = record_map.get(key)

            if current_date in holiday_dates:
                result.append({
                    "id": key,
                    "date": key,
                    "check_in": None,
                    "check_out": None,
                    "status": "holiday",
                    "present": False,
                    "message": "Holiday"
                })
                continue

            if current_date in leave_dates:
                result.append({
                    "id": key,
                    "date": key,
                    "check_in": None,
                    "check_out": None,
                    "status": "leave",
                    "present": False,
                    "message": "Approved Leave"
                })
                continue

            if not record:
                result.append({
                    "id": key,
                    "date": key,
                    "check_in": None,
                    "check_out": None,
                    "status": "absent",
                    "present": False,
                    "message": "No punch"
                })
                continue

            check_in = record.get("check_in")
            check_out = record.get("check_out")

            if check_in and check_out:
                status = "completed"
                present = True
                message = "Present"
            else:
                status = "absent"
                present = False
                message = "Out punch missing"

            result.append({
                "id": str(record.get("_id")),
                "date": key,
                "check_in": check_in,
                "check_out": check_out,
                "status": status,
                "present": present,
                "message": message
            })

        return result[::-1]

    except Exception as e:
        return {"error": str(e)}


@app.get("/attendance/today")
def today_attendance():
    today = now_ist().date()
    result = []

    for record in attendance_collection.find():
        check_in_time = record.get("check_in")

        if check_in_time and check_in_time.date() == today:
            result.append(attendance_model(record))

    return result


@app.get("/stats/today")
def today_stats():
    today = now_ist().date()

    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)

    holiday_dates = get_holiday_dates(today, today)
    total = users_collection.count_documents({})

    if today in holiday_dates:
        return {
            "present_today": 0,
            "absent_today": 0,
            "leave_today": 0,
            "total_employees": total,
            "holiday_today": True
        }

    present_users = set()

    records = attendance_collection.find({
        "check_in": {"$gte": today_start, "$lte": today_end},
        "check_out": {"$ne": None}
    })

    for record in records:
        present_users.add(record.get("user_id"))

    approved_leave_users = set()
    users = list(users_collection.find())

    for user in users:
        user_id = str(user["_id"])
        leave_dates = get_approved_leave_dates(user_id, today, today)

        if today in leave_dates:
            approved_leave_users.add(user_id)

    present = len(present_users)
    leave_count = len(approved_leave_users)
    absent = total - present - leave_count

    if absent < 0:
        absent = 0

    return {
        "present_today": present,
        "absent_today": absent,
        "leave_today": leave_count,
        "total_employees": total,
        "holiday_today": False
    }


@app.get("/reports/attendance-summary")
def attendance_summary(days: int = 30):
    try:
        settings = get_attendance_settings()
        report_days = int(days or settings["report_days"])

        today = now_ist().date()
        start_date = today - timedelta(days=report_days - 1)

        holiday_dates = get_holiday_dates(start_date, today)

        users = list(users_collection.find())
        result = []

        for user in users:
            user_id = str(user["_id"])
            leave_dates = get_approved_leave_dates(user_id, start_date, today)

            start_day = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
            end_day = datetime(today.year, today.month, today.day, 23, 59, 59)

            records = list(attendance_collection.find({
                "user_id": user_id,
                "check_in": {"$gte": start_day, "$lte": end_day}
            }).sort("check_in", -1))

            completed_dates = set()
            incomplete_dates = set()

            for record in records:
                check_in = record.get("check_in")
                check_out = record.get("check_out")

                if not check_in:
                    continue

                punch_date = check_in.date()

                if check_in and check_out:
                    completed_dates.add(punch_date)
                elif check_in and not check_out:
                    incomplete_dates.add(punch_date)

            non_working_dates = holiday_dates | leave_dates
            working_days = report_days - len(non_working_dates)

            if working_days < 0:
                working_days = 0

            present_days = len(completed_dates - non_working_dates)
            incomplete_days = len((incomplete_dates - completed_dates) - non_working_dates)
            absent_days = working_days - present_days

            if absent_days < 0:
                absent_days = 0

            last_record = records[0] if records else None

            result.append({
                "user_id": user_id,
                "name": user.get("name", "Unknown"),
                "fingerprint_id": user.get("fingerprint_id"),
                "total_days": report_days,
                "working_days": working_days,
                "holiday_days": len(holiday_dates),
                "leave_days": len(leave_dates),
                "present_days": present_days,
                "absent_days": absent_days,
                "incomplete_days": incomplete_days,
                "last_check_in": last_record.get("check_in") if last_record else None,
                "last_check_out": last_record.get("check_out") if last_record else None,
                "status": "present" if present_days > 0 else "absent"
            })

        return result

    except Exception as e:
        return {"error": str(e)}


@app.get("/attendance/user/{user_id}")
def get_user_attendance_records(user_id: str):
    records = list(attendance_collection.find({"user_id": user_id}).sort("check_in", -1))
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
    today = now_ist()
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
    today = now_ist()
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
    calendar = attendance_calendar(user_id, 30)

    if isinstance(calendar, dict):
        return {
            "present": 0,
            "absent": 0,
            "leave": 0,
            "holiday": 0
        }

    present = 0
    absent = 0
    leave = 0
    holiday = 0

    for item in calendar:
        if item.get("status") == "completed":
            present += 1
        elif item.get("status") == "leave":
            leave += 1
        elif item.get("status") == "holiday":
            holiday += 1
        else:
            absent += 1

    return {
        "present": present,
        "absent": absent,
        "leave": leave,
        "holiday": holiday
    }


@app.get("/attendance/{user_id}")
def get_attendance_by_user_id(user_id: str):
    records = attendance_collection.find({"user_id": user_id}).sort("check_in", -1)
    result = []

    for record in records:
        result.append(attendance_model(record))

    return result
