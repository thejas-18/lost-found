import sqlite3
import os
import json

from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.utils import secure_filename
from sentence_transformers import SentenceTransformer

# Load AI model (local)
model = SentenceTransformer("model/all-MiniLM-L6-v2", local_files_only=True)

# AI modules
from clip_engine import get_embedding, get_text_embedding, get_similarity

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Upload folder
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure folder exists (IMPORTANT for Render)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= DATABASE =================
def connect_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

db = connect_db()
cursor = db.cursor()

# ================= TABLES =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prn TEXT,
    password TEXT,
    name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    title TEXT,
    description TEXT,
    location TEXT,
    date TEXT,
    image TEXT,
    embedding TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lost_item_id INTEGER,
    found_item_id INTEGER,
    match_score INTEGER,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER,
    claimer_prn TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER,
    sender_prn TEXT,
    message TEXT
)
""")

db.commit()
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():

    prn = request.form["prn"]
    password = request.form["password"]

    cursor.execute("""
    SELECT * FROM users
    WHERE prn=? AND password=?
    """, (prn, password))

    user = cursor.fetchone()

    if not user:
        return "Invalid Credentials"

    session["user"] = user["prn"]
    session["user_id"] = user["id"]
    session["name"] = user["name"]

    return redirect("/dashboard")
@app.route("/dashboard")
def dashboard():
    reconnect_db()

    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    user_prn = session["user"]

    # MATCH COUNT
    cursor.execute("""
    SELECT COUNT(*) AS total
    FROM matches m
    JOIN items i ON m.lost_item_id = i.id
    WHERE i.user_id=?
    AND m.status='pending'
    AND i.status='open'
    """, (user_id,))
    
    match_count = cursor.fetchone()["total"]

    # CLAIM REQUESTS
    cursor.execute("""
    SELECT c.id, c.match_id, m.match_score
    FROM claims c
    JOIN matches m ON c.match_id = m.id
    JOIN items i ON m.found_item_id = i.id
    WHERE i.user_id = ?
    AND c.status = 'pending'
    ORDER BY m.match_score DESC
    """, (user_id,))
    
    claim_requests = cursor.fetchall()

    # CHAT COUNT
    cursor.execute("""
    SELECT COUNT(*) AS total
    FROM messages msg
    JOIN matches m ON msg.match_id = m.id
    WHERE msg.sender_prn != ?
    AND m.status = 'pending'
    """, (user_prn,))
    
    message_count = cursor.fetchone()["total"]

    return render_template(
        "dashboard.html",
        name=session["name"],
        match_count=match_count,
        claim_requests=claim_requests,
        message_count=message_count
    )
    
@app.route("/lost", methods=["GET", "POST"])
def lost():
    reconnect_db()

    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        # RAW INPUT
        raw_text = request.form.get("description")

        # LLM (only for title)
        data = extract_item_details(raw_text)

        title = data["title"]

        # IMPORTANT FIX
        description = raw_text

        location = data["location"] or request.form.get("place")
        date_lost = request.form.get("date_lost")

        image_file = request.files.get("image")

        filename = None
        embedding = None

        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(path)

            embedding = get_embedding(path)

        cursor.execute("""
        INSERT INTO items
        (user_id, type, title, description, location, date, image, embedding, status)
        VALUES(?, 'lost', ?, ?, ?, ?, ?, ?, 'open')
        """, (
            session["user_id"],
            title,
            description,
            location,
            date_lost,
            filename,
            str(embedding) if embedding else None
        ))

        db.commit()
        return redirect("/dashboard")

    return render_template("lost.html")


@app.route("/view")
def view_items():
    reconnect_db()

    if "user_id" not in session:
        return redirect("/")

    cursor.execute("""
    SELECT 
        i.*,
        m.id AS match_id,
        m.match_score
    FROM items i
    LEFT JOIN matches m
    ON i.id = m.lost_item_id
    WHERE i.type = 'lost'
    AND i.user_id = ?
    """, (session["user_id"],))

    items = cursor.fetchall()

    for item in items:

        # sqlite Row is mutable? NO → convert to dict
        item = dict(item)

        item["claim_status"] = None

        if item["match_id"]:

            cursor.execute("""
            SELECT status
            FROM claims
            WHERE match_id = ? AND claimer_prn = ?
            ORDER BY id DESC LIMIT 1
            """, (item["match_id"], session["user"]))

            claim = cursor.fetchone()

            if claim:
                item["claim_status"] = claim["status"]

    return render_template("view.html", items=items)
@app.route("/found", methods=["GET", "POST"])
def found():
    reconnect_db()

    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        # RAW INPUT
        raw_text = request.form.get("description")

        data = extract_item_details(raw_text)

        title = data["title"]

        # IMPORTANT FIX
        description = raw_text

        place = data["location"] or request.form.get("place")
        date_found = request.form.get("date_found")

        image_file = request.files.get("image")

        filename = None
        embedding = None

        # ✅ SAFE IMAGE HANDLING (FIXED CRASH ISSUE)
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(path)

            embedding = get_embedding(path)

        cursor.execute("""
        INSERT INTO items
        (user_id, type, title, description, location, date, image, embedding, status)
        VALUES(?, 'found', ?, ?, ?, ?, ?, ?, 'open')
        """, (
            session["user_id"],
            title,
            description,
            place,
            date_found,
            filename,
            str(embedding) if embedding else None
        ))

        db.commit()
        found_id = cursor.lastrowid

        # FETCH LOST ITEMS (LOCATION FILTER)
        cursor.execute("""
        SELECT * FROM items
        WHERE type = 'lost'
        AND status = 'open'
        AND location LIKE ?
        """, (f"%{place}%",))

        lost_items = cursor.fetchall()

        for lost in lost_items:

            # PREVENT DUPLICATE MATCH
            cursor.execute("""
            SELECT id FROM matches
            WHERE lost_item_id = ? AND status = 'pending'
            """, (lost["id"],))

            if cursor.fetchone():
                continue

            # LOAD EMBEDDING
            lost_embedding = None
            if lost["embedding"] and lost["embedding"] != "None":
                try:
                    lost_embedding = json.loads(lost["embedding"])
                except:
                    pass

            lost_data = {
                "description": lost["description"],
                "image": lost["image"],
                "embedding": lost_embedding
            }

            found_data = {
                "description": description,
                "image": filename,
                "embedding": embedding
            }

            # BASE MATCH
            score = match_items(lost_data, found_data)

            # TEXT BOOST
            if description and lost["description"]:
                if any(word in lost["description"].lower() for word in description.lower().split()):
                    score += 40

            # KEYWORD BOOST
            if "earbud" in description.lower() and "earbud" in lost["description"].lower():
                score += 40

            # LOCATION BOOST
            if place and lost["location"]:
                if place.lower() in lost["location"].lower():
                    score += 10

            # DEBUG
            print("--------")
            print("Lost:", lost["description"])
            print("Found:", description)
            print("Score:", score)
            print("--------")

            # FINAL THRESHOLD
            if score >= 40:
                cursor.execute("""
                INSERT INTO matches
                (lost_item_id, found_item_id, match_score, status)
                VALUES(?, ?, ?, 'pending')
                """, (lost["id"], found_id, score))

        db.commit()
        return redirect("/dashboard")

    return render_template("found.html")
@app.route("/view-found")
def view_found():
    reconnect_db()

    if "user_id" not in session:
        return redirect("/")

    cursor.execute("""
    SELECT 
        i.*,
        m.id AS match_id,
        c.status AS claim_status
    FROM items i
    LEFT JOIN matches m ON i.id = m.found_item_id
    LEFT JOIN claims c ON m.id = c.match_id
    WHERE i.user_id = ?
    AND i.type = 'found'
    """, (session["user_id"],))

    items = cursor.fetchall()

    return render_template("view_found.html", items=items)


@app.route("/claim/<int:match_id>")
def claim(match_id):

    if "user" not in session:
        return redirect("/")

    user_prn = session["user"]

    # CHECK DUPLICATE CLAIM
    cursor.execute("""
    SELECT id
    FROM claims
    WHERE match_id = ? AND claimer_prn = ?
    """, (match_id, user_prn))

    existing = cursor.fetchone()

    if existing:
        return redirect("/view")

    # CREATE CLAIM
    cursor.execute("""
    INSERT INTO claims
    (match_id, claimer_prn, status)
    VALUES(?, ?, 'pending')
    """, (match_id, user_prn))

    db.commit()

    return redirect(f"/chat/{match_id}")


@app.route("/verification/<int:match_id>")
def verification(match_id):

    if "user" not in session:
        return redirect("/")

    cursor.execute("""
    SELECT i.title, i.description
    FROM matches m
    JOIN items i ON m.found_item_id = i.id
    WHERE m.id = ?
    """, (match_id,))

    item = cursor.fetchone()

    if not item:
        return "Invalid match"

    questions = generate_verification_questions(
        item["title"],
        item["description"]
    )

    session["verification_questions"] = questions
    session["answers"] = []

    return render_template(
        "verification.html",
        questions=questions,
        match_id=match_id
    )


@app.route("/submit_verification/<int:match_id>", methods=["POST"])
def submit_verification(match_id):

    answers = request.form.getlist("answers")

    session["answers"] = answers

    cursor.execute("""
    SELECT description
    FROM items
    WHERE id = (SELECT found_item_id FROM matches WHERE id = ?)
    """, (match_id,))

    item = cursor.fetchone()

    # AI verification
    result = verify_claim(item["description"], answers)

    score = result["score"]

    # ⚠️ IMPORTANT: SQLite me column hona chahiye
    cursor.execute("""
    UPDATE matches
    SET verification_score = ?
    WHERE id = ?
    """, (score, match_id))

    db.commit()

    return redirect(f"/chat/{match_id}")


@app.route("/chat/<int:match_id>", methods=["GET", "POST"])
def chat(match_id):

    if "user" not in session:
        return redirect("/")

    # CHECK MATCH STATUS
    cursor.execute("""
    SELECT status FROM matches WHERE id = ?
    """, (match_id,))
    
    match = cursor.fetchone()

    if not match:
        return redirect("/dashboard")

    # BLOCK CHAT IF NOT ACTIVE
    if match["status"] != "pending":
        return "Chat closed (Request Rejected or Completed)"

    user_prn = session["user"]

    # GET ITEM
    cursor.execute("""
    SELECT i.title
    FROM matches m
    JOIN items i ON m.lost_item_id = i.id
    WHERE m.id = ?
    """, (match_id,))

    item = cursor.fetchone()

    if not item:
        return "Invalid Chat"

    item_name = item["title"]

    # GET CLAIM
    cursor.execute("""
    SELECT id, claimer_prn, status
    FROM claims
    WHERE match_id = ?
    ORDER BY id DESC
    LIMIT 1
    """, (match_id,))

    claim = cursor.fetchone()

    claim_id = None
    show_buttons = False

    if claim:
        claim_id = claim["id"]

        # FOUNDER ONLY
        if claim["claimer_prn"] != user_prn and claim["status"] == "pending":
            show_buttons = True

    # SEND MESSAGE
    if request.method == "POST":

        msg = request.form["message"]

        cursor.execute("""
        INSERT INTO messages
        (match_id, sender_prn, message)
        VALUES(?, ?, ?)
        """, (match_id, user_prn, msg))

        db.commit()

        return redirect(f"/chat/{match_id}")

    # LOAD MESSAGES
    cursor.execute("""
    SELECT sender_prn, message
    FROM messages
    WHERE match_id = ?
    ORDER BY id ASC
    """, (match_id,))

    chats = cursor.fetchall()

    # ⚠️ FIX: sqlite row → dict convert
    updated_chats = []

    for c in chats:
        c = dict(c)

        if c["sender_prn"] == user_prn:
            c["side"] = "me"
        else:
            c["side"] = "other"

        updated_chats.append(c)

    return render_template(
        "chat.html",
        chats=updated_chats,
        item_name=item_name,
        show_approval_buttons=show_buttons,
        claim_id=claim_id
    )
@app.route("/approve/<int:claim_id>")
def approve(claim_id):

    if "user" not in session:
        return redirect("/")

    # GET MATCH ID
    cursor.execute("""
    SELECT match_id FROM claims WHERE id = ?
    """, (claim_id,))
    
    claim = cursor.fetchone()

    if not claim:
        return redirect("/dashboard")

    match_id = claim["match_id"]

    # UPDATE CLAIM
    cursor.execute("""
    UPDATE claims SET status = 'approved'
    WHERE id = ?
    """, (claim_id,))

    # KEEP MATCH ACTIVE
    cursor.execute("""
    UPDATE matches SET status = 'pending'
    WHERE id = ?
    """, (match_id,))

    db.commit()

    return redirect(f"/chat/{match_id}")


@app.route("/reject/<int:claim_id>")
def reject(claim_id):

    if "user" not in session:
        return redirect("/")

    cursor.execute("""
    SELECT match_id FROM claims WHERE id = ?
    """, (claim_id,))
    
    claim = cursor.fetchone()

    if not claim:
        return redirect("/dashboard")

    match_id = claim["match_id"]

    # CLAIM REJECT
    cursor.execute("""
    UPDATE claims SET status = 'rejected'
    WHERE id = ?
    """, (claim_id,))

    # MATCH CLOSE
    cursor.execute("""
    UPDATE matches SET status = 'closed'
    WHERE id = ?
    """, (match_id,))

    db.commit()

    return redirect("/dashboard")


@app.route("/item-returned/<int:match_id>")
def item_returned(match_id):

    if "user" not in session:
        return redirect("/")

    cursor.execute("""
    SELECT lost_item_id, found_item_id
    FROM matches WHERE id = ?
    """, (match_id,))

    match = cursor.fetchone()

    if not match:
        return redirect("/dashboard")

    # UPDATE ITEMS
    cursor.execute("""
    UPDATE items SET status = 'returned'
    WHERE id = ?
    """, (match["lost_item_id"],))

    cursor.execute("""
    UPDATE items SET status = 'returned'
    WHERE id = ?
    """, (match["found_item_id"],))

    # UPDATE MATCH
    cursor.execute("""
    UPDATE matches SET status = 'completed'
    WHERE id = ?
    """, (match_id,))

    # UPDATE CLAIM
    cursor.execute("""
    UPDATE claims SET status = 'approved'
    WHERE match_id = ?
    """, (match_id,))

    db.commit()

    return redirect("/dashboard")


@app.route("/chat-list")
def chat_list():

    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    cursor.execute("""
    SELECT DISTINCT m.id AS match_id, i.title
    FROM matches m
    JOIN items i ON m.lost_item_id = i.id
    WHERE m.id IN (
        SELECT match_id FROM messages
    )
    AND (
        m.lost_item_id IN (
            SELECT id FROM items WHERE user_id = ?
        )
        OR
        m.found_item_id IN (
            SELECT id FROM items WHERE user_id = ?
        )
    )
    """, (user_id, user_id))

    chats = cursor.fetchall()

    return render_template("chat_list.html", chats=chats)


# ================= RUN SERVER =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
