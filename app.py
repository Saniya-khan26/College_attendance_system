from flask import Flask, render_template, redirect, url_for, request, session
from werkzeug.security import check_password_hash,generate_password_hash
from dotenv import load_dotenv
from datetime import datetime
import os

from db import db
from bson.objectid import ObjectId
from io import BytesIO
from flask import send_file
from openpyxl import Workbook
load_dotenv()

app = Flask(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing from .env")

app.config["SECRET_KEY"] = SECRET_KEY


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = db.users.find_one({
            "username": username
        })

        if user and user.get("status", "active") != "active":
            return render_template(
                "login.html",
                error="Your account is inactive. Please contact the administrator."
                )

        if user and check_password_hash(user["password"], password):

            session["username"] = user["username"]
            session["role"] = user["role"]
            session["student_id"] = user.get("student_id")
            session["faculty_id"] = user.get("faculty_id")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            elif user["role"] == "faculty":
                return redirect(url_for("faculty_dashboard"))

            elif user["role"] == "student":
                return redirect(url_for("student_dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")
@app.route("/faculty/dashboard")
def faculty_dashboard():

    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    faculty_id = session.get("faculty_id")

    faculty_member = db.faculty.find_one({
        "faculty_id": faculty_id
    })

    if not faculty_member:
        return redirect(url_for("login"))

    assigned_classes = faculty_member.get("assigned_classes", [])

    classes_list = list(
        db.classes.find({
            "class_id": {
                "$in": assigned_classes
            },
            "status": "active"
        })
    )

    total_students = db.students.count_documents({
        "status": "active"
    })

    today = datetime.now().strftime("%Y-%m-%d")

    final_attendance = list(
        db.attendance.find({
            "date": today,
            "session": "afternoon"
        })
    )

    if not final_attendance:
        final_attendance = list(
            db.attendance.find({
                "date": today,
                "session": "noon"
            })
        )

    present_today = sum(
        1
        for record in final_attendance
        if record.get("status") == "Present"
    )

    absent_today = sum(
        1
        for record in final_attendance
        if record.get("status") == "Absent"
    )

    return render_template(
        "faculty/dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        faculty=faculty_member,
        assigned_classes=classes_list
    )
@app.route("/faculty/attendance/<class_id>", methods=["GET", "POST"])
def faculty_attendance(class_id):

    # Faculty login check
    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    faculty_id = session.get("faculty_id")

    # Find logged-in faculty
    faculty_member = db.faculty.find_one({
        "faculty_id": faculty_id
    })

    if not faculty_member:
        return redirect(url_for("login"))

    # Get assigned classes
    assigned_classes = faculty_member.get("assigned_classes", [])

    # SECURITY CHECK
    if class_id not in assigned_classes:
        return "You are not authorized to access this class.", 403

    # Find selected class
    selected_class = db.classes.find_one({
        "class_id": class_id,
        "status": "active"
    })

    if not selected_class:
        return "Class not found.", 404

    # Get students of selected class
    students = list(
        db.students.find({
            "status": "active",
            "class_id": class_id
        }).sort("student_id", 1)
    )

    today = datetime.now().strftime("%Y-%m-%d")

    # ==================================================
    # SAVE ATTENDANCE
    # ==================================================

    if request.method == "POST":

        attendance_date = request.form.get("date", today)
        session_type = request.form.get("session_type")

        if session_type not in ["noon", "afternoon"]:
            return render_template(
                "faculty/attendance.html",
                students=students,
                selected_class=selected_class,
                noon_status={},
                afternoon_status={},
                comparison_results={},
                today=today,
                today_display=datetime.now().strftime("%d-%m-%Y"),
                error="Please select an attendance session."
            )

        saved_count = 0

        for student in students:

            student_id = student.get("student_id")

            status = request.form.get(
                f"status_{student_id}"
            )

            # Skip if neither Present nor Absent was selected
            if status not in ["Present", "Absent"]:
                continue

            # Prevent duplicate attendance
            existing_record = db.attendance.find_one({
                "date": attendance_date,
                "class_id": class_id,
                "student_id": student_id,
                "session": session_type
            })

            if existing_record:

                db.attendance.update_one(
                    {
                        "_id": existing_record["_id"]
                    },
                    {
                        "$set": {
                            "status": status,
                            "faculty_id": faculty_id
                        }
                    }
                )

            else:

                db.attendance.insert_one({
                    "date": attendance_date,
                    "class_id": class_id,
                    "student_id": student_id,
                    "student_name": student.get("name"),
                    "session": session_type,
                    "status": status,
                    "faculty_id": faculty_id
                })

            saved_count += 1

        return redirect(
            url_for(
                "faculty_attendance",
                class_id=class_id
            )
        )

    # ==================================================
    # LOAD TODAY'S ATTENDANCE
    # ==================================================

    noon_records = list(
        db.attendance.find({
            "date": today,
            "class_id": class_id,
            "session": "noon"
        })
    )

    afternoon_records = list(
        db.attendance.find({
            "date": today,
            "class_id": class_id,
            "session": "afternoon"
        })
    )

    noon_status = {
        record.get("student_id"): record.get("status")
        for record in noon_records
    }

    afternoon_status = {
        record.get("student_id"): record.get("status")
        for record in afternoon_records
    }

    # ==================================================
    # COMPARE NOON + AFTERNOON
    # ==================================================

    comparison_results = {}

    for student in students:

        student_id = student.get("student_id")

        noon = noon_status.get(student_id)
        afternoon = afternoon_status.get(student_id)

        if noon == "Present" and afternoon == "Present":
            result = "Present"

        elif noon == "Absent" and afternoon == "Present":
            result = "Late Arrival"

        elif noon == "Present" and afternoon == "Absent":
            result = "Left Midway"

        elif noon == "Absent" and afternoon == "Absent":
            result = "Absent Both Sessions"

        elif noon == "Present" and afternoon is None:
            result = "Present"

        elif noon == "Absent" and afternoon is None:
            result = "Absent"

        else:
            result = None

        comparison_results[student_id] = result

    return render_template(
        "faculty/attendance.html",
        students=students,
        selected_class=selected_class,
        noon_status=noon_status,
        afternoon_status=afternoon_status,
        comparison_results=comparison_results,
        today=today,
        today_display=datetime.now().strftime("%d-%m-%Y")
    )

@app.route("/admin/dashboard")
def admin_dashboard():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    total_students = db.students.count_documents({
        "status": "active"
    })

    total_faculty = db.faculty.count_documents({})

    total_classes = db.classes.count_documents({})

    today = datetime.now().strftime("%Y-%m-%d")

    today_attendance = list(
        db.attendance.find({
            "date": today
        })
    )

    present_today = sum(
        1 for record in today_attendance
        if record.get("status") == "Present"
    )

    absent_today = sum(
        1 for record in today_attendance
        if record.get("status") == "Absent"
    )

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_faculty=total_faculty,
        total_classes=total_classes,
        present_today=present_today,
        absent_today=absent_today
    )
# ==========================================
# ADMIN CLASS MANAGEMENT
# ==========================================
@app.route("/admin/classes/add", methods=["GET", "POST"])
def add_class():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # Get all active faculty
    faculty_list = list(
        db.faculty.find({
            "status": "active"
        }).sort("name", 1)
    )

    print("Faculty found:", faculty_list)

    if request.method == "POST":

        class_id = request.form.get("class_id", "").strip()
        course = request.form.get("course", "").strip()
        semester = request.form.get("semester", "").strip()
        division = request.form.get("division", "").strip()
        academic_year = request.form.get("academic_year", "").strip()
        teacher_id = request.form.get("teacher_id", "").strip()

        if not all([
            class_id,
            course,
            semester,
            division,
            academic_year,
            teacher_id
        ]):
            return render_template(
                "admin/add_class.html",
                faculty_list=faculty_list,
                error="Please fill all fields."
            )

        try:
            semester = int(semester)
        except ValueError:
            return render_template(
                "admin/add_class.html",
                faculty_list=faculty_list,
                error="Invalid semester selected."
            )

        # Check duplicate class
        existing_class = db.classes.find_one({
            "class_id": class_id
        })

        if existing_class:
            return render_template(
                "admin/add_class.html",
                faculty_list=faculty_list,
                error="Class ID already exists."
            )

        # Find selected faculty
        teacher = db.faculty.find_one({
            "faculty_id": teacher_id,
            "status": "active"
        })

        if not teacher:
            return render_template(
                "admin/add_class.html",
                faculty_list=faculty_list,
                error="Selected faculty does not exist."
            )

        class_data = {
            "class_id": class_id,
            "course": course,
            "semester": semester,
            "division": division,
            "academic_year": academic_year,
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("name", ""),
            "status": "active",
            "created_at": datetime.now()
        }

        db.classes.insert_one(class_data)

        return redirect(url_for("classes"))

    return render_template(
        "admin/add_class.html",
        faculty_list=faculty_list
    )
@app.route("/student/dashboard")
def student_dashboard():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    student_id = session.get("student_id")

    student = db.students.find_one({
        "student_id": student_id
    })

    if not student:
        return "Student record not found", 404

    # Get all attendance records of this student
    attendance_records = list(
        db.attendance.find({
            "student_id": student_id
        }).sort("date", -1)
    )
   
    # Combine noon and afternoon attendance
    # into one record per date
    daily_attendance = {}

    for record in attendance_records:

        date = record.get("date")

        if date not in daily_attendance:
            daily_attendance[date] = {
                "date": date,
                "noon": None,
                "afternoon": None,
                "attendance_type": None
            }

        if record.get("session") == "noon":
            daily_attendance[date]["noon"] = record.get("status")

        elif record.get("session") == "afternoon":
            daily_attendance[date]["afternoon"] = record.get("status")
            daily_attendance[date]["attendance_type"] = record.get(
                "attendance_type"
            )

    # Calculate attendance
    present_days = 0
    absent_days = 0

    for day in daily_attendance.values():

        noon = day.get("noon")
        afternoon = day.get("afternoon")

        # Present in both sessions
        if noon == "Present" and afternoon == "Present":
            present_days += 1

        # Present at noon but absent during final recheck
        elif noon == "Present" and afternoon == "Absent":
            present_days += 1

        # Absent at noon but arrived later
        elif noon == "Absent" and afternoon == "Present":
            present_days += 1

        # Absent in both sessions
        elif noon == "Absent" and afternoon == "Absent":
            absent_days += 1

        # Only noon attendance has been marked
        elif noon == "Present" and afternoon is None:
            present_days += 1

        elif noon == "Absent" and afternoon is None:
            absent_days += 1

    # Only actually marked attendance days are counted
    total_days = present_days + absent_days

    # Calculate percentage
    attendance_percentage = (
        round((present_days / total_days) * 100, 2)
        if total_days > 0
        else 0
    )

    return render_template(
        "student/dashboard.html",
        student=student,
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        attendance_percentage=attendance_percentage
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

@app.route("/admin/students")
def students():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()

    if search:

        students_list = list(
            db.students.find({
                "$or": [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"student_id": {"$regex": search, "$options": "i"}},
                    {"roll_no": search}
                ]
            }).sort("roll_no", 1)
        )

    else:

        students_list = list(
            db.students.find().sort("roll_no", 1)
        )

    return render_template(
        "admin/students.html",
        students=students_list,
        search=search
    )
@app.route("/admin/students/add", methods=["GET", "POST"])
def add_student():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # Get active classes
    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort([
            ("course", 1),
            ("semester", 1),
            ("division", 1)
        ])
    )

    if request.method == "POST":

        # ---------------------------------------------
        # Get form data
        # ---------------------------------------------

        name = request.form.get(
            "name",
            ""
        ).strip()

        class_id = request.form.get(
            "class_id",
            ""
        ).strip()


        # ---------------------------------------------
        # Basic validation
        # ---------------------------------------------

        if not name or not class_id:

            return render_template(
                "admin/add_student.html",
                classes=classes_list,
                name=name,
                selected_class_id=class_id,
                error="Student name and class are required."
            )


        # ---------------------------------------------
        # Find selected class
        # ---------------------------------------------

        selected_class = db.classes.find_one({
            "class_id": class_id,
            "status": "active"
        })

        if not selected_class:

            return render_template(
                "admin/add_student.html",
                classes=classes_list,
                name=name,
                selected_class_id=class_id,
                error="Selected class is invalid."
            )


        # ---------------------------------------------
        # Get course
        # ---------------------------------------------

        course = str(
            selected_class.get(
                "course",
                ""
            )
        ).strip().upper()


        # ---------------------------------------------
        # Create short course code
        #
        # BCA -> BCA
        # Biotechnology -> BT
        # BSc -> BSC
        # ---------------------------------------------

        course_codes = {
            "BCA": "BCA",
            "BIOTECHNOLOGY": "BT",
            "BT": "BT",
            "BSC": "BSC",
            "B.SC": "BSC"
        }

        course_code = course_codes.get(
            course
        )

        if not course_code:

            # Fallback:
            # remove spaces and use first 3 letters
            course_code = (
                course
                .replace(" ", "")
                .replace(".", "")
                [:3]
            )

        if not course_code:

            return render_template(
                "admin/add_student.html",
                classes=classes_list,
                name=name,
                selected_class_id=class_id,
                error="Unable to generate course code for this class."
            )


        # ---------------------------------------------
        # Determine batch year
        #
        # Example:
        # academic_year = 2026-27
        # batch year     = 26
        # ---------------------------------------------

        academic_year = str(
            selected_class.get(
                "academic_year",
                ""
            )
        ).strip()

        batch_year = ""

        if academic_year:

            first_year = academic_year.split("-")[0]

            if first_year.isdigit():

                batch_year = first_year[-2:]


        # Fallback if academic year is missing
        if not batch_year:

            batch_year = str(
                datetime.now().year
            )[-2:]


        # ---------------------------------------------
        # Generate ID prefix
        #
        # Example:
        # 26-BCA
        # 26-BT
        # ---------------------------------------------

        id_prefix = (
            f"{batch_year}-{course_code}"
        )


        # ---------------------------------------------
        # Find existing students with this prefix
        # ---------------------------------------------

        existing_students = list(
            db.students.find({
                "student_id": {
                    "$regex": f"^{id_prefix}-\\d+$",
                    "$options": "i"
                }
            })
        )


        # ---------------------------------------------
        # Find next student number
        # ---------------------------------------------

        used_numbers = []

        for student in existing_students:

            student_id = str(
                student.get(
                    "student_id",
                    ""
                )
            )

            parts = student_id.split("-")

            if len(parts) == 3:

                number_part = parts[-1]

                if number_part.isdigit():

                    used_numbers.append(
                        int(number_part)
                    )


        if used_numbers:

            next_number = max(
                used_numbers
            ) + 1

        else:

            next_number = 1


        # ---------------------------------------------
        # Generate final Student ID
        # ---------------------------------------------

        student_id = (
            f"{id_prefix}-{next_number:03d}"
        )


        # ---------------------------------------------
        # Safety check
        # ---------------------------------------------

        while db.students.find_one({
            "student_id": student_id
        }):

            next_number += 1

            student_id = (
                f"{id_prefix}-{next_number:03d}"
            )


        # ---------------------------------------------
        # Insert student
        # ---------------------------------------------

        student_document = {

            "student_id": student_id,

            "name": name,

            "class_id": class_id,

            "class_name": class_id,

            "course": selected_class.get(
                "course"
            ),

            "semester": selected_class.get(
                "semester"
            ),

            "division": selected_class.get(
                "division"
            ),

            "academic_year": selected_class.get(
                "academic_year"
            ),

            "status": "active"
        }


        db.students.insert_one(
            student_document
        )


        # ---------------------------------------------
        # Redirect after successful creation
        # ---------------------------------------------

        return redirect(
            url_for("students")
        )


    return render_template(
        "admin/add_student.html",
        classes=classes_list,
        name="",
        selected_class_id="",
        error=None
    )
