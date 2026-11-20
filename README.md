# College_attendance_system
# 🎓 College Attendance Management System

A web-based **College Attendance Management System** built using Python, Flask, MongoDB Atlas, HTML, CSS, Bootstrap, and JavaScript. The system simplifies daily attendance management for administrators and faculty while providing attendance records and reports.

The system supports role-based access for Admin and Faculty, class-wise attendance, two-session attendance tracking, monthly reports, and Excel export.

## 🌐 Live Demo

**Live Application:** https://collegeattendancesystem-eight.vercel.app

## ✨ Features

### 👨‍💼 Admin Dashboard
- Dashboard overview with total students, faculty, and classes.
- Today's attendance summary.
- Student management.
- Faculty management.
- Class management.
- Holiday management.
- Take attendance for different classes.
- View attendance reports.
- Monthly attendance reports.

### 👨‍🏫 Faculty Dashboard
- Faculty dashboard with attendance overview.
- Access assigned classes.
- Take attendance for assigned classes.
- Mark attendance for noon and afternoon sessions.
- View attendance history.
- View class-wise reports.

### 📝 Two-Session Attendance System

Attendance is recorded in two sessions each day:

- **Noon Session:** First attendance check.
- **Afternoon Session:** Final recheck.

The system compares both sessions and automatically determines the student's final attendance status.

| Noon | Afternoon | Final Result |
|---|---|---|
| Present | Present | Present |
| Absent | Present | Late Arrival |
| Present | Absent | Left Midway |
| Absent | Absent | Absent Both Sessions |
| Present | Not marked | Present |
| Absent | Not marked | Absent |

### 📊 Attendance Reports
- Daily attendance report.
- Class-wise attendance filtering.
- Student search.
- Date-wise filtering.
- Present and absent statistics.
- Attendance percentage calculation.

### 📅 Monthly Attendance Reports
- Month-wise attendance records.
- Year and class filters.
- Student-wise attendance summaries.
- Present, late, and absent counts.
- Working days.
- Attendance percentage.
- Excel report download.

### 👥 Student Management
- Add and manage students.
- Student ID generation.
- Class assignment.
- Student records and attendance tracking.

### 🏫 Class Management
- Manage multiple courses and classes.
- Semester management.
- Division management.
- Academic year management.

### 📆 Holiday Management
- Admin can manage college holidays.
- Attendance cannot be marked on holidays.
- Sunday is automatically treated as a holiday.

### 🔐 Authentication & Access Control
- Login system.
- Role-based access control.
- Separate Admin and Faculty interfaces.
- Faculty access restricted to assigned classes.

### 📱 Responsive Interface
- Responsive layout for desktop, tablet, and mobile screens.
- Mobile-friendly attendance marking.
- Easy-to-use navigation and dashboard interface.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web framework |
| MongoDB Atlas | Cloud database |
| HTML5 | Structure |
| CSS3 | Styling |
| Bootstrap | Responsive UI |
| JavaScript | Interactive features |
| Jinja2 | Template rendering |
| Openpyxl | Excel report generation |
| Git & GitHub | Version control |
| Vercel | Deployment |

---

## 🏗️ System Architecture

```text
                  Users
        ┌──────────┼──────────┐
        │          │          │
      Admin      Faculty    Students*
        │          │          │
        └──────────┼──────────┘
                   │
             Web Interface
          HTML / CSS / Bootstrap
             JavaScript
                   │
                   ▼
             Flask Backend
           Python Application
                   │
                   ▼
             MongoDB Atlas
          Cloud Database Storage
```

*Student interface availability depends on the implemented modules.*

---

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Saniya-khan26/College_attendance_system.git
```

### 2. Navigate to the Project Folder

```bash
cd College_attendance_system
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

### 4. Activate the Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your_secret_key
MONGO_URI=your_mongodb_connection_string
```

Replace the values with your own credentials. Never upload your real `.env` file or database credentials to GitHub.

### 7. Run the Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

---

## 📁 Project Structure

```text
College_Attendance_System/
│
├── app.py
├── requirements.txt
├── .env
│
├── templates/
│   ├── admin/
│   ├── faculty/
│   └── ...
│
├── static/
│   ├── css/
│   ├── js/
│   └── ...
│
└── README.md
```

*The structure above is a simplified overview.*

---

## 📈 Future Enhancements

- Android application.
- Push notifications and attendance reminders.
- Student self-service attendance dashboard.
- QR-based attendance.
- Advanced analytics and visualizations.
- Improved attendance insights.

---

## 👩‍💻 Developed By

**Saniya Khan**  
BCA Student | Aspiring Software Developer

- GitHub: [Saniya-khan26](https://github.com/Saniya-khan26)
- LinkedIn: [Saniya Khan](https://www.linkedin.com/in/saniya-khan-300044352/)

---

## 🤝 Contributing

Suggestions, improvements, and contributions are welcome. Feel free to fork this repository and submit a pull request.

---

## 📄 License

This project was developed for educational and learning purposes. You may add an appropriate open-source license if you wish to allow reuse and contributions.

---

⭐ If you find this project interesting, consider giving the repository a star!

