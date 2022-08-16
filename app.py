import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# export API_KEY=pk_f4bf9f7b2c4d441f8535ad589e521722

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
#db = SQL("sqlite:///finance.db")
uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():

    user_id = session['user_id']
    username = db.execute("SELECT username FROM users WHERE id = ?", user_id)
    name = username[0]["username"]
    cash = db.execute("SELECT cash FROM users WHERE username =?", name)[0]["cash"]
    # if empty prtoflio
    if len(db.execute("SELECT * FROM portfolio WHERE username = ?", name)) < 1:
        return render_template("index_empty.html")

    else:
        sum = db.execute("SELECT SUM(price) AS sum FROM portfolio WHERE username =?", name)[0]["sum"]
        total = sum + cash
        return render_template("index.html", users=db.execute("SELECT * FROM portfolio WHERE username = ?", name), name=name, cash=cash, sum=sum, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    user_id = session['user_id']
    wallet = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = wallet[0]["cash"]
    if request.method == "GET":
        return render_template("buy.html")

    else:

        username = db.execute("SELECT username FROM users WHERE id = ?", user_id)
        name = username[0]["username"]

        if (lookup(request.form.get("symbol")) == None):
            return apology("company doesn't exist", 400)
        else:
            symbol = lookup(request.form.get("symbol"))["symbol"]
            company = lookup(request.form.get("symbol"))["name"]

            shares = request.form.get("shares", type=int)

            if (isinstance(shares, int) != True):
                return apology("invalid purchase: share must be integer", 400)

            elif (shares < 0):
                return apology("invalid purchase: share must a be positive number", 400)

        price = lookup(request.form.get("symbol"))["price"] * float(request.form.get("shares"))

        print(usd(price))

        remain = cash - price

        if (lookup(request.form.get("symbol"))["price"] * shares > remain):
            return apology("don't have enough money", 400)

        else:
            # update portfolio
            if len(db.execute("SELECT * FROM portfolio WHERE stock = ? AND username = ?", symbol, name)) >= 1:
                sum_shares = (db.execute("SELECT share FROM portfolio WHERE username = ?", name)[0]["share"] + shares)
                sum_price = (db.execute("SELECT price FROM portfolio WHERE username = ?", name)[0]["price"] + price)

                db.execute("UPDATE portfolio SET share = ?, price = ? WHERE username = ? AND stock =?",sum_shares, sum_price, name, symbol)

            else:
                db.execute("INSERT INTO portfolio(username, stock, company, share, price) VALUES(?,?,?,?,?)", name, symbol, company, shares, price)

            #update histroy table
            db.execute("INSERT INTO history(username, stock, share, price, transaction_type, remain) VALUES(?, ?, ?, ?, 'buy', ?)",
            name, symbol, shares, price, remain)
            # updates total cash
            db.execute("UPDATE users SET cash = ? WHERE username = ?", remain, name)
            return redirect("/")


@app.route("/history")
@login_required
def history():

    user_id = session['user_id']
    username = db.execute("SELECT username FROM users WHERE id = ?", user_id)
    name = username[0]["username"]
    cash = db.execute("SELECT cash FROM users")[0]["cash"]

    if len(db.execute("SELECT * FROM history WHERE username = ?", name)) < 1:

        return render_template("history_empty.html")

    else:
        total = db.execute("SELECT SUM(price) AS total FROM history WHERE username =?", name)[0]["total"] + cash

        return render_template("history.html", users = db.execute("SELECT *, SUM(price) OVER (ORDER BY history.id) AS sum FROM history JOIN users ON history.username = users.username WHERE users.username = ?", name), cash=cash, total=total)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

    else:
        stock = request.form.get("symbol")
        if (lookup(stock) == None):
            return apology("the stock does not exist", 400)

        else:
            print(type(lookup(stock)["price"]))
            return render_template("quoted.html", name=lookup(stock)["name"], price=lookup(stock)["price"], symbol=lookup(stock)["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # user thru GET
    # direct to a register.html
    # ask the user to submit their user name password and retyple password
    if request.method == "GET":
        return render_template("register.html")

    # user thru POST
    # check possible errors
    else:
        # confirmation = generate_password_hash(request.form.get("confirmation"), method='pbkdf2:sha1', salt_length=8)
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure username is not taken
        elif len(db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))) >= 1:
            return apology("username has already been taken", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must confirm your password", 400)

        # Ensure password match configuration
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation doesn't match with password", 400)

        # log the user in
        else:
            username = request.form.get("username")
            password = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", username, password)
            session["user_id"] = db.execute("SELECT id FROM users WHERE username = ?", username)[0]["id"]
            return redirect("/")

    # return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    user_id = session['user_id']
    wallet = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = wallet[0]["cash"]
    username = db.execute("SELECT username FROM users WHERE id = ?", user_id)
    name = username[0]["username"]

    if request.method == "GET":
        return render_template("sell.html", stocks=db.execute("SELECT stock FROM portfolio WHERE username =?", name))

    else:

        if (len(db.execute("SELECT * FROM portfolio WHERE username = ?", name)) < 1):
            return render_template("sell_empty.html")

        elif (lookup(request.form.get("symbol")) == None):
            return apology("company doesn't exist", 403)

        else:
            symbol = lookup(request.form.get("symbol"))["symbol"]
            company = lookup(request.form.get("symbol"))["name"]
            shares = request.form.get("shares", type=int)

        if(isinstance(shares, int) != True):
            return apology("invalid shares: not integer", 400)

        elif (shares < 0):
            return apology("invalid shares: negative", 400)

        elif (shares > db.execute("SELECT share FROM portfolio WHERE stock =? AND username = ?", symbol, name)[0]["share"]):
            return apology("can't sell more than you own", 400)

        else:

            price = lookup(request.form.get("symbol"))["price"] * float(request.form.get("shares"))
            remain = cash + price
            # update portfolio

            sum_share = (db.execute("SELECT share FROM portfolio WHERE username = ? AND stock = ?", name, symbol)[0]["share"] - shares)
            sum_price = (db.execute("SELECT price FROM portfolio WHERE username = ?", name)[0]["price"] - price)

            # delete if sell all shares
            if (shares == db.execute("SELECT share FROM portfolio WHERE stock =? AND username = ?", symbol, name)[0]["share"]):
                db.execute("DELETE FROM portfolio WHERE stock = ? AND username = ?", symbol, name)

            else:
                db.execute("UPDATE portfolio SET share = ?, price = ? WHERE username = ? AND stock =?",
                sum_share, sum_price, name, symbol)

            #update histroy table
            db.execute("INSERT INTO history(username, stock, share, price, transaction_type, remain) VALUES(?, ?, ?, ?, 'sell', ?)", name, symbol, shares, price, remain)
            #updates total cash
            db.execute("UPDATE users SET cash = ? WHERE username = ?", remain, name)

            return redirect("/")

