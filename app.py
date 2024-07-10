from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "23baf8bb501b2fcb42ff37925019b9ae"

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Welcome123'
app.config['MYSQL_DB'] = 'donation_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# File upload configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

mysql = MySQL(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT 
            posts.*, 
            users.username,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count,
            (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.post_id) AS comment_count,
            (SELECT SUM(donations.amount) FROM donations WHERE donations.post_id = posts.post_id) AS total_donations,
            (SELECT users.username 
             FROM donations 
             JOIN users ON donations.user_id = users.user_id 
             WHERE donations.post_id = posts.post_id 
             ORDER BY donations.created_at DESC 
             LIMIT 1) AS donor_username
        FROM 
            posts
        JOIN 
            users ON posts.user_id = users.user_id
        ORDER BY 
            posts.created_at DESC
    ''')
    posts = cur.fetchall()

    # Fetching images for each post
    for post in posts:
        cur.execute('SELECT image_filename FROM post_images WHERE post_id = %s', (post['post_id'],))
        post['images'] = cur.fetchall()
    cur.close()
    return render_template('home.html', posts=posts)

@app.route('/home/<int:user_id>')
def home(user_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    user = cur.fetchone()

    cur.execute('''
        SELECT posts.*, users.username, 
        (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count,
        (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.post_id) AS comment_count,
        (SELECT SUM(donations.amount) FROM donations WHERE donations.post_id = posts.post_id) AS total_donations
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        ORDER BY created_at DESC
    ''')
    posts = cur.fetchall()

    # Fetching images for each post
    for post in posts:
        cur.execute('SELECT image_filename FROM post_images WHERE post_id = %s', (post['post_id'],))
        post['images'] = cur.fetchall()

    cur.close()

    return render_template('home.html', user=user, posts=posts)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            if user.get('is_admin'):
                return redirect(url_for('admin', user_id=user['user_id']))
            else:
                return redirect(url_for('home', user_id=user['user_id']))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Hash the password with a valid method
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)', (username, email, hashed_password))
        mysql.connection.commit()
        cur.close()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin/<int:user_id>')
def admin(user_id):
    # Check if user is admin
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()

    if not user or not user.get('is_admin'):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('index'))  # Redirect to appropriate page

    # Fetch posts for admin panel
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM posts ORDER BY created_at DESC')
    posts = cur.fetchall()
    cur.close()

    # Fetch donations with relevant details (username, post name, amount, date/time)
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT donations.*, users.username AS donor_username, posts.title AS post_title, posts.created_at AS post_created_at
        FROM donations
        JOIN users ON donations.user_id = users.user_id
        JOIN posts ON donations.post_id = posts.post_id
        ORDER BY donations.created_at DESC
    ''')
    donations = cur.fetchall()

    # Fetching images for each post
    for post in posts:
        cur.execute('SELECT image_filename FROM post_images WHERE post_id = %s', (post['post_id'],))
        post['images'] = cur.fetchall()


    cur.close()

    return render_template('admin.html', user=user, posts=posts, donations=donations)

@app.route('/admin/create_post', methods=['POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = request.form.get('user_id')  # Assuming you get user_id from the form

        # Check if images are uploaded
        if 'images[]' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)

        files = request.files.getlist('images[]')

        # Validate and save each image
        image_filenames = []
        for file in files:
            if file.filename == '':
                flash('No selected file', 'danger')
                return redirect(request.url)

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filenames.append(filename)
            else:
                flash('File type not allowed', 'danger')
                return redirect(request.url)

        # Insert post details into the posts table
        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO posts (user_id, title, content) VALUES (%s, %s, %s)', (user_id, title, content))
        mysql.connection.commit()

        # Get the post_id of the newly inserted post
        post_id = cur.lastrowid

        # Insert each image filename into the post_images table
        for filename in image_filenames:
            cur.execute('INSERT INTO post_images (post_id, image_filename) VALUES (%s, %s)', (post_id, filename))
            mysql.connection.commit()

        cur.close()

        flash('Post created successfully!', 'success')
        return redirect(url_for('admin', user_id=user_id))

    flash('Method Not Allowed', 'danger')
    return redirect(url_for('admin', user_id=session['user_id']))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    user_id = request.form['user_id']
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM posts WHERE post_id = %s', (post_id,))
    mysql.connection.commit()
    cur.close()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('admin', user_id=user_id))

@app.route('/like/<int:post_id>/<int:user_id>', methods=['GET'])
def like_post(post_id, user_id):
    if 'user_id' not in session:
        flash('Please login to like posts.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('INSERT INTO likes (post_id, user_id) VALUES (%s, %s)', (post_id, user_id))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('home', user_id=user_id))

@app.route('/unlike/<int:post_id>/<int:user_id>', methods=['GET'])
def unlike_post(post_id, user_id):
    if 'user_id' not in session:
        flash('Please login to unlike posts.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM likes WHERE post_id = %s AND user_id = %s', (post_id, user_id))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('home', user_id=user_id))

@app.route('/comment/<int:post_id>/<int:user_id>', methods=['POST'])
def comment_post(post_id, user_id):
    if 'user_id' not in session:
        flash('Please login to comment on posts.', 'danger')
        return redirect(url_for('login'))

    comment_text = request.form['comment_text']
    cur = mysql.connection.cursor()
    cur.execute('INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s)', (post_id, user_id, comment_text))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('home', user_id=user_id))

