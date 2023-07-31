from flask import Flask, flash, redirect, request, render_template, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime

app = Flask(__name__)
db = SQLAlchemy()

# Database setup
app.config["SQLALCHEMY_DATABASE_URI"]  = "sqlite:///project.db"
db.init_app(app)

# Login Manager
app.config["SECRET_KEY"] = "appsecretkey"
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# Models
class User(db.Model, UserMixin):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(60), nullable=False)
    user_role = db.Column(db.String(50), nullable=False, default="Employee")
    manager_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))

    def __repr__(self):
        return self.user_id
    
    def get_id(self):
        return self.user_id

    def to_dict(self):
        hash_map = dict({
            "userId": self.user_id,
            "password": self.password,
            "userType": self.user_type,
            "managerId": self.manager_id
        })
        return json.dumps(hash_map, sort_keys=True, default=str)
    
class Task(db.Model):
   __tablename__ = "tasks"
   task_no = db.Column(db.Integer, primary_key = True)
   task = db.Column(db.String, nullable = True)
   created_date = db.Column(db.DateTime, default = datetime.now(), nullable = False)
   due_date = db.Column(db.DateTime)
   status = db.Column(db.String, default = "In Progress", nullable = False)
   assignee_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
   assignor_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))

   def __repr__(self):
       return self.task

with app.app_context():
   db.create_all() 

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register")
def register():
    return render_template("register.html") 

@app.route("/register", methods=["POST"])
def register_post():
    user_id = request.form.get("id")
    password = request.form.get("password")
    user_role = request.form.get("role")
    manager_id = request.form.get("manager_id")

    user = User.query.filter_by(user_id=user_id).first()

    if user:
        flash("User already exists")
        return redirect(url_for("register"))
    
    new_user = User(
        user_id = user_id,
        password = generate_password_hash(password, method="sha256"),
        user_role = user_role,
        manager_id = manager_id
    )
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user)
    return redirect(url_for("home"))

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    user_id = request.form.get("id")
    password = request.form.get("password")
    remember = True if request.form.get("remember") else False

    user = User.query.filter_by(user_id=user_id).first()

    if not user or not check_password_hash(user.password, password):
        flash("Please check your login details and try again")
        return redirect(url_for("login"))

    login_user(user, remember=remember)

    return redirect(url_for("profile"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))
    
@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user) 

@app.route("/subordinate")
@login_required
def subordinate_assign():
    users = User.query.filter_by(user_role="Employee").all()
    return render_template("subordinate.html", users=users)

@app.route("/subordinate/<int:user_id>/assign")
@login_required
def subordinate(user_id):
    user = User.query.get(user_id)
    user.manager_id = current_user.user_id
    db.session.commit()
    return redirect(url_for("subordinate_assign"))

def init(): 
    manager_user = User.query.filter_by(user_id=101).first()
    employee_user = User.query.filter_by(user_id=1).first()
    if not manager_user:
        manager_user = User(
            user_id = 101,
            password = generate_password_hash("pass", method="sha256"), 
            user_role = "Manager",
            manager_id = None
        )
        db.session.add(manager_user)
    if not employee_user:
        employee_user = User(
            user_id = 1,
            password = generate_password_hash("pass", method="sha256"),
            user_role = "Employee",
            manager_id = 101
        )
        db.session.add(employee_user)
    db.session.commit()
    return {"message": "Initialization successful"}, 201

# Task section
@app.route("/tasks") 
def tasks():
    tasks = Task.query.order_by(Task.task_no)
    if current_user.user_role == "Employee":
        tasks = tasks.filter_by(assignee_id = current_user.user_id)

    if current_user.user_role == "Manager":
        tasks = tasks.filter_by(assignor_id = current_user.user_id)

    filter_map = {
        "1": "Completed",
        "2": "In Progress"
    }
    filter = request.args.get("filter")
    if filter_map.get(filter):
        tasks = tasks.filter_by(status=filter_map[filter])
    tasks = tasks.all()
    return render_template("task/list.html", tasks=tasks)

@app.route("/task/create", methods=["GET", "POST"])
def create_task():
    if request.method == "POST":
        task = Task(
            task = request.form["task"],
            due_date = datetime.strptime(request.form["due"], '%Y-%m-%d'),
            status = request.form["status"],
            assignee_id = request.form["assignee"],
            assignor_id = current_user.user_id
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for("task", task_no=task.task_no))
    if current_user.user_role != "Manager":
        flash("You are not authorized to create a task")
        return redirect(url_for("tasks"))
    # Get a list of subordinates 
    subordinates = User.query.filter_by(manager_id=current_user.user_id)
    subordinates = [subordinate.user_id for subordinate in subordinates]
    print(subordinates)
    return render_template("task/create.html", subordinates=subordinates)

@app.route("/task/<int:task_no>")
def task(task_no):
    task = db.get_or_404(Task, task_no)
    return render_template("task/detail.html", task=task)

@app.route("/task/<int:task_no>/edit", methods=["GET", "POST"])
def edit_task(task_no):
    task = db.get_or_404(Task, task_no)
    if request.method == "POST":
        task.task = request.form["task"]
        task.due_date = datetime.strptime(request.form["due"], '%Y-%m-%d')
        task.status = request.form["status"]
        db.session.commit()
        return redirect(url_for("task", task_no=task.task_no))
    if current_user.user_role != "Manager":
        flash("You are not authorized to edit a task")
        return redirect(url_for("tasks"))
    return render_template("task/edit.html", task=task)

@app.route("/task/<int:task_no>/status")
def toggle_status(task_no):
    task = db.get_or_404(Task, task_no)
    task.status = "Completed" if task.status == "In Progress" else "In Progress"
    db.session.commit()
    return redirect("/tasks")

@app.route("/task/<int:task_no>/delete")
def delete_task(task_no):
    if current_user.user_role != "Manager":
        flash("You are not authorized to delete a task")
        return redirect(url_for("tasks"))
    task = db.get_or_404(Task, task_no)
    db.session.delete(task)
    db.session.commit()
    return redirect("/tasks")