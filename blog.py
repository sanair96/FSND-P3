import re
import os
import jinja2
import webapp2
import random
import time
import hashlib
import hmac
from string import letters
from user import User
from comment import Comment
from handler import Handler
SECRET = 'imsosecret'
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), autoescape=True)

#Code follows logic of how a user interacts with the blog, Starting from register upto deleting a comment

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		params['user'] = self.user
		return render_str(template, **params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

        def set_secure_cookie(self,name,val):
            cookie_val = make_secure_val(val)
            self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

        def read_secure_cookie(self,name):
            cookie_val = self.request.cookies.get(name)
            return cookie_val and check_secure_val(cookie_val)

        def initialize(self, *a, **kw):
                webapp2.RequestHandler.initialize(self, *a, **kw)
        	uid = self.read_secure_cookie('user_id')
        	self.user = uid and User.by_id(int(uid))
            
	def login(self, user):
		self.set_secure_cookie('user_id', str(user.key().id()))

	def logout(self):
		self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')





def hash_str(s):
	return hmac.new(SECRET, s).hexdigest()

def make_secure_val(s):
	return "%s|%s" % (s, hash_str(s))

def check_secure_val(h):
	st = h.split('|')[0]
	if h == make_secure_val(st):
		return st
def render_str(template, ** params):
	t = jinja_env.get_template(template)
	return t.render(params)

 
class Post(db.Model):
	subject = db.StringProperty(required=True)
	content = db.TextProperty(required=True)
	created = db.DateTimeProperty(auto_now_add=True)
	author = db.StringProperty(required=True)
	likes = db.IntegerProperty()
	likers = db.StringListProperty()
	modify = db.DateTimeProperty(auto_now=True)
    
	def render(self):
		self._render_text = self.content.replace('\n', '<br>')
		return render_str("blog_postformat.html", p=self)

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
	return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
	return password and PASS_RE.match(password)

EMAIL_RE = re.compile(r"^[\S]+@[\S]+.[\S]+$")
def valid_email(email):
	return not email or EMAIL_RE.match(email)


# Page loaded when url typed 
class FirstPage(Handler):
    def get(self):
        self.render("firstpage.html")


# Manages Sign up
class Signup(Handler):
    def get(self):
        self.render("signup.html");
    def post(self):
        errors = False;
        self.name = self.request.get("name");
        self.password = self.request.get("password")
        self.verpassword = self.request.get('verpassword')
        self.email = self.request.get("email")

        params = dict( username=self.name, email=self.email)

        if not valid_username(self.name):
            params['error_username'] = "Thats not a Valid Username"
            errors = True

        if not valid_password(self.password):
            params['error_password'] = "That is not a Valid password"
            errors = True

        if self.password!=self.verpassword:
            params['error_verify'] = "Passwords do not match"
            errors= True

        if not valid_email(self.email):
            params['error_email'] = "Thats an Invalid Email ID"
            errors = True

        if errors:
            self.render("signup.html", **params)
        else:
            self.done()


    def done(self, *a,**kw):
        raise NotImplementedError


# registers user to the databasae
class Register(Signup):
    def done(self):
        u = User.by_name(self.name)

        if u:
            msg = "The username is already taken"
            self.render('signup.html', error_username = msg)
        else:
            u = User.register(self.name, self.password,self.email)
            u.put()

            self.login(u)
            self.redirect('/blog/Welcome')


# Login Function
class Login(Handler):
    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('name')
        password = self.request.get('password')

        u = User.login(username,password)

        if u:
            self.login(u)
            self.redirect('blog/Welcome')
        else:
            msg = 'Invalid Username or Password'
            self.render('login.html',error = msg, name = username)

# after Logging in
class Welcome(Handler):
	def get(self):
        	if self.user:
			self.render("welcome.html", username=self.user.name)
		else:
			self.redirect('/signup')

            
# For Logout
class Logout(Handler):
    def get(self):
        self.logout()
        self.redirect('/login')


# to rener the posts in the page
def render_post(response, post):
    response.out.write('<b>'+post.subject+'<br><br>')
    response.out.write(post.content)


#to load the blog page
class Blog(Handler):
	def render_blog(self):
		posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC LIMIT 20")
		comments = db.GqlQuery("SELECT * FROM Comment ORDER BY created DESC")
		self.render("blog_front.html", posts=posts, comments=comments)

	def get(self):
		self.render_blog()

#to poost a new blog

class PostSub(Handler):
    def get(self,post_id):
        key = db.Key.from_path('Post',int(post_id))
        p= db.get(key)
        if not p:
            self.error(404)
            return
        self.render("blog_newpost.html", p=p)

class PostCreate(Handler):
    def get(self):
        if self.user:
            self.render("blog_forms.html")
        else:
            self.redirect('/login')

    def post(self):
        if not self.user:
            return self.redirect('/login')

	subject = self.request.get('subject')
	content = self.request.get('content')
	author = self.user.name
	likes = 0

        if subject and content:
        	p = Post(subject=subject, content=content, author=author, likes=likes)
		p.put()
		self.redirect('/blog/%s' % str(p.key().id()))
	else:
		error = "Please Fill up subject and content!"
		self.render("blog_forms.html", subject=subject, content=content, error=error)

class LikeHandler(Handler):
	def post(self, post_id):
		key = db.Key.from_path('Post', int(post_id))
		p = db.get(key)

		if not p :
			return self.redirect('/blog')

		if not self.user:
			return self.redirect('/login')
                p.likes = p.likes+1
                p.likers.append(self.user.name)

                if self.user.name == p.author:
			error="You cannot like your own post!"
			return self.render("blog_front.html", message=error)
		else:
			p.put()
			time.sleep(0.1)
			self.redirect("/blog")
		


class EditPost(Handler):
	def get(self, post_id):
		key = db.Key.from_path('Post', int(post_id))
		p = db.get(key)

		if not p:
			self.error(404)
			return

		if not self.user:
			return self.redirect('/login')


		if self.user.name == p.author:
			self.render("blog_edit.html", p=p, subject=p.subject, content=p.content)
		else:
			error = "You don't have access to edit this code"
			return self.render('blog_front.html', message=error)

	def post(self, post_id):
		key = db.Key.from_path('Post', int(post_id))
		p = db.get(key)

		if not p:
			return self.redirect('/blog')

		subject = self.request.get("subject")
		content = self.request.get("content")

		if self.user and self.user.name == p.author:
			if subject and content:
				p.subject = subject
				p.content = content
				p.put()
				self.redirect("/blog/%s" % str(p.key().id()))
			else:
				error = "Please fill up subject and content fields!"
				self.render("blog_edit.html", p=p, subject=subject, content=content,
							 error=error)


class DeletePost(Handler):
	def get(self, post_id):
		key = db.Key.from_path('Post', int(post_id))
		p = db.get(key)

		if not p:
			return self.redirect('/blog')

		if not self.user:
			return self.redirect('/login')

		if self.user.name == p.author:
			p.delete()
			message = "Post Deleted!"
			self.render("blog_front.html", p=p, message=message)
		else:
			error = "You don't have permission to delete this post"
			return self.render("blog_front.html", message=error)

class CreateComment(Handler):
	def get(self, post_id):
		key = db.Key.from_path('Post', int(post_id))
		p = db.get(key)

		if not p:
			self.error(404)
			return

		if not self.user:
			self.redirect("/login")
		else:
			self.render("newcomment.html", p=p, subject=p.subject,
						content=p.content)

	def post(self, post_id):
		if not self.user:
			return self.redirect("/login")

		key = db.Key.from_path('Post', int(post_id))
		p = db.get(key)

		commentin = self.request.get("comment")
		comment = commentin.replace('\n', '<br>')
		commentauthor = self.user.name
		commentid = int(p.key().id())

		if commentauthor and comment and commentid:
			c = Comment(comment=comment, commentauthor=commentauthor, commentid=commentid)
			c.put()
			time.sleep(0.1)
			self.redirect("/blog")
		else:
			error = "Enter your text in the comment box"
			return self.render("newcomment.html", p=p, subject=p.subject,
						 content=p.content, error=error)

		#Class that allows to edit the comment made on a particular post
class EditComment(Handler):
	def get(self, comment_id):
		key = db.Key.from_path('Comment', int(comment_id))
		c = db.get(key)

		if not c:
			self.error(404)
			return

		commented = c.comment.replace('<br>', '\n')

		if not self.user:
			return self.redirect('/login')

		if not self.user.name == c.commentauthor:
			error="You can only edit your own comment!"
			return self.render("blog_front.html", message=error)
		else:
			self.render("editcomment.html", c=c, comment=commented)

	def post(self, comment_id):
		key = db.Key.from_path('Comment', int(comment_id))
		c = db.get(key)

		if not c:
			return self.redirect("/blog")

		commentin = self.request.get("comment")
		comment = commentin.replace('\n', '<br>')
		commentid = c.commentid
		commentauthor = c.commentauthor

		if self.user and self.user.name == c.commentauthor:
			if commentauthor and comment and commentid:
				c.comment = comment
				c.commentauthor = commentauthor
				c.put()
				time.sleep(0.1)
				self.redirect("/blog")
			else:
				error = "Enter your text in the Comment box!"
				return self.render("editcomment.html", c=c, commented=c.comment)

		#Class that allows a user delete his comment
class DeleteComment(Handler):
	def get(self, comment_id):
		key = db.Key.from_path('Comment', int(comment_id))
		c = db.get(key)

		if not c:
			return self.redirect("/blog")

		if not self.user:
			return self.redirect("/login")

		if self.user.name != c.commentauthor:
			error="You can delete only your own comments"
			return self.render("blog_front.html",error=error)
		else:
			c.delete()
			message = "Comment Deleted!"
			self.render("blog_front.html", c=c, message=message)



app = webapp2.WSGIApplication([('/', FirstPage),
                                ('/blog', Blog),
	    			 ('/blog/([0-9]+)', PostSub),
                		 ('/blog/newpost', PostCreate),
                        	 ('/blog/edit/([0-9]+)', EditPost),
				 ('/blog/delete/([0-9]+)', DeletePost),
				 ('/blog/like/([0-9]+)', LikeHandler),
				 ('/blog/newcomment/([0-9]+)', CreateComment),
				 ('/blog/editcomment/([0-9]+)',EditComment),
				 ('/blog/deletecomment/([0-9]+)', DeleteComment),
				 ('/signup', Register),
				 ('/blog/Welcome', Welcome),
				 ('/login', Login),
				 ('/logout', Logout)
				 ], debug = True)
