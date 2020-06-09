import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

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

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # Create a portfolio list
    portfolio_list = []

    # Retrieve the username and cash data from user_id
    username_raw = db.execute("SELECT username,cash FROM users WHERE id = :id", id = session["user_id"])
    username = username_raw[0]["username"]
    cash = username_raw[0]["cash"]

    # counter to store total value of stocks
    stock_total = 0

    # Retrieve symbols, shares information for user
    portfolio = db.execute("SELECT * FROM portfolio WHERE username = :username",username = username)
    for row in portfolio:
        tmp_list = []
        tmp_list.append(row["symbol"])
        tmp_list.append(row["shares"])

        # Retrieve price information for stock
        price_raw = lookup(row["symbol"])
        price = price_raw["price"]
        tmp_list.append(price)

        total = price*int(row["shares"])
        tmp_list.append(total)
        stock_total = stock_total + total
        portfolio_list.append(tmp_list)

    grand_total = cash + stock_total
    grand_total = usd(grand_total)
    cash = usd(cash)
    print(portfolio_list)
    return render_template("/index.html",portfolio=portfolio_list,cash = cash, grand_total = grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        # Retrieve the Stock information from database
        symbol = request.form.get("symbol")

        data_dict = lookup(symbol)

        # Ensure that the user has entered a valid stick symbol
        if data_dict == None:
            return apology("Invalid Symbol")

        price = data_dict["price"]

        # Ensure that the user has entered a positive integer for the number of shares to buy
        str_shares = request.form.get("shares")
        if not str_shares:
            return apology("please enter a positive integer")

        shares = int(str_shares)

        if shares < 0:
            return apology("please enter a positive integer")
        elif type(shares) != int:
            return apology("please enter a positive integer")

        # Check user's current balance
        balance_str = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        balance = balance_str[0]["cash"]


        # Ensure that the user has sufficent balance to purchase shares
        if shares*price > balance:
            return apology("You do not have sufficient balance in your account to make the purchase")

        updated_balance = balance - shares*price

        # Retrieve the username from user_id
        username_raw = db.execute("SELECT username FROM users WHERE id = :id", id = session["user_id"])
        username = username_raw[0]["username"]

        # update the portfolio table
        port_row = db.execute("SELECT * FROM portfolio WHERE username = :username AND symbol = :symbol", username = username ,symbol = symbol)

        if len(port_row) != 1:
            db.execute("INSERT INTO portfolio (username,symbol,price,shares,total) VALUES (:username,:symbol,:price,:shares,:total)", username = username,symbol = symbol,
            price = price, shares = shares, total = shares*price)
        else:
            previous_shares = port_row[0]["shares"]
            int_previous_shares = int(previous_shares)
            updated_shares = int_previous_shares + shares
            db.execute("UPDATE portfolio SET price = :price, shares = :shares, total = :total WHERE username = :username AND symbol = :symbol",price = price,
            shares = updated_shares, total = updated_shares*price, username = username, symbol = symbol)

        # update cash balance after purchase
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash = updated_balance, id = session["user_id"])

        # update transactions history
        db.execute("INSERT INTO transactions (username,symbol,shares,price,datetime,type) VALUES (:username,:symbol,:shares,:price,:datetime,:type)",username = username,
        symbol = symbol, shares= shares, price=price, datetime = datetime.now().strftime("%m/%d/%Y %H:%M:%S"),type = "buy")

        return render_template("buy.html")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Retrieve the username and cash data from user_id
    user_raw = db.execute("SELECT username,cash FROM users WHERE id = :id", id = session["user_id"])
    username = user_raw[0]["username"]

    transactions = db.execute("SELECT * FROM transactions WHERE username = :username",username = username)
    return render_template("history.html",transactions = transactions)





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

    if request.method == "POST":

        # Retrieve the Stock information from database
        symbol = request.form.get("symbol")

        data_dict = lookup(symbol)

        if data_dict == None:
            return apology("Invalid Symbol")

        company_name = data_dict["name"]
        price = data_dict["price"]
        stock_symbol = data_dict["symbol"]

        return render_template("quoted.html", company_name = company_name, price = price, stock_symbol = stock_symbol)


    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirmation and password are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password and Confirmation does not match", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username does not already exist
        if len(rows) != 0:
            return apology("Username already exist, please choose a different username", 403)

        # Create a new user account and store in database.
        hashedpass = generate_password_hash(request.form.get("password"),method='pbkdf2:sha256', salt_length=8)
        username = request.form.get("username")
        db.execute("INSERT INTO users (username,hash) VALUES (:username, :hash)",username = username, hash = hashedpass)

        # Redirect user to login page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Retrieve the username and cash data from user_id
        user_raw = db.execute("SELECT username,cash FROM users WHERE id = :id", id = session["user_id"])
        username = user_raw[0]["username"]
        cash = user_raw[0]["cash"]

        # Determine which stock was selected from the drop down menu
        symbol = request.form.get("symbol")

        # Ensure that the user has entered a positive integer for the number of shares to buy
        str_shares = request.form.get("shares")
        if not str_shares:
            return apology("please enter a positive integer")
        shares = int(str_shares)

        if shares < 0:
            return apology("please enter a positive integer")
        elif type(shares) != int:
            return apology("please enter a positive integer")

        # Ensure that the user has sufficient stocks to sell
        outstanding_stocks = db.execute("SELECT shares FROM portfolio WHERE username = :username and symbol = :symbol",username = username, symbol = symbol)
        stocks = outstanding_stocks[0]["shares"]

        if int(stocks) < shares:
            return apology("You have exceeded the number of shares you have")

        # Look up on current stock price
        data_dict = lookup(symbol)
        price = data_dict["price"]

        # Update cash balance after selling
        updated_balance = cash + shares*price
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash = updated_balance, id = session["user_id"])

        # update transactions history
        db.execute("INSERT INTO transactions (username,symbol,shares,price,datetime,type) VALUES (:username,:symbol,:shares,:price,:datetime,:type)",username = username,
        symbol = symbol, shares= shares, price=price, datetime = datetime.now().strftime("%m/%d/%Y %H:%M:%S"),type = "sell")

        # update the portfolio table
        updated_shares = stocks - shares

        if updated_shares == 0:
            db.execute("DELETE FROM portfolio WHERE username = :username AND symbol = :symbol",username = username, symbol = symbol)
        else:
            db.execute("UPDATE portfolio SET price = :price, shares = :shares, total = :total WHERE username = :username AND symbol = :symbol",price = price,
            shares = updated_shares, total = updated_shares*price, username = username, symbol = symbol)

        return render_template("sell.html")

    else:
        # Retrieve the username from user_id
        username_raw = db.execute("SELECT username FROM users WHERE id = :id", id = session["user_id"])
        username = username_raw[0]["username"]

        # Retrieve symbols from user_id
        options = db.execute("SELECT symbol FROM portfolio WHERE username=:username",username=username)

        return render_template("sell.html",options=options)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
