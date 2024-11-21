from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField, DecimalField
from wtforms.validators import DataRequired, Length, Email, NumberRange
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bank.db"
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref=db.backref("accounts", lazy=True))


class RegistrationForm(FlaskForm):
    username = StringField(
        "User name", validators=[DataRequired(), Length(min=2, max=20)]
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    initial_deposit = DecimalField("Initial Deposit", validators=[DataRequired()])
    submit = SubmitField("Sign Up")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class TransferForm(FlaskForm):
    to_account = StringField("To Account", validators=[DataRequired()])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField("Transfer")


class DepositForm(FlaskForm):
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField("Deposit")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/reset_db")
def reset_db():
    db.drop_all()
    db.create_all()
    flash("Database reset successfully!", "success")
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
        )
        db.session.add(user)
        db.session.commit()

        # Create account with initial deposit
        account = Account(
            name=form.username.data, balance=form.initial_deposit.data, user_id=user.id
        )
        db.session.add(account)
        db.session.commit()

        flash("Account created successfully!", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.password == form.password.data:
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", accounts=accounts)


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    form = TransferForm()
    if form.validate_on_submit():
        from_account = Account.query.filter_by(user_id=current_user.id).first()
        to_account = Account.query.filter_by(name=form.to_account.data).first()
        amount = float(form.amount.data)
        if from_account and to_account and from_account.balance >= amount:
            from_account.balance -= amount
            to_account.balance += amount
            db.session.commit()
            flash(
                "Transfer successful!"
                + ""
                + "Your account balance is "
                + str(from_account.balance),
                "success",
            )
        else:
            flash("Transfer failed. Check account details and balance.", "danger")
    return render_template("transfer.html", form=form)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    form = DepositForm()
    if form.validate_on_submit():
        amount = float(form.amount.data)
        account = Account.query.filter_by(
            user_id=current_user.id
        ).first()  # 確保從資料庫中獲取最新的帳戶物件
        if account:
            account.balance += amount
            db.session.commit()
            flash(
                "Deposit successful!"
                + ""
                + "Your account balance is "
                + str(account.balance),
                "success",
            )
            return redirect(url_for("deposit"))
        else:
            flash("Account not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("deposit.html", form=form)


@app.route("/api/accounts", methods=["GET"])
def get_accounts():
    accounts = Account.query.all()
    return jsonify(
        [
            {"id": account.id, "name": account.name, "balance": account.balance}
            for account in accounts
        ]
    )


@app.route("/api/transfer", methods=["POST"])
def api_transfer():
    data = request.get_json()
    from_account = Account.query.filter_by(name=data["from_account"]).first()
    to_account = Account.query.filter_by(name=data["to_account"]).first()
    amount = data["amount"]
    if from_account and to_account and from_account.balance >= amount:
        from_account.balance -= amount
        to_account.balance += amount
        db.session.commit()
        return jsonify({"message": "Transfer successful"}), 200
    return jsonify({"message": "Transfer failed"}), 400


@app.route("/api/deposit", methods=["POST"])
def api_deposit():
    data = request.get_json()
    account = Account.query.filter_by(name=data["account"]).first()
    amount = data["amount"]
    if account:
        account.balance += amount
        db.session.commit()
        return jsonify({"message": "Deposit successful"}), 200
    return jsonify({"message": "Deposit failed"}), 400


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
