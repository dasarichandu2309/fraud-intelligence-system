from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "analyst"


@app.post("/create_user")
def create_user(user: UserCreate):
    conn = get_connection()
    cursor = conn.cursor()

    hashed = hash_password(user.password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (user.username, hashed, user.role)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    cursor.close()
    conn.close()

    return {"message": "User created successfully"}