@app.route('/comments/<int:post_id>', methods=['GET'])
def get_comments(post_id):
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT comments.*, users.username FROM comments
        JOIN users ON comments.user_id = users.user_id
        WHERE comments.post_id = %s
        ORDER BY comments.created_at DESC
    ''', (post_id,))
    comments = cur.fetchall()
    cur.close()
    return jsonify(comments)

@app.route('/delete_comment/<int:comment_id>/<int:user_id>', methods=['POST'])
def delete_comment(comment_id, user_id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM comments WHERE comment_id = %s', (comment_id,))
    mysql.connection.commit()
    cur.close()
    flash('Comment deleted successfully!', 'success')
    return redirect(url_for('home', user_id=user_id))

@app.route('/share/<int:post_id>/<int:user_id>', methods=['GET'])
def share_post(post_id, user_id):
    if 'user_id' not in session:
        flash('Please login to share posts.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('INSERT INTO shares (post_id, user_id) VALUES (%s, %s)', (post_id, user_id))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('home', user_id=user_id))


# Example AJAX endpoint for checking username availability
@app.route('/check_username', methods=['POST'])
def check_username():
    username = request.form['username']

    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cur.fetchone()
    cur.close()

    if user:
        return jsonify({'available': False})
    else:
        return jsonify({'available': True})

# Example endpoint for handling donations
@app.route('/payment/<int:post_id>/<int:user_id>', methods=['GET'])
def payment_page(post_id, user_id):
    return render_template('payment_page.html', post_id=post_id, user_id=user_id)

'''
# Route to handle donation submission
@app.route('/donate', methods=['POST'])
def donate():
    if 'user_id' not in session:
        flash('Please login to donate.', 'danger')
        return redirect(url_for('login'))

    post_id = request.form.get('post_id')
    user_id = request.form.get('user_id')
    amount = request.form.get('amount')
    payment_method = request.form.get('payment_method')

    # Insert donation into database (replace with your actual SQL insertion)
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO donations (post_id, user_id, amount, payment_method) VALUES (%s, %s, %s, %s)", (post_id, user_id, amount, payment_method))
    mysql.connection.commit()
    cur.close()

    flash('Donation successful', 'success')
    return redirect(url_for('index'))  # Redirect to index or another appropriate page after donation

# Route to handle help_now redirection
@app.route('/help_now/<int:post_id>/<int:user_id>', methods=['GET'])
def help_now(post_id, user_id):
    if 'user_id' not in session:
        flash('Please login to help now.', 'danger')
        return redirect(url_for('login'))

    # Redirect to the payment page with post_id and user_id
    return redirect(url_for('payment_page', post_id=post_id, user_id=user_id))'''
# Route to handle donation submission
@app.route('/donate', methods=['POST'])
def donate():
    if 'user_id' not in session:
        flash('Please login to donate.', 'danger')
        return redirect(url_for('login'))

    post_id = request.form.get('post_id')
    user_id = request.form.get('user_id')
    amount = request.form.get('amount')
    payment_method = request.form.get('payment_method')  # Retrieve selected payment method

    # Insert donation into database
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO donations (post_id, user_id, amount, payment_method) VALUES (%s, %s, %s, %s)", (post_id, user_id, amount, payment_method))
    mysql.connection.commit()
    cur.close()

    flash('Donation successful', 'success')
    return redirect(url_for('index'))  # Redirect to index or another appropriate page after donation

# Route to handle help_now redirection
@app.route('/help_now/<int:post_id>/<int:user_id>', methods=['GET'])
def help_now(post_id, user_id):
    if 'user_id' not in session:
        flash('Please login to help now.', 'danger')
        return redirect(url_for('login'))

    # Redirect to the payment page with post_id and user_id
    return redirect(url_for('payment_page', post_id=post_id, user_id=user_id))
    
    # Run the app
if __name__ == '__main__':
    app.run(debug=True)
