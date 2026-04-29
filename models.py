def user_model(user):
    return {
        "id": str(user["_id"]),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role", "employee"),
        "fingerprint_id": user.get("fingerprint_id"),
        "department": user.get("department"),
        "phone": user.get("phone"),
    }


def attendance_model(record):
    return {
        "id": str(record["_id"]),
        "user_id": record.get("user_id"),
        "fingerprint_id": record.get("fingerprint_id"),
        "name": record.get("name"),
        "check_in": record.get("check_in"),
        "check_out": record.get("check_out"),
        "status": record.get("status", "present"),
    }