@app.route("/admin/students/edit/<student_id>", methods=["GET", "POST"])
def edit_student(student_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # Find student
    student = db.students.find_one({
        "_id": ObjectId(student_id)
    })

    if not student:
        return redirect(url_for("students"))

    # Get active classes
    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort([
            ("course", 1),
            ("semester", 1),
            ("division", 1)
        ])
    )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        class_id = request.form.get(
            "class_id",
            ""
        ).strip()

        status = request.form.get(
            "status",
            "active"
        ).strip()

        # Validation
        if not name or not class_id:

            return render_template(
                "admin/edit_student.html",
                student=student,
                classes=classes_list,
                error="Student name and class are required."
            )

        if status not in ["active", "inactive"]:

            status = "active"

        # Find selected class
        selected_class = db.classes.find_one({
            "class_id": class_id,
            "status": "active"
        })

        if not selected_class:

            return render_template(
                "admin/edit_student.html",
                student=student,
                classes=classes_list,
                error="Selected class is invalid."
            )

        # Update student
        db.students.update_one(
            {
                "_id": ObjectId(student_id)
            },
            {
                "$set": {
                    "name": name,
                    "class_id": class_id,
                    "class_name": class_id,
                    "course": selected_class.get("course"),
                    "semester": selected_class.get("semester"),
                    "division": selected_class.get("division"),
                    "academic_year": selected_class.get("academic_year"),
                    "status": status
                }
            }
        )

        return redirect(
            url_for("students")
        )

    return render_template(
        "admin/edit_student.html",
        student=student,
        classes=classes_list,
        error=None
    )

