def user_model(user):
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user.get("role", "employee"),
        "fingerprint_id": user.get("fingerprint_id"),
        "department": user.get("department"),
        "phone": user.get("phone"),
    }

def attendance_model(record):
    return {
        "id": str(record["_id"]),
        "user_id": record["user_id"],
        "check_in": record["check_in"],
        "check_out": record.get("check_out"),
        "status": record.get("status", "present"),
    }