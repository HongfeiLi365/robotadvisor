from datetime import datetime
from flask_login import UserMixin
from .sql_db_utils import execute_query, execute_prepared_stmt
from flask import abort

# from robotadvisor import login_manager

# @login_manager.user_loader
# def load_user(user_id):
#     return UserSQL().get(user_id=int(user_id))


class UserSQL(UserMixin):
    id = None
    username = None
    email = None
    image_file = 'default.jpg'
    password = None
    posts = None

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"

    def _load_row(self, row):
        """
        set attributes of itself by values in row

        Parameters
        ----------
        row : dict
            a record from database
        """
        self.id = row['id']
        self.username = row['username']
        self.email = row['email']
        self.password = row['password']
        self.image_file = row['image_file']

    def get(self, user_id=None, email=None, username=None):
        """
        Retrieve a user from database by either user_id, email, or username.
        Return None if such a user does not exist in database.

        Returns
        -------
        User object
            retrieved user
        """
        try:
            if user_id is not None:
                row = execute_query(
                    "SELECT * FROM user WHERE id='{}'".format(user_id))[0]
            elif email is not None:
                row = execute_query(
                    "SELECT * FROM user WHERE email='{}'".format(email))[0]
            elif username is not None:
                row = execute_query(
                    "SELECT * FROM user WHERE username='{}'".format(username))[0]
            self._load_row(row)
            return self
        except IndexError:
            return None

    @classmethod
    def add_user(cls, username, email, password):
        """Save a new user to database"""
        max_id = execute_query("SELECT max(id) FROM user")[0]['max(id)']
        if max_id == None:
            max_id = 0
        execute_query(
            "INSERT INTO user (id, username, email, image_file, password) " +
            "VALUES('{}', '{}', '{}', '{}', '{}')".format(
                max_id+1, username, email, 'default.jpg', password),
            fetch=False)

    def update_user(self):
        """Update a user in database by current attribute values"""
        execute_query(
            "UPDATE user " +
            "SET username='{}', email='{}', image_file='{}' WHERE id='{}'".format(
                self.username, self.email, self.image_file, self.id),
            fetch=False)


class PostSQL():
    id = None
    title = None
    date_posted = datetime.utcnow()
    content = None
    user_id = None
    author = None

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"

    def _load_row(self, row):
        """set attributes of current object

        Parameters
        ----------
        row : dict
            a record from database
        """
        self.id = row['id']
        self.title = row['title']
        self.date_posted = row['date_posted']
        self.content = row['content']
        self.user_id = row['user_id']
        self.author = User().get(user_id=row['user_id'])

    @classmethod
    def query_all(cls):
        """return all posts in database

        Returns
        -------
        list of Post objects
        """
        rows = execute_query("SELECT * FROM post")
        posts = []
        for row in rows:
            p = cls()
            p._load_row(row)
            posts.append(p)
        return posts

    @classmethod
    def add_post(cls, title, content, author):
        """save a new post to database

        Parameters
        ----------
        title : str
            title of post (No special characters please)
        content : str
            content of post (No special characters please)
        author : User object
            user who created this post
        """
        max_id = execute_query("SELECT max(id) FROM post")[0]['max(id)']
        if max_id == None:
            max_id = 0
        execute_query(
            "INSERT INTO post (id, title, date_posted, content, user_id) " +
            "VALUES('{}', '{}', '{}', '{}', '{}')".format(
                max_id+1, title, datetime.utcnow(), content, author.id),
            fetch=False)

    @classmethod
    def delete_post(cls, post):
        """delete a post from database

        Parameters
        ----------
        post : Post object
            the post to be deleted
        """
        execute_query("DELETE FROM post WHERE id='{}'".format(post.id),
                      fetch=False)

    def get(self, post_id=None):
        """
        Retrieve a post from database by id.
        Return None if such a post does not exist in database.

        Returns
        -------
        Post object
            retrieved post
        """

        try:
            row = execute_query(
                "SELECT * FROM post WHERE id='{}'".format(post_id))[0]
            self._load_row(row)
            return self
        except IndexError:
            return None

    def get_or_404(self, post_id, description=None):
        """
        Retrieve a post from database, raise NotFound error if post does
        not exist

        Parameters
        ----------
        post_id : int
            'id' in post table
        description : str, optional
            Message to display in NotFound Error, by default None

        Returns
        -------
        Post object
            retrieved post
        """
        p = self.get(post_id)
        if p is None:
            abort(404, description=description)
        return p

    def update_post(self):
        """
        Update post title and content in database by current attribute values
        """
        execute_query(
            "UPDATE post " +
            "SET title='{}', content='{}' WHERE id='{}'".format(
                self.title, self.content, self.id),
            fetch=False)


class StockSQL():
    symbol = None
    market_cap = None
    sma200 = None
    ps = None
    gross_margin = None
    profit_margin = None
    operating_margin = None

    def __repr__(self):
        return f"Stock('{self.symbol}')"

    def load_row(self, row):
        """
        set attributes of current object

        Parameters
        ----------
        row : dict
            a record from database
        """
        self.symbol = row[0]
        self.market_cap = int(row[1])
        self.sma200 = round(row[2], 4)
        self.ps = round(row[3], 4)
        self.gross_margin = round(row[4], 4)
        self.profit_margin = round(row[5], 4)
        self.operating_margin = round(row[6], 4)


def filter_stocks(market_cap='Any', sma200='Any', ps='Any',
                  gross_margin='Any', profit_margin='Any',
                  operating_margin='Any'):
    """return stocks matching filtering conditions

    Parameters
    ----------
    market_cap : str
        Market Cap, one of 'Any', 'Micro(<$300mln)', 'Small($300mln~$2bln)',
        'Mid($2bln~$10bln)', 'Large(>$10bln)'
    sma200 : str
        200-day Simple Moving Average, one of 'Any', 'Price above SMA200', 
        'Price below SMA200'
    ps : str
        Price to Sales ratio, one of 'Any', 'Low(<1)', 'High(>10)', 'Under 10'
    gross_margin : str
        Gross Margin, one of 'Any', 'Positive(>0%)', 'Negative(<0%)', 'High(>50%)'
    profit_margin : str
        Profit Margin, one of 'Any', 'Positive(>0%)', 'Negative(<0%)', 'High(>20%)'
    operating_margin : str
        Operating Margi, one of 'Any', 'Positive(>0%)', 'Negative(<0%)', 
        'High(>25%)', 'Very Negative(<-20%)'

    Returns
    -------
    list of StockSQL objects
        stocks
    """
    stmt = 'CALL filter_stocks(%s, %s, %s, %s, %s, %s)'
    data = (market_cap, sma200, ps, gross_margin,
            profit_margin, operating_margin)
    rows = execute_prepared_stmt(stmt, data)

    stocks = []
    for row in rows:
        s = StockSQL()
        s.load_row(row)
        stocks.append(s)
    return stocks