@app.route("/admin/students/delete/<student_id>", methods=["POST"])
def delete_student(student_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    db.students.delete_one({
        "_id": ObjectId(student_id)
    })

    return redirect(url_for("students"))

@app.route("/student/profile")
def student_profile():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    student_id = session.get("student_id")

    student = db.students.find_one({
        "student_id": student_id
    })

    if not student:
        return "Student record not found", 404

    return render_template(
        "student/profile.html",
        student=student
    )

@app.route("/admin/faculty")
def faculty():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()

    if search:

        faculty_list = list(
            db.faculty.find({
                "$or": [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"faculty_id": {"$regex": search, "$options": "i"}},
                    {"department": {"$regex": search, "$options": "i"}}
                ]
            }).sort("name", 1)
        )

    else:

        faculty_list = list(
            db.faculty.find().sort("name", 1)
        )

    return render_template(
        "admin/faculty.html",
        faculty_list=faculty_list,
        search=search
    )
@app.route("/admin/faculty/edit/<faculty_id>", methods=["GET", "POST"])
def edit_faculty(faculty_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # Find faculty
    faculty_member = db.faculty.find_one({
        "faculty_id": faculty_id
    })

    if not faculty_member:
        return redirect(url_for("faculty"))

    # Get active classes
    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort("course", 1)
    )

    # Find existing login account
    user = db.users.find_one({
        "faculty_id": faculty_id,
        "role": "faculty"
    })

    # -----------------------------
    # POST
    # -----------------------------
    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()

        assigned_classes = request.form.getlist("assigned_classes")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        status = request.form.get("status", "active")

        # Required fields
        if not name or not username or not assigned_classes:

            return render_template(
                "admin/edit_faculty.html",
                faculty=faculty_member,
                classes=classes_list,
                username=username,
                error="Name, username and at least one assigned class are required."
            )

        # Check whether username belongs to another account
        existing_user = db.users.find_one({
            "username": username,
            "faculty_id": {
                "$ne": faculty_id
            }
        })

        if existing_user:

            return render_template(
                "admin/edit_faculty.html",
                faculty=faculty_member,
                classes=classes_list,
                username=username,
                error="This username is already being used."
            )

        # Validate selected classes
        selected_classes = list(
            db.classes.find({
                "class_id": {
                    "$in": assigned_classes
                },
                "status": "active"
            })
        )

        if len(selected_classes) != len(assigned_classes):

            return render_template(
                "admin/edit_faculty.html",
                faculty=faculty_member,
                classes=classes_list,
                username=username,
                error="One or more selected classes are invalid."
            )

        # --------------------------------
        # Update faculty information
        # --------------------------------

        db.faculty.update_one(
            {
                "faculty_id": faculty_id
            },
            {
                "$set": {
                    "name": name,
                    "email": email,
                    "department": department,
                    "designation": designation,
                    "assigned_classes": assigned_classes,
                    "status": status
                }
            }
        )

        # --------------------------------
        # Update or create login account
        # --------------------------------

        if user:

            user_update = {
                "username": username,
                "status": status
            }

            # Update password only if entered
            if password:

                user_update["password"] = generate_password_hash(
                    password
                )

            db.users.update_one(
                {
                    "faculty_id": faculty_id,
                    "role": "faculty"
                },
                {
                    "$set": user_update
                }
            )

        else:

            # No login account exists
            if not password:

                return render_template(
                    "admin/edit_faculty.html",
                    faculty=faculty_member,
                    classes=classes_list,
                    username=username,
                    error="Please enter a password to create the faculty login account."
                )

            new_user = {
                "username": username,
                "password": generate_password_hash(password),
                "role": "faculty",
                "faculty_id": faculty_id,
                "status": status
            }

            db.users.insert_one(new_user)

        return redirect(url_for("faculty"))

    # -----------------------------
    # GET
    # -----------------------------

    return render_template(
        "admin/edit_faculty.html",
        faculty=faculty_member,
        classes=classes_list,
        username=user.get("username", "") if user else ""
    )

@app.route("/admin/faculty/add", methods=["GET", "POST"])
def add_faculty():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort("course", 1)
    )

    if request.method == "POST":

        faculty_id = request.form.get("faculty_id", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        assigned_classes = request.form.getlist("assigned_class")
        status = request.form.get("status", "active")

        # Check required fields
        if not all([
            faculty_id,
            name,
            username,
            password,
            assigned_classes
        ]):
            return render_template(
                "admin/add_faculty.html",
                classes=classes_list,
                error="Please fill all required fields."
            )

        # Check duplicate Faculty ID
        existing_faculty = db.faculty.find_one({
            "faculty_id": faculty_id
        })

        if existing_faculty:
            return render_template(
                "admin/add_faculty.html",
                classes=classes_list,
                error="Faculty ID already exists."
            )

        # Check duplicate username
        existing_user = db.users.find_one({
            "username": username
        })

        if existing_user:
            return render_template(
                "admin/add_faculty.html",
                classes=classes_list,
                error="Username already exists."
            )

        # Check selected class exists
        selected_classes = list(
            db.classes.find({
               "class_id": {"$in": assigned_classes},
               "status": "active"
            })
        )

        if len(selected_classes) != len(assigned_classes):
            return render_template(
           "admin/add_faculty.html",
            classes=classes_list,
             error="One or more selected classes are invalid."
        )

        if not selected_classes:
            return render_template(
                "admin/add_faculty.html",
                classes=classes_list,
                error="Selected class does not exist."
            )

        # Create faculty record
        db.faculty.insert_one({
            "faculty_id": faculty_id,
            "name": name,
            "email": email,
            "department": department,
            "designation": designation,
            "assigned_classes": assigned_classes,
            "status": status
        })

        # Create login account
        db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password),
            "role": "faculty",
            "faculty_id": faculty_id,
            "status": status
        })

        return redirect(url_for("faculty"))

    return render_template(
        "admin/add_faculty.html",
        classes=classes_list
    )
@app.route("/admin/classes")
def classes():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    classes_list = list(
        db.classes.find({})
    )

    print("================================")
    print("TOTAL CLASSES:", len(classes_list))
    print("CLASSES:", classes_list)
    print("================================")

    return render_template(
        "admin/classes.html",
        classes=classes_list
    )

