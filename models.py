def user_model(user):
    return {
        "id": str(user["_id"]),
        "_id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "user"),
        "fingerprint_id": user.get("fingerprint_id"),
        "department": user.get("department", ""),
        "phone": user.get("phone") or user.get("Phone") or "",
    }


def attendance_model(record):
    check_in = record.get("check_in")

    return {
        "id": str(record["_id"]),
        "_id": str(record["_id"]),
        "user_id": record.get("user_id"),
        "fingerprint_id": record.get("fingerprint_id"),
        "name": record.get("name", ""),
        "date": check_in.strftime("%Y-%m-%d") if check_in else record.get("date"),
        "check_in": record.get("check_in"),
        "check_out": record.get("check_out"),
        "status": record.get("status", "present"),
        "message": record.get("message", ""),
    }


def leave_model(leave):
    return {
        "id": str(leave["_id"]),
        "_id": str(leave["_id"]),
        "user_id": leave.get("user_id"),
        "name": leave.get("name", ""),
        "reason": leave.get("reason", ""),
        "start_date": leave.get("start_date"),
        "end_date": leave.get("end_date"),
        "status": leave.get("status", "pending"),
        "applied_at": leave.get("applied_at"),
        "updated_at": leave.get("updated_at"),
    }


def holiday_model(holiday):
    return {
        "id": str(holiday["_id"]),
        "_id": str(holiday["_id"]),
        "name": holiday.get("name", ""),
        "date": holiday.get("date"),
        "created_at": holiday.get("created_at"),
    }
