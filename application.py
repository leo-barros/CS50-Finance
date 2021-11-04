import os
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime,date

from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SECRET_KEY"] = 'TPmi4aLWRbyVq8zu9v82dWYW1'
# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use POSTGRES database
db = SQL(os.getenv("DATABASE_URI"))

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    current_price={}
    response={}
    total={}
    query= db.execute("SELECT userid,symbol,name,quantity FROM holdings WHERE userid=:userid ",userid=session["user_id"])
    cashq= db.execute("SELECT cash FROM users WHERE id=:userid",userid=session["user_id"])
    gtotal=cashq[0]["cash"]
    for j in query:
        total[j["symbol"]] = lookup(j["symbol"])["price"] * int(j["quantity"])
        current_price[j["symbol"]]=lookup(j["symbol"])["price"]
        gtotal=gtotal+total[j["symbol"]]

    return render_template("index.html",gtotal=gtotal,query=query,cash=cashq[0]["cash"],total=total,current_price=current_price)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        capital= db.execute("SELECT cash FROM users WHERE id=:userid",userid=session["user_id"])
        if request.form.get("symbol") == None:
            return apology("Symbol required")

        elif request.form.get("shares") == None:
            return apology("Invalid quantity")

        elif lookup(request.form.get("symbol")) == None:
            return apology("Invalid symbol")

        elif capital[0]["cash"] < lookup(request.form.get("symbol"))["price"] * int(request.form.get("shares")):
            return apology("Insufficient funds")

        else:
            today = date.today()
            d = today.strftime("%d/%m/%Y")
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            response=lookup(request.form.get("symbol"))
            amount= response["price"] * int(request.form.get("shares"))
            response=lookup(request.form.get("symbol"))
            trade= db.execute("INSERT INTO transactions (userid,date,time,symbol,name,price,quantity,total) VALUES (:userid,:date,:time,:symbol,:name,:price,:quantity,:total)",userid=session["user_id"],date=d,time=current_time,symbol=request.form.get("symbol"), name=response["name"], price=response["price"],quantity=request.form.get("shares"),total=amount )
            update= db.execute("UPDATE users SET cash=:amt WHERE id=:userid ", amt=capital[0]["cash"]-amount,userid=session["user_id"])
            check=db.execute("SELECT symbol FROM holdings WHERE symbol=:symbol AND userid=:userid",symbol=request.form.get("symbol"),userid=session["user_id"])
            if len(check) < 1:
                update_holdings=db.execute("INSERT INTO holdings (userid,symbol,name,quantity) VALUES (:userid,:symbol,:name,:quantity)", userid=session["user_id"], symbol=request.form.get("symbol"),name=lookup(request.form.get("symbol"))["name"],quantity=request.form.get("shares"))
            else:
                quant=db.execute("SELECT quantity FROM holdings WHERE userid=:userid AND symbol=:symbol ",userid=session["user_id"], symbol=request.form.get("symbol"))
                update_holdings=db.execute("UPDATE holdings SET quantity=:q WHERE symbol=:symbol AND userid=:userid",q=int(quant[0]["quantity"])+int(request.form.get("shares")), symbol=request.form.get("symbol"),userid=session["user_id"])
            flash('Bought!')
            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    query=db.execute("SELECT * FROM transactions WHERE userid=:userid ORDER BY id DESC",userid=session["user_id"])
    return render_template("history.html",query=query)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
        symbol=request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("Invalid symbol!")
        else:
            response = lookup(symbol)
            message="A share of " + response["name"] +" ("+ response["symbol"] +") "+ "costs $" +str(response["price"])+"."
            return render_template("quoted.html",message=message)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username= request.form.get("username")
        check=db.execute("SELECT * FROM users WHERE username=:username",username=username)
        password1=request.form.get("password")
        password2=request.form.get("cpassword")

        if not username:
            return apology("You must enter a username")

        elif len(check) > 0:
            return apology("Username not available")

        elif password1 != password2:
            return apology("Passwords do not match")

        else:
            rows=db.execute("INSERT INTO users (username,hash) VALUES (:username,:password)",username=username,password=generate_password_hash(password2, method='pbkdf2:sha256', salt_length=8))
            check2=db.execute("SELECT * FROM users WHERE username=:username",username=username)
            session["user_id"] = check2[0]["id"]
            flash('Registered!')
            return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        query= db.execute("SELECT symbol,quantity FROM holdings WHERE userid=:userid",userid=session["user_id"])
        return render_template("sell.html",query=query)
    else:
        capital= db.execute("SELECT cash FROM users WHERE id=:userid",userid=session["user_id"])
        quantity=db.execute("SELECT quantity FROM holdings WHERE userid=:userid AND symbol=:symbol",userid=session["user_id"],symbol=request.form.get("symbol"))

        if request.form.get("symbol") == None:
            return apology("Symbol required")

        elif lookup(request.form.get("symbol")) == None:
            return apology("Invalid symbol")

        elif request.form.get("shares") == None:
            return apology("Incomplete input")

        elif int(request.form.get("shares")) > quantity[0]["quantity"]:
            return apology("Not enough shares")

        else:
            today = date.today()
            d = today.strftime("%d/%m/%Y")
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            name=lookup(request.form.get("symbol"))
            response=lookup(request.form.get("symbol"))
            amount= response["price"] * int(request.form.get("shares"))
            trade= db.execute("INSERT INTO transactions (userid,date,time,symbol,name,price,quantity,total) VALUES (:userid,:date,:time,:symbol,:name,:price,:quantity,:total)",userid=session["user_id"],date=d,time=current_time, symbol=(request.form.get("symbol")), name=name["name"], price=response["price"],quantity=-(int(request.form.get("shares"))),total=amount )
            update= db.execute("UPDATE users SET cash=:cash WHERE id=:userid ", cash=capital[0]["cash"]+amount,userid=session["user_id"])
            update2= db.execute("UPDATE holdings SET quantity=:q WHERE userid=:userid AND symbol=:symbol",q=int(quantity[0]["quantity"])-int(request.form.get("shares")),userid=session["user_id"],symbol=request.form.get("symbol"))
            flash('Sold!')
            return redirect("/")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "GET":
        return render_template("addcash.html")
    else:
        amount=request.form.get("amount")
        if amount == None:
            return apology("Invalid input")
        else:
            capital= db.execute("SELECT cash FROM users WHERE id=:userid",userid=session["user_id"])
            update= db.execute("UPDATE users SET cash=:cash WHERE id=:userid ", cash=float(capital[0]["cash"])+float(amount),userid=session["user_id"])
            flash('Cash added sucessfully!')
            return redirect("/")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