@app.route(
    "/admin/classes/delete/<class_id>",
    methods=["POST"]
)
def delete_class(class_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    db.classes.delete_one({
        "_id": ObjectId(class_id)
    })

    return redirect(url_for("classes"))

@app.route("/admin/holidays")
def holidays():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    holidays_list = list(
        db.holidays.find().sort("date", 1)
    )

    return render_template(
        "admin/holidays.html",
        holidays_list=holidays_list
    )
@app.route("/admin/holidays/add", methods=["GET", "POST"])
def add_holiday():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":

        holiday_date = request.form.get("date", "").strip()
        holiday_name = request.form.get("name", "").strip()

        if not holiday_date or not holiday_name:

            return render_template(
                "admin/add_holiday.html",
                error="Please fill all fields."
            )

        # Check duplicate date
        existing_holiday = db.holidays.find_one({
            "date": holiday_date
        })

        if existing_holiday:

            return render_template(
                "admin/add_holiday.html",
                error="A holiday already exists on this date."
            )

        db.holidays.insert_one({
            "date": holiday_date,
            "name": holiday_name
        })

        return redirect(url_for("holidays"))

    return render_template("admin/add_holiday.html")
@app.route("/admin/holidays/delete/<holiday_id>", methods=["POST"])
def delete_holiday(holiday_id):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    db.holidays.delete_one({
        "_id": ObjectId(holiday_id)
    })

    return redirect(url_for("holidays"))
@app.route("/admin/attendance")
def admin_attendance():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # -----------------------------
    # Filters
    # -----------------------------

    search = request.args.get("search", "").strip()
    selected_date = request.args.get("date", "").strip()
    selected_class_id = request.args.get("class_id", "").strip()

    # -----------------------------
    # Get active classes
    # -----------------------------

    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort([
            ("course", 1),
            ("semester", 1),
            ("division", 1)
        ])
    )

    # -----------------------------
    # Attendance query
    # -----------------------------

    query = {}

    if selected_date:
        query["date"] = selected_date

    if selected_class_id:
        query["class_id"] = selected_class_id

    # -----------------------------
    # Get attendance records
    # -----------------------------

    attendance_records = list(
        db.attendance.find(query)
    )

    # -----------------------------
    # Search student
    # -----------------------------

    if search:

        search_lower = search.lower()

        filtered_records = []

        for record in attendance_records:

            student_name = str(
                record.get("student_name", "")
            ).lower()

            student_id = str(
                record.get("student_id", "")
            ).lower()

            roll_no = str(
                record.get("roll_no", "")
            ).lower()

            if (
                search_lower in student_name
                or search_lower in student_id
                or search_lower in roll_no
            ):
                filtered_records.append(record)

        attendance_records = filtered_records

    # -----------------------------
    # Combine noon + afternoon
    # -----------------------------

    daily_attendance = {}

    for record in attendance_records:

        student_id = record.get("student_id")
        date = record.get("date")

        key = (student_id, date)

        if key not in daily_attendance:

            daily_attendance[key] = {
                "student_id": student_id,
                "student_name": record.get("student_name"),
                "roll_no": record.get("roll_no"),
                "date": date,
                "class_id": record.get("class_id"),
                "noon": None,
                "afternoon": None,
                "attendance_type": None
            }

        if record.get("session") == "noon":

            daily_attendance[key]["noon"] = record.get(
                "status"
            )

        elif record.get("session") == "afternoon":

            daily_attendance[key]["afternoon"] = record.get(
                "status"
            )

    # -----------------------------
    # Calculate final attendance
    # -----------------------------

    daily_records = []

    for day in daily_attendance.values():

        noon = day.get("noon")
        afternoon = day.get("afternoon")

        if noon == "Present" and afternoon == "Present":

            day["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon == "Present":

            day["attendance_type"] = "Late Arrival"

        elif noon == "Present" and afternoon == "Absent":

            day["attendance_type"] = "Left Midway"

        elif noon == "Absent" and afternoon == "Absent":

            day["attendance_type"] = "Absent Both Sessions"

        elif noon == "Present" and afternoon is None:

            day["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon is None:

            day["attendance_type"] = "Absent Both Sessions"

        else:

            day["attendance_type"] = "Waiting for Recheck"

        daily_records.append(day)

    # -----------------------------
    # Safe sorting
    # -----------------------------

    def safe_roll_no(record):

        roll_no = record.get("roll_no")

        if roll_no is None:
            return 999999

        try:
            return int(roll_no)

        except (ValueError, TypeError):
            return 999999

    daily_records.sort(
        key=lambda record: (
            record.get("date") or "",
            safe_roll_no(record)
        ),
        reverse=True
    )

    # -----------------------------
    # Statistics
    # -----------------------------

    total_records = len(daily_records)

    present_count = 0
    absent_count = 0

    for record in daily_records:

        attendance_type = record.get(
            "attendance_type"
        )

        if attendance_type in [
            "Present",
            "Late Arrival",
            "Left Midway"
        ]:

            present_count += 1

        elif attendance_type == "Absent Both Sessions":

            absent_count += 1

    marked_days = present_count + absent_count

    attendance_percentage = (
        round(
            (present_count / marked_days) * 100,
            2
        )
        if marked_days > 0
        else 0
    )

    # -----------------------------
    # Send data to template
    # -----------------------------

    return render_template(
        "admin/attendance.html",
        attendance_records=daily_records,
        search=search,
        date=selected_date,
        selected_class_id=selected_class_id,
        classes=classes_list,
        total_records=total_records,
        present_count=present_count,
        absent_count=absent_count,
        attendance_percentage=attendance_percentage
    )
@app.route("/admin/take-attendance", methods=["GET", "POST"])
def admin_take_attendance():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    today_date = datetime.now().strftime("%Y-%m-%d")
    today_display = datetime.now().strftime("%d %B %Y")

    # --------------------------------
    # Get all active classes
    # --------------------------------

    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort([
            ("course", 1),
            ("semester", 1),
            ("division", 1)
        ])
    )

    # --------------------------------
    # Selected class
    # --------------------------------

    selected_class_id = request.args.get(
        "class_id",
        ""
    ).strip()

    if request.method == "POST":
        selected_class_id = request.form.get(
            "class_id",
            ""
        ).strip()

    # --------------------------------
    # Validate selected class
    # --------------------------------

    selected_class = None

    if selected_class_id:

        selected_class = db.classes.find_one({
            "class_id": selected_class_id,
            "status": "active"
        })

        if not selected_class:

            return render_template(
                "admin/take_attendance.html",
                today=today_date,
                today_display=today_display,
                classes=classes_list,
                students=[],
                selected_class_id="",
                selected_class=None,
                noon_status={},
                comparison_results={},
                error="Selected class is invalid."
            )

    # --------------------------------
    # Get students of selected class
    # --------------------------------

    students = []

    if selected_class:

        students = list(
            db.students.find({
                "status": "active",
                "class_id": selected_class_id
            }).sort("roll_no", 1)
        )

    # --------------------------------
    # Get today's noon attendance
    # for selected class
    # --------------------------------

    noon_attendance = []

    if selected_class:

        noon_attendance = list(
            db.attendance.find({
                "date": today_date,
                "session": "noon",
                "class_id": selected_class_id
            })
        )

    noon_status = {
        record["student_id"]: record.get("status")
        for record in noon_attendance
    }

    # --------------------------------
    # Get comparison results
    # --------------------------------

    comparison_records = []

    if selected_class:

        comparison_records = list(
            db.attendance.find({
                "date": today_date,
                "session": "afternoon",
                "class_id": selected_class_id,
                "attendance_type": {
                    "$exists": True
                }
            })
        )

    comparison_results = {
        record["student_id"]: record.get(
            "attendance_type"
        )
        for record in comparison_records
    }

    # --------------------------------
    # POST - Save attendance
    # --------------------------------

    if request.method == "POST":

        session_type = request.form.get(
            "session_type"
        )

        # Check class
        if not selected_class:

            return render_template(
                "admin/take_attendance.html",
                today=today_date,
                today_display=today_display,
                classes=classes_list,
                students=students,
                selected_class_id=selected_class_id,
                selected_class=selected_class,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Please select a valid class."
            )

        # Check session
        if session_type not in [
            "noon",
            "afternoon"
        ]:

            return render_template(
                "admin/take_attendance.html",
                today=today_date,
                today_display=today_display,
                classes=classes_list,
                students=students,
                selected_class_id=selected_class_id,
                selected_class=selected_class,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Please select a valid attendance session."
            )

        # --------------------------------
        # Sunday check
        # --------------------------------

        date_object = datetime.strptime(
            today_date,
            "%Y-%m-%d"
        )

        if date_object.weekday() == 6:

            return render_template(
                "admin/take_attendance.html",
                today=today_date,
                today_display=today_display,
                classes=classes_list,
                students=students,
                selected_class_id=selected_class_id,
                selected_class=selected_class,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Attendance cannot be marked on Sunday."
            )

        # --------------------------------
        # Holiday check
        # --------------------------------

        holiday = db.holidays.find_one({
            "date": today_date
        })

        if holiday:

            return render_template(
                "admin/take_attendance.html",
                today=today_date,
                today_display=today_display,
                classes=classes_list,
                students=students,
                selected_class_id=selected_class_id,
                selected_class=selected_class,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Attendance cannot be marked on a holiday."
            )

        # --------------------------------
        # Prevent duplicate attendance
        # for same class/session/date
        # --------------------------------

        existing_attendance = db.attendance.find_one({
            "date": today_date,
            "session": session_type,
            "class_id": selected_class_id
        })

        if existing_attendance:

            return render_template(
                "admin/take_attendance.html",
                today=today_date,
                today_display=today_display,
                classes=classes_list,
                students=students,
                selected_class_id=selected_class_id,
                selected_class=selected_class,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error=(
                    "Attendance for this class and "
                    "session has already been marked."
                )
            )

        # --------------------------------
        # Create attendance records
        # --------------------------------

        attendance_records = []

        for student in students:

            student_id = student["student_id"]

            status = request.form.get(
                f"status_{student_id}",
                "Absent"
            )

            # Safety validation
            if status not in [
                "Present",
                "Absent"
            ]:
                status = "Absent"

            attendance_records.append({

                "student_id": student_id,

                "student_name": student["name"],

                "roll_no": student.get(
                    "roll_no"
                ),

                "faculty_id": "ADMIN",

                "class_id": selected_class_id,

                "date": today_date,

                "session": session_type,

                "status": status,

                "created_at": datetime.now()
            })

        # --------------------------------
        # Save attendance
        # --------------------------------

        if attendance_records:

            db.attendance.insert_many(
                attendance_records
            )

        # --------------------------------
        # Compare Noon + Afternoon
        # --------------------------------

        if session_type == "afternoon":

            noon_records = list(
                db.attendance.find({
                    "date": today_date,
                    "session": "noon",
                    "class_id": selected_class_id
                })
            )

            afternoon_records = list(
                db.attendance.find({
                    "date": today_date,
                    "session": "afternoon",
                    "class_id": selected_class_id
                })
            )

            noon_by_student = {
                record["student_id"]: record
                for record in noon_records
            }

            afternoon_by_student = {
                record["student_id"]: record
                for record in afternoon_records
            }

            for student_id, noon_record in noon_by_student.items():

                afternoon_record = (
                    afternoon_by_student.get(
                        student_id
                    )
                )

                if not afternoon_record:
                    continue

                noon_status_value = noon_record.get(
                    "status"
                )

                afternoon_status_value = (
                    afternoon_record.get("status")
                )

                # Present in both sessions
                if (
                    noon_status_value == "Present"
                    and afternoon_status_value == "Present"
                ):

                    attendance_type = "Present"

                # Absent at noon, present afternoon
                elif (
                    noon_status_value == "Absent"
                    and afternoon_status_value == "Present"
                ):

                    attendance_type = "Late Arrival"

                # Present at noon, absent afternoon
                elif (
                    noon_status_value == "Present"
                    and afternoon_status_value == "Absent"
                ):

                    attendance_type = "Left Midway"

                # Absent in both
                elif (
                    noon_status_value == "Absent"
                    and afternoon_status_value == "Absent"
                ):

                    attendance_type = "Absent Both Sessions"

                else:

                    attendance_type = "Waiting for Recheck"

                # Update afternoon record
                db.attendance.update_one(
                    {
                        "_id": afternoon_record["_id"]
                    },
                    {
                        "$set": {
                            "attendance_type":
                                attendance_type
                        }
                    }
                )

                # Update noon record
                db.attendance.update_one(
                    {
                        "_id": noon_record["_id"]
                    },
                    {
                        "$set": {
                            "attendance_type":
                                attendance_type
                        }
                    }
                )

                comparison_results[
                    student_id
                ] = attendance_type

        return redirect(
            url_for(
                "admin_take_attendance",
                class_id=selected_class_id
            )
        )

    # --------------------------------
    # Display page
    # --------------------------------

    return render_template(
        "admin/take_attendance.html",
        today=today_date,
        today_display=today_display,
        classes=classes_list,
        students=students,
        selected_class_id=selected_class_id,
        selected_class=selected_class,
        noon_status=noon_status,
        comparison_results=comparison_results
    )

@app.route("/faculty/students")
def faculty_students():

    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    faculty_id = session.get("faculty_id")

    # Get classes assigned to this faculty
    classes_list = list(
        db.classes.find({
            "teacher_id": faculty_id,
            "status": "active"
        })
    )

    # Get all active students
    students = list(
        db.students.find({
            "status": "active"
        }).sort("roll_no", 1)
    )

    return render_template(
        "faculty/students.html",
        students=students,
        classes_list=classes_list
    )
@app.route("/faculty/attendance", methods=["GET", "POST"])
def daily_attendance():

    if session.get("role") not in ["faculty", "admin"]:
        return redirect(url_for("login"))

    today_date = datetime.now().strftime("%Y-%m-%d")
    today_display = datetime.now().strftime("%d %B %Y")

    # Get all active students
    students = list(
        db.students.find({
            "status": "active"
        }).sort("roll_no", 1)
    )

    # Get today's noon attendance
    noon_attendance = list(
        db.attendance.find({
            "date": today_date,
            "session": "noon"
        })
    )

    noon_status = {
        record["student_id"]: record.get("status")
        for record in noon_attendance
    }
    # Get saved recheck results from afternoon attendance
    comparison_records = list(
         db.attendance.find({
             "date": today_date,
             "session": "afternoon",
             "attendance_type": {"$exists": True}
        })
    )

    comparison_results = {
         record["student_id"]: record.get("attendance_type")
         for record in comparison_records
    }
    
    if request.method == "POST":

        selected_date = request.form.get(
            "date",
            today_date
        )

        session_type = request.form.get(
            "session_type"
        )

        # Check session
        if session_type not in ["noon", "afternoon"]:
            return render_template(
                "faculty/attendance.html",
                today=today_date,
                today_display=today_display,
                students=students,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Please select a valid attendance session."
            )

        # Check date
        try:
            date_object = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            )
        except ValueError:

            return render_template(
                "faculty/attendance.html",
                today=today_date,
                today_display=today_display,
                students=students,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Invalid date format."
            )

        # Sunday check
        if date_object.weekday() == 6:

            return render_template(
                "faculty/attendance.html",
                today=today_date,
                today_display=today_display,
                students=students,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Attendance cannot be marked on Sunday."
            )

        # Holiday check
        holiday = db.holidays.find_one({
            "date": selected_date
        })

        if holiday:

            return render_template(
                "faculty/attendance.html",
                today=today_date,
                today_display=today_display,
                students=students,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error="Attendance cannot be marked on a holiday."
            )

        faculty_id = session.get("faculty_id")

        # Prevent duplicate attendance for same session
        existing_attendance = db.attendance.find_one({
            "date": selected_date,
            "session": session_type,
            "faculty_id": faculty_id
        })

        if existing_attendance:

            return render_template(
                "faculty/attendance.html",
                today=today_date,
                today_display=today_display,
                students=students,
                noon_status=noon_status,
                comparison_results=comparison_results,
                error=(
                    "Attendance for this session has "
                    "already been marked."
                )
            )

        attendance_records = []

        # Create attendance records
        for student in students:

            student_id = student["student_id"]

            status = request.form.get(
                f"status_{student_id}",
                "Absent"
            )

            attendance_records.append({

                "student_id": student_id,

                "student_name": student["name"],

                "roll_no": student["roll_no"],

                "faculty_id": faculty_id,

                "date": selected_date,

                "session": session_type,

                "status": status,

                "created_at": datetime.now()
            })

        # Save attendance
        if attendance_records:

            db.attendance.insert_many(
                attendance_records
            )

        # Compare noon and afternoon attendance
        if session_type == "afternoon":

            noon_records = list(
                db.attendance.find({
                    "date": selected_date,
                    "session": "noon"
                })
            )

            afternoon_records = list(
                db.attendance.find({
                    "date": selected_date,
                    "session": "afternoon"
                })
            )

            noon_by_student = {
                record["student_id"]: record
                for record in noon_records
            }

            afternoon_by_student = {
                record["student_id"]: record
                for record in afternoon_records
            }

            for student_id, noon_record in noon_by_student.items():

                afternoon_record = afternoon_by_student.get(
                    student_id
                )

                if not afternoon_record:
                    continue

                noon_status_value = noon_record.get("status")
                afternoon_status_value = afternoon_record.get("status")

                # Present in both sessions
                if (
                    noon_status_value == "Present"
                    and afternoon_status_value == "Present"
                ):
                    attendance_type = "Present"

                # Absent at noon, present in afternoon
                elif (
                    noon_status_value == "Absent"
                    and afternoon_status_value == "Present"
                ):
                    attendance_type = "Late Arrival"

                # Present at noon, absent in afternoon
                elif (
                    noon_status_value == "Present"
                    and afternoon_status_value == "Absent"
                ):
                    attendance_type = "Left Midway"

                # Absent in both sessions
                else:
                    attendance_type = "Absent Both Sessions"
                comparison_results[student_id] = attendance_type
                # Update afternoon record
                db.attendance.update_one(
                    {
                        "_id": afternoon_record["_id"]
                    },
                    {
                        "$set": {
                            "attendance_type": attendance_type
                        }
                    }
                )

                # Update noon record
                db.attendance.update_one(
                    {
                        "_id": noon_record["_id"]
                    },
                    {
                        "$set": {
                            "attendance_type": attendance_type
                        }
                    }
                )

        return redirect(
            url_for("daily_attendance")
        )

    return render_template(
         "faculty/attendance.html",
         today=today_date,
         today_display=today_display,
         students=students,
         noon_status=noon_status,
         comparison_results=comparison_results,
    )   
