import json
import os

import pymysql
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "studentdb")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "20"))
CACHE_KEY = "students:all"

app = FastAPI(title="学生管理系统", version="1.0.0")
cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=2)


def get_conn():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
    )


def drop_cache():
    try:
        cache.delete(CACHE_KEY)
    except Exception:
        pass


class StudentIn(BaseModel):
    student_no: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)
    gender: str = Field("男", max_length=4)
    class_name: str = Field(..., min_length=1, max_length=64)
    email: str | None = Field(None, max_length=128)


@app.get("/api/health")
def health():
    db_ok = False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = cur.fetchone() is not None
    except Exception:
        pass

    redis_ok = False
    try:
        redis_ok = bool(cache.ping())
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "mysql": db_ok,
        "redis": redis_ok,
        "pod": os.getenv("HOSTNAME", "unknown"),
    }


@app.get("/api/stats")
def stats():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total FROM students")
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT class_name, COUNT(*) AS cnt FROM students "
                    "GROUP BY class_name ORDER BY cnt DESC"
                )
                rows = cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库不可用: %s" % exc)
    return {"total": total, "by_class": rows}


@app.get("/api/students")
def list_students(keyword: str = ""):
    if not keyword:
        try:
            cached = cache.get(CACHE_KEY)
            if cached:
                return {"source": "redis", "items": json.loads(cached)}
        except Exception:
            pass

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if keyword:
                    like = "%%%s%%" % keyword
                    cur.execute(
                        "SELECT * FROM students WHERE name LIKE %s OR student_no LIKE %s "
                        "OR class_name LIKE %s ORDER BY id DESC",
                        (like, like, like),
                    )
                else:
                    cur.execute("SELECT * FROM students ORDER BY id DESC")
                rows = cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库不可用: %s" % exc)

    if not keyword:
        try:
            cache.setex(CACHE_KEY, CACHE_TTL, json.dumps(rows, ensure_ascii=False, default=str))
        except Exception:
            pass

    return {"source": "mysql", "items": rows}


@app.post("/api/students", status_code=201)
def create_student(body: StudentIn):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO students (student_no, name, gender, class_name, email) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (body.student_no, body.name, body.gender, body.class_name, body.email),
                )
                new_id = cur.lastrowid
            conn.commit()
    except pymysql.err.IntegrityError:
        raise HTTPException(status_code=400, detail="学号已存在")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库不可用: %s" % exc)

    drop_cache()
    return {"id": new_id, "message": "创建成功"}


@app.put("/api/students/{sid}")
def update_student(sid: int, body: StudentIn):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                affected = cur.execute(
                    "UPDATE students SET student_no=%s, name=%s, gender=%s, "
                    "class_name=%s, email=%s WHERE id=%s",
                    (body.student_no, body.name, body.gender, body.class_name, body.email, sid),
                )
            conn.commit()
    except pymysql.err.IntegrityError:
        raise HTTPException(status_code=400, detail="学号已存在")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库不可用: %s" % exc)

    if not affected:
        raise HTTPException(status_code=404, detail="学生不存在")

    drop_cache()
    return {"message": "更新成功"}


@app.delete("/api/students/{sid}")
def delete_student(sid: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                affected = cur.execute("DELETE FROM students WHERE id=%s", (sid,))
            conn.commit()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库不可用: %s" % exc)

    if not affected:
        raise HTTPException(status_code=404, detail="学生不存在")

    drop_cache()
    return {"message": "删除成功"}
