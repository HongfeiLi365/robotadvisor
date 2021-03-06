import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from robotadvisor import app, bcrypt
from robotadvisor.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, PortfolioForm, AddStockToPortfolioForm, SQLSearchForm
from .models_with_neo4j import User, Post, Portfolio, Stock
from flask_login import login_user, current_user, logout_user, login_required
from .models_with_sql import filter_stocks
from .neo4j_db_utils import execute_query


@app.route("/about")
def about():
    return render_template('about.html', title='About')

@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html', title='Home')

################################################################################
#User login section. Utilizes the models_with_Neo4j class
################################################################################

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        User.add_user(username=form.username.data, email=form.email.data, password=hashed_password)
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User().get(email=form.email.data)
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn

@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.update_user()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)

################################################################################
#Portfolio Section. Utilizes the models_with_Neo4j class
################################################################################
@app.route("/portfolio")
@login_required
def portfolio():
    if current_user.is_authenticated:
        userPortfolios = Portfolio.query_all_by_user(user = current_user)
        if(len(userPortfolios) < 1):
            flash("You have no portfolios. Please click the link below to create a portfolio.",'info')
        return render_template('portfolio.html', title='Portfolio', results=userPortfolios)

@app.route("/portfolio/edit/<int:portfolio_id>", methods=['GET','POST'])
@login_required
def edit_portfolio(portfolio_id):
    portfolio = Portfolio().get_or_404(portfolio_id)
    recommendations = Portfolio.recommend_stocks(portfolio=portfolio)
    if (len(portfolio.member)<1):
        flash('You have no stocks in this portfolio', 'info')
    return render_template('edit_portfolio.html', title=portfolio.name, portfolio = portfolio, recommendations = recommendations)


@app.route("/portfolio/new", methods=['GET', 'POST'])
@login_required
def new_portfolio():
    form = PortfolioForm()
    if form.validate_on_submit():
        Portfolio.add_portfolio(name=form.name.data, user=current_user)
        flash('Your empty portfolio has been created!', 'success')
        return redirect(url_for('portfolio'))
    return render_template('create_portfolio.html', title='New Portfolio',
                           form=form, legend='New Portfolio')

@app.route("/portfolio/delete/<int:portfolio_id>", methods=['POST'])
@login_required
def delete_portfolio(portfolio_id):
    portfolio = Portfolio().get_or_404(portfolio_id)
    Portfolio.delete_portfolio(portfolio)
    flash('Your portfolio has been deleted!', 'success')
    return redirect(url_for('portfolio'))

@app.route("/portfolio/addStock/<int:portfolio_id>", methods=['GET', 'POST'])
@app.route("/portfolio/addStock/<int:portfolio_id>/<string:defaultNameInput>", methods=['GET', 'POST'])
@login_required
def addStockToPortfolio(portfolio_id,defaultNameInput = None):
    form = AddStockToPortfolioForm()
    m_Portfolio = Portfolio().get_or_404(portfolio_id)
    recommendations = Portfolio.recommend_stocks(portfolio=m_Portfolio)
    if form.validate_on_submit():
        m_Stock = Stock().get(symbol=form.name.data.upper())
        if (Portfolio.add_stock(portfolio=m_Portfolio, stock=m_Stock)):
            flash('Stock has been added', 'success')
        else:
            flash('Error! Stock not present in database', 'danger')
        return redirect(url_for('edit_portfolio', portfolio_id=portfolio_id))
        
    #This section will prefill the "Name of Stock" Field on the webpage.
    form.name.data = defaultNameInput

    return render_template('addStock.html', title='Add Stock',
                           form=form, legend='Add Stock to Portfolio',
                           portfolio=m_Portfolio,
                           recommendations = recommendations)

@app.route("/portfolio/recommend/<int:portfolio_id>", methods=['GET','POST'])
@login_required
def recommend(portfolio_id):
    m_portfolio = Portfolio().get_or_404(portfolio_id)
    recommendations = Portfolio.recommend_stocks(portfolio=m_portfolio)
    return render_template('recommendations.html', title='Recomended Stocks', recommendations = recommendations, portfolio = m_portfolio)

@app.route("/portfolio/Stock/details/<string:stock_name>/<int:portfolio_id>", methods=['GET', 'POST'])
def stockDetails(stock_name, portfolio_id):
    m_Stock = Stock().get(symbol=stock_name)
    m_title = "Details +" + m_Stock.symbol
    inPortfolio = False
    try:
        if execute_query("MATCH (p:portfolio)-[:contains]->(s:stock) WHERE p.id = %s AND s.symbol = '%s' RETURN s" % (portfolio_id, stock_name)) != []:
            inPortfolio = True
            return render_template('stock_details.html', title=m_title, stock=m_Stock, portfolio_id=portfolio_id, inPortfolio = inPortfolio)
    except:
        pass
    return render_template('stock_details.html', title=m_title, stock=m_Stock, portfolio_id=portfolio_id, inPortfolio = inPortfolio)

@app.route("/portfolio/Stock/delete/<string:stock_name>/<int:portfolio_id>", methods=['POST'])
@login_required
def deleteFromPortfolio(stock_name, portfolio_id):
    m_Portfolio = Portfolio().get_or_404(portfolio_id)
    m_Stock = Stock().get(symbol=stock_name)
    Portfolio.delete_stock(portfolio=m_Portfolio, stock=m_Stock)

    flash('Removed from portfolio!', 'success')
    return redirect(url_for('edit_portfolio', portfolio_id=portfolio_id))

################################################################################
#SQL Stock Screener Section
################################################################################

@app.route("/screener", methods=['GET', 'POST'])
def screener():
    form = SQLSearchForm()
    if form.validate_on_submit():
        m_market_cap = form.market_cap_field.data
        m_sma = form.sma_field.data
        m_ps = form.ps_field.data
        m_gross_margin = form.gross_margin_field.data
        m_profit_margin = form.profit_margin_field.data
        m_operating_margin = form.operating_margin_field.data
        print('Operating margin: ' + m_operating_margin)
        print('Profit margin: ' + m_profit_margin)
        m_searchResults = filter_stocks(
            market_cap=m_market_cap,
            sma200=m_sma, ps=m_ps,
            gross_margin=m_gross_margin,
            profit_margin=m_profit_margin,
            operating_margin=m_operating_margin)
        return render_template('sqlSearch.html', title='Screener After Submit', form=form, searchResults=m_searchResults)
    return render_template('sqlSearch.html', title='Screener', form=form)
################################################################################
#Blog Section
################################################################################
@app.route("/blog")
def blog():
    posts = Post.query_all()
    return render_template('blog.html', posts=posts)

@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        Post.add_post(title=form.title.data, content=form.content.data, author=current_user)
        flash('Your post has been created!', 'success')
        return redirect(url_for('blog'))
    return render_template('create_post.html', title='New Post',
                           form=form, legend='New Post')


@app.route("/post/<int:post_id>")
def post(post_id):
    post = Post().get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post().get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        post.update_post()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('create_post.html', title='Update Post',
                           form=form, legend='Update Post')


@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post().get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    Post.delete_post(post)
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))