@app.route("/faculty/history")
def faculty_history():

    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    faculty_id = session.get("faculty_id")

    # Get logged-in faculty
    faculty_member = db.faculty.find_one({
        "faculty_id": faculty_id
    })

    if not faculty_member:
        return redirect(url_for("login"))

    # Classes assigned to this faculty
    assigned_class_ids = faculty_member.get(
        "assigned_classes",
        []
    )

    assigned_classes = list(
        db.classes.find({
            "class_id": {"$in": assigned_class_ids},
            "status": "active"
        }).sort([
            ("course", 1),
            ("semester", 1),
            ("division", 1)
        ])
    )

    # Selected filters
    selected_class_id = request.args.get(
        "class_id",
        ""
    ).strip()

    selected_date = request.args.get(
        "date",
        ""
    ).strip()

    # Base query
    query = {
        "faculty_id": faculty_id
    }

    # Class filter + security check
    if selected_class_id:

        if selected_class_id not in assigned_class_ids:
            return "You are not authorized to access this class.", 403

        query["class_id"] = selected_class_id

    # Date filter
    if selected_date:
        query["date"] = selected_date

    # Get attendance records
    attendance_records = list(
        db.attendance.find(query)
    )

    # --------------------------------------------------
    # Get student information for roll numbers
    # --------------------------------------------------

    student_ids = list({
        record.get("student_id")
        for record in attendance_records
        if record.get("student_id")
    })

    students = list(
        db.students.find({
            "student_id": {"$in": student_ids}
        })
    )

    student_details = {
        student.get("student_id"): student
        for student in students
    }

    # --------------------------------------------------
    # Combine Noon + Afternoon
    # One row per student per date
    # --------------------------------------------------

    daily_attendance = {}

    for record in attendance_records:

        student_id = record.get("student_id")
        date = record.get("date")
        key = (student_id, date)

        if key not in daily_attendance:

            student = student_details.get(
                student_id,
                {}
            )

            daily_attendance[key] = {
                "date": date,
                "student_id": student_id,
                "roll_no": student.get(
                    "roll_no",
                    record.get("roll_no", "")
                ),
                "student_name": student.get(
                    "name",
                    record.get("student_name", "")
                ),
                "noon": None,
                "afternoon": None,
                "attendance_type": None
            }

        # Noon attendance
        if record.get("session") == "noon":

            daily_attendance[key]["noon"] = (
                record.get("status")
            )

        # Afternoon attendance
        elif record.get("session") == "afternoon":

            daily_attendance[key]["afternoon"] = (
                record.get("status")
            )

    # --------------------------------------------------
    # Calculate final daily result
    # --------------------------------------------------

    attendance_history = []

    for record in daily_attendance.values():

        noon = record.get("noon")
        afternoon = record.get("afternoon")

        if noon == "Present" and afternoon == "Present":

            record["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon == "Present":

            record["attendance_type"] = "Late Arrival"

        elif noon == "Present" and afternoon == "Absent":

            record["attendance_type"] = "Left Midway"

        elif noon == "Absent" and afternoon == "Absent":

            record["attendance_type"] = "Absent Both Sessions"

        elif noon == "Present" and afternoon is None:

            record["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon is None:

            record["attendance_type"] = "Absent"

        else:

            record["attendance_type"] = "Waiting for Recheck"

        attendance_history.append(record)

    # --------------------------------------------------
    # Sort newest date first, then roll number
    # --------------------------------------------------

    def safe_roll_no(record):

        roll_no = record.get("roll_no")

        if roll_no is None or roll_no == "":
            return 999999

        try:
            return int(roll_no)
        except (ValueError, TypeError):
            return 999999

    attendance_history.sort(
        key=lambda record: (
            record.get("date") or "",
            safe_roll_no(record)
        ),
        reverse=True
    )

    return render_template(
        "faculty/history.html",
        attendance_history=attendance_history,
        assigned_classes=assigned_classes,
        selected_class_id=selected_class_id,
        selected_date=selected_date
    )

@app.route("/faculty/reports")
def faculty_reports():

    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    faculty_id = session.get("faculty_id")

    attendance_records = list(
        db.attendance.find({
            "faculty_id": faculty_id
        }).sort("date", -1)
    )

    total_records = len(attendance_records)

    present_count = sum(
        1 for record in attendance_records
        if record.get("status") == "Present"
    )

    absent_count = sum(
        1 for record in attendance_records
        if record.get("status") == "Absent"
    )

    attendance_percentage = (
        round((present_count / total_records) * 100, 2)
        if total_records > 0 else 0
    )

    return render_template(
        "faculty/report.html",
        attendance_records=attendance_records,
        total_records=total_records,
        present_count=present_count,
        absent_count=absent_count,
        attendance_percentage=attendance_percentage
    )
@app.route("/student/attendance")
def student_attendance():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    student_id = session.get("student_id")

    student = db.students.find_one({
        "student_id": student_id
    })

    if not student:
        return "Student record not found", 404

    attendance_records = list(
        db.attendance.find({
            "student_id": student_id
        }).sort("date", -1)
    )

    # Combine noon and afternoon records by date
    daily_attendance = {}

    for record in attendance_records:

        date = record.get("date")

        if date not in daily_attendance:
            daily_attendance[date] = {
                "date": date,
                "noon": None,
                "afternoon": None,
                "attendance_type": None
            }

        if record.get("session") == "noon":
            daily_attendance[date]["noon"] = record.get("status")

            # In case attendance_type was saved on noon record
            if record.get("attendance_type"):
                daily_attendance[date]["attendance_type"] = (
                    record.get("attendance_type")
                )

        elif record.get("session") == "afternoon":
            daily_attendance[date]["afternoon"] = record.get("status")

            if record.get("attendance_type"):
                daily_attendance[date]["attendance_type"] = (
                    record.get("attendance_type")
                )

    daily_attendance = list(daily_attendance.values())

    # Calculate attendance
    present_days = 0
    absent_days = 0

    for day in daily_attendance:

        noon = day.get("noon")
        afternoon = day.get("afternoon")

        # Present in both sessions
        if noon == "Present" and afternoon == "Present":
            present_days += 1

        # Present at noon, absent at afternoon
        elif noon == "Present" and afternoon == "Absent":
            present_days += 1

        # Absent at noon, present at afternoon
        elif noon == "Absent" and afternoon == "Present":
            present_days += 1

        # Absent in both sessions
        elif noon == "Absent" and afternoon == "Absent":
            absent_days += 1

        # Only noon has been marked
        elif noon == "Present" and afternoon is None:
            present_days += 1

        elif noon == "Absent" and afternoon is None:
            absent_days += 1

    # Only marked attendance days count
    total_days = present_days + absent_days

    attendance_percentage = (
        round((present_days / total_days) * 100, 2)
        if total_days > 0
        else 0
    )

    return render_template(
        "student/attendance.html",
        student=student,
        attendance_records=daily_attendance,
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        attendance_percentage=attendance_percentage
    )
@app.route("/admin/reports")
def admin_reports():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # --------------------------------
    # Get selected month, year and class
    # --------------------------------

    selected_month = request.args.get(
        "month",
        datetime.now().month,
        type=int
    )

    selected_year = request.args.get(
        "year",
        datetime.now().year,
        type=int
    )

    selected_class_id = request.args.get(
        "class_id",
        ""
    ).strip()

    search_student = request.args.get(
        "search",
        ""
    ).strip()

    # --------------------------------
    # Get active classes
    # --------------------------------

    classes_list = list(
        db.classes.find({
            "status": "active"
        }).sort([
            ("course", 1),
            ("semester", 1),
            ("division", 1)
        ])
    )

    # --------------------------------
    # Attendance filter
    # --------------------------------

    attendance_filter = {}

    if selected_class_id:

        attendance_filter["class_id"] = selected_class_id

    # --------------------------------
    # Get attendance records
    # --------------------------------

    attendance_records = list(
        db.attendance.find(
            attendance_filter
        ).sort([
            ("date", -1),
            ("roll_no", 1)
        ])
    )

    # --------------------------------
    # Combine noon + afternoon
    # into one record per student/date
    # --------------------------------

    daily_attendance = {}

    for record in attendance_records:

        student_id = record.get("student_id")
        date = record.get("date")

        # --------------------------------
        # Convert date into datetime
        # --------------------------------

        record_date = None

        if isinstance(date, datetime):

            record_date = date

        elif isinstance(date, str):

            try:

                record_date = datetime.strptime(
                    date,
                    "%Y-%m-%d"
                )

            except ValueError:

                try:

                    record_date = datetime.strptime(
                        date,
                        "%d-%m-%Y"
                    )

                except ValueError:

                    continue

        # Skip invalid dates
        if record_date is None:
            continue

        # --------------------------------
        # MONTH + YEAR FILTER
        # --------------------------------

        if (
            record_date.month != selected_month
            or record_date.year != selected_year
        ):
            continue

        key = (
            student_id,
            record_date.strftime("%Y-%m-%d")
        )

        if key not in daily_attendance:

            daily_attendance[key] = {

                "student_id": student_id,

                "student_name": record.get(
                    "student_name"
                ),

                "roll_no": record.get(
                    "roll_no"
                ),

                "class_id": record.get(
                    "class_id"
                ),

                "date": record_date.strftime(
                    "%Y-%m-%d"
                ),

                "noon": None,

                "afternoon": None,

                "attendance_type": None
            }

        # --------------------------------
        # Noon attendance
        # --------------------------------

        if record.get("session") == "noon":

            daily_attendance[key]["noon"] = (
                record.get("status")
            )

        # --------------------------------
        # Afternoon attendance
        # --------------------------------

        elif record.get("session") == "afternoon":

            daily_attendance[key]["afternoon"] = (
                record.get("status")
            )

    # --------------------------------
    # Determine final daily result
    # --------------------------------

    daily_records = []

    for record in daily_attendance.values():

        noon = record.get("noon")
        afternoon = record.get("afternoon")

        if noon == "Present" and afternoon == "Present":

            record["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon == "Present":

            record["attendance_type"] = "Late Arrival"

        elif noon == "Present" and afternoon == "Absent":

            record["attendance_type"] = "Left Midway"

        elif noon == "Absent" and afternoon == "Absent":

            record["attendance_type"] = "Absent Both Sessions"

        elif noon == "Present" and afternoon is None:

            record["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon is None:

            record["attendance_type"] = "Absent Both Sessions"

        else:

            record["attendance_type"] = "Waiting for Recheck"

        daily_records.append(record)

    # --------------------------------
    # Overall statistics
    # --------------------------------

    total_records = len(daily_records)

    present_count = 0
    absent_count = 0

    for record in daily_records:

        result = record.get(
            "attendance_type"
        )

        if result in [
            "Present",
            "Late Arrival",
            "Left Midway"
        ]:

            present_count += 1

        elif result == "Absent Both Sessions":

            absent_count += 1

    marked_days = present_count + absent_count

    attendance_percentage = (

        round(
            (present_count / marked_days) * 100,
            2
        )

        if marked_days > 0

        else 0
    )

    # --------------------------------
    # Student-wise monthly report
    # --------------------------------

    student_report = {}

    for record in daily_records:

        student_id = record.get(
            "student_id"
        )

        if student_id not in student_report:

            student_report[student_id] = {

                "student_id": student_id,

                "student_name": record.get(
                    "student_name"
                ),

                "roll_no": record.get(
                    "roll_no"
                ),

                "total": 0,

                "present": 0,

                "late": 0,

                "absent": 0
            }

        result = record.get(
            "attendance_type"
        )

        # --------------------------------
        # Present
        # --------------------------------

        if result == "Present":

            student_report[student_id][
                "present"
            ] += 1

            student_report[student_id][
                "total"
            ] += 1

        # --------------------------------
        # Late Arrival
        # --------------------------------

        elif result == "Late Arrival":

            student_report[student_id][
                "late"
            ] += 1

            student_report[student_id][
                "present"
            ] += 1

            student_report[student_id][
                "total"
            ] += 1

        # --------------------------------
        # Left Midway
        # --------------------------------

        elif result == "Left Midway":

            student_report[student_id][
                "present"
            ] += 1

            student_report[student_id][
                "total"
            ] += 1

        # --------------------------------
        # Absent
        # --------------------------------

        elif result == "Absent Both Sessions":

            student_report[student_id][
                "absent"
            ] += 1

            student_report[student_id][
                "total"
            ] += 1

    # --------------------------------
    # Calculate percentage
    # --------------------------------

    for student in student_report.values():

        total = student["total"]

        present = student["present"]

        student["percentage"] = (

            round(
                (present / total) * 100,
                2
            )

            if total > 0

            else 0
        )

    # --------------------------------
    # Convert dictionary to list
    # --------------------------------

    student_report = list(
        student_report.values()
    )

    # --------------------------------
    # Search student
    # --------------------------------

    if search_student:

        search_lower = search_student.lower()

        student_report = [

            student

            for student in student_report

            if search_lower in str(
                student.get("student_id", "")
            ).lower()

            or search_lower in str(
                student.get("student_name", "")
            ).lower()

            or search_lower in str(
                student.get("roll_no", "")
            ).lower()
        ]

    # --------------------------------
    # Sort by roll number
    # --------------------------------

    student_report.sort(
        key=lambda x: (
            x.get("roll_no")
            if x.get("roll_no") is not None
            else 0
        )
    )

    # --------------------------------
    # Send data to template
    # --------------------------------

    return render_template(
        "admin/reports.html",

        total_records=total_records,

        present_count=present_count,

        absent_count=absent_count,

        attendance_percentage=attendance_percentage,

        student_report=student_report,

        selected_month=selected_month,

        selected_year=selected_year,

        selected_class_id=selected_class_id,

        classes=classes_list,

        search_student=search_student
    )
@app.route("/admin/reports/download")
def admin_reports_download():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    selected_month = request.args.get(
        "month",
        datetime.now().month,
        type=int
    )

    selected_year = request.args.get(
        "year",
        datetime.now().year,
        type=int
    )

    selected_class_id = request.args.get(
        "class_id",
        ""
    ).strip()

    # --------------------------------
    # Attendance filter
    # --------------------------------

    attendance_filter = {}

    if selected_class_id:
        attendance_filter["class_id"] = selected_class_id

    # --------------------------------
    # Get attendance records
    # --------------------------------

    attendance_records = list(
        db.attendance.find(attendance_filter)
    )

    # --------------------------------
    # Get students
    # --------------------------------

    student_filter = {
        "status": "active"
    }

    if selected_class_id:
        student_filter["class_id"] = selected_class_id

    students = list(
        db.students.find(student_filter)
    )

    student_report = {}

    for student in students:

        student_id = student.get("student_id")

        student_report[student_id] = {
            "student_id": student_id,
            "student_name": student.get("name", ""),
            "present": 0,
            "late": 0,
            "absent": 0,
            "working_days": 0
        }

    # --------------------------------
    # Group attendance by
    # student + date
    # --------------------------------

    daily_attendance = {}

    for record in attendance_records:

        student_id = record.get("student_id")

        if student_id not in student_report:
            continue

        attendance_date = record.get("date")

        if not attendance_date:
            continue

        try:

            if isinstance(
                attendance_date,
                datetime
            ):

                record_date = attendance_date

            else:

                record_date = datetime.strptime(
                    str(attendance_date)[:10],
                    "%Y-%m-%d"
                )

        except (ValueError, TypeError):

            continue

        # --------------------------------
        # Month + Year filter
        # --------------------------------

        if (
            record_date.month != selected_month
            or record_date.year != selected_year
        ):
            continue

        key = (
            student_id,
            record_date.strftime("%Y-%m-%d")
        )

        if key not in daily_attendance:

            daily_attendance[key] = {
                "noon": None,
                "afternoon": None
            }

        session_name = str(
            record.get("session", "")
        ).lower()

        status = record.get("status")

        if "noon" in session_name:

            daily_attendance[key]["noon"] = status

        elif "afternoon" in session_name:

            daily_attendance[key]["afternoon"] = status

    # --------------------------------
    # Calculate monthly summary
    # --------------------------------

    for (
        student_id,
        date
    ), sessions in daily_attendance.items():

        noon = sessions["noon"]
        afternoon = sessions["afternoon"]

        student_report[
            student_id
        ]["working_days"] += 1

        if (
            noon == "Present"
            and afternoon == "Present"
        ):

            student_report[
                student_id
            ]["present"] += 1

        elif (
            noon == "Absent"
            and afternoon == "Present"
        ):

            student_report[
                student_id
            ]["late"] += 1

        elif (
            noon == "Present"
            and afternoon == "Absent"
        ):

            student_report[
                student_id
            ]["present"] += 1

        elif (
            noon == "Absent"
            and afternoon == "Absent"
        ):

            student_report[
                student_id
            ]["absent"] += 1

        elif (
            noon == "Present"
            and afternoon is None
        ):

            student_report[
                student_id
            ]["present"] += 1

        elif (
            noon == "Absent"
            and afternoon is None
        ):

            student_report[
                student_id
            ]["absent"] += 1

    # --------------------------------
    # Create Excel workbook
    # --------------------------------

    workbook = Workbook()

    worksheet = workbook.active

    worksheet.title = "Monthly Summary"

    # --------------------------------
    # Headers
    # --------------------------------

    headers = [
        "Student ID",
        "Student Name",
        "Present",
        "Late",
        "Absent",
        "Working Days",
        "Attendance %"
    ]

    worksheet.append(headers)

    # --------------------------------
    # Add student data
    # --------------------------------

    for student in student_report.values():

        working_days = student[
            "working_days"
        ]

        attended_days = (
            student["present"]
            + student["late"]
        )

        if working_days > 0:

            percentage = (
                attended_days
                / working_days
            ) * 100

        else:

            percentage = 0

        worksheet.append([
            student["student_id"],
            student["student_name"],
            student["present"],
            student["late"],
            student["absent"],
            working_days,
            round(percentage, 2)
        ])

    # --------------------------------
    # Column widths
    # --------------------------------

    worksheet.column_dimensions[
        "A"
    ].width = 15

    worksheet.column_dimensions[
        "B"
    ].width = 25

    worksheet.column_dimensions[
        "C"
    ].width = 12

    worksheet.column_dimensions[
        "D"
    ].width = 12

    worksheet.column_dimensions[
        "E"
    ].width = 12

    worksheet.column_dimensions[
        "F"
    ].width = 15

    worksheet.column_dimensions[
        "G"
    ].width = 15

    # --------------------------------
    # Send Excel file
    # --------------------------------

    output = BytesIO()

    workbook.save(output)

    output.seek(0)

    # --------------------------------
    # Filename
    # --------------------------------

    if selected_class_id:

        filename = (
            f"Monthly_Attendance_"
            f"{selected_class_id}_"
            f"{selected_year}_"
            f"{selected_month:02d}.xlsx"
        )

    else:

        filename = (
            f"Monthly_Attendance_"
            f"{selected_year}_"
            f"{selected_month:02d}.xlsx"
        )

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
@app.route("/student/history")
def student_history():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    student_id = session.get("student_id")

    # --------------------------------
    # Get student
    # --------------------------------

    student = db.students.find_one({
        "student_id": student_id
    })

    if not student:
        return "Student record not found", 404

    # --------------------------------
    # Get attendance records
    # --------------------------------

    attendance_records = list(
        db.attendance.find({
            "student_id": student_id
        }).sort("date", -1)
    )

    # --------------------------------
    # Combine noon + afternoon
    # --------------------------------

    daily_attendance = {}

    for record in attendance_records:

        date = record.get("date")

        if date not in daily_attendance:

            daily_attendance[date] = {
                "date": date,
                "noon": None,
                "afternoon": None,
                "attendance_type": None
            }

        # Noon attendance

        if record.get("session") == "noon":

            daily_attendance[date]["noon"] = (
                record.get("status")
            )

        # Afternoon attendance

        elif record.get("session") == "afternoon":

            daily_attendance[date]["afternoon"] = (
                record.get("status")
            )

    # --------------------------------
    # Determine final result
    # --------------------------------

    history_records = []

    for day in daily_attendance.values():

        noon = day.get("noon")
        afternoon = day.get("afternoon")

        if noon == "Present" and afternoon == "Present":

            day["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon == "Present":

            day["attendance_type"] = "Late Arrival"

        elif noon == "Present" and afternoon == "Absent":

            day["attendance_type"] = "Left Midway"

        elif noon == "Absent" and afternoon == "Absent":

            day["attendance_type"] = "Absent Both Sessions"

        elif noon == "Present" and afternoon is None:

            day["attendance_type"] = "Present"

        elif noon == "Absent" and afternoon is None:

            day["attendance_type"] = "Absent Both Sessions"

        else:

            day["attendance_type"] = "Waiting for Recheck"

        history_records.append(day)

    # --------------------------------
    # Sort newest date first
    # --------------------------------

    history_records.sort(
        key=lambda x: x.get("date", ""),
        reverse=True
    )

    # --------------------------------
    # Calculate statistics
    # --------------------------------

    total_days = 0
    present_days = 0
    absent_days = 0

    for record in history_records:

        result = record.get("attendance_type")

        if result in [
            "Present",
            "Late Arrival",
            "Left Midway"
        ]:

            present_days += 1
            total_days += 1

        elif result == "Absent Both Sessions":

            absent_days += 1
            total_days += 1

    attendance_percentage = (
        round(
            (present_days / total_days) * 100,
            2
        )
        if total_days > 0
        else 0
    )

    # --------------------------------
    # Render history page
    # --------------------------------

    return render_template(
        "student/history.html",

        student=student,

        attendance_records=history_records,

        total_days=total_days,

        present_days=present_days,

        absent_days=absent_days,

        attendance_percentage=attendance_percentage
    )
if __name__ == "__main__":
    app.run(debug=True)