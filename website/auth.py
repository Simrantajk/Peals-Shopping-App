from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from decimal import Decimal
from pymysql import IntegrityError
from .conn import conn

auth = Blueprint('auth', __name__)
connection = conn()

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        customer_name = request.form.get('customer_name')
        contactno = request.form.get('contactno')
        customer_address = request.form.get('customer_address')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        if len(email) < 4:
            flash('Invalid email', category='error')
        elif password1 != password2:
            flash('Passwords do not match', category='error')
        else:
            # Check if the user already exists
            with connection.cursor() as cursor:
                sql = "SELECT * FROM customers WHERE email = %s"
                cursor.execute(sql, (email))
                user = cursor.fetchone()
                
                if user:
                    flash('Email already exists. Please log in.', category='error')
                else:
                    # Insert user data into the database
                    sql = "INSERT INTO customers (email, customer_name, contactno, customer_address, password) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(sql, (email, customer_name, contactno, customer_address, password1))
                    connection.commit()  # Commit the transaction

                    flash('Account created successfully', category='success')
                    return redirect(url_for('auth.login'))  # Redirect to login page

    return render_template('signup.html', user="current_user")



@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        with connection.cursor() as cursor:
            sql = "SELECT * FROM customers WHERE email = %s AND password = %s"
            cursor.execute(sql, (email, password))
            user = cursor.fetchone()
            
            if user:
                session['user'] = {
                    'customer_id': user['customer_id']} # Store user information including customer_id in session
                flash('Login successful', category='success')
                return redirect(url_for('auth.home'))  # Redirect to home page after login
            else:
                flash('Incorrect email or password', category='error')
    
    return render_template('login.html', user="current_user")



@auth.route('/home', methods=['GET', 'POST'])
def home():
    if 'user' in session:
        selected_category = request.args.get('category')
        if request.method == 'POST':
            product_id = request.form.get('product_id')
            
            if not product_id:
                flash('Invalid product', category='error')
                return redirect(url_for('auth.home'))

            with connection.cursor() as cursor:
                # Check if the product exists
                sql_check_product = "SELECT * FROM products WHERE product_id = %s"
                cursor.execute(sql_check_product, (product_id,))
                product = cursor.fetchone()

                if not product:
                    flash('Product not found', category='error')
                    return redirect(url_for('auth.home'))

                # Get the customer ID
                customer_id = session['user']['customer_id']

                # Check if the user has an active cart
                sql_check_cart = "SELECT * FROM cart WHERE customer_id = %s"
                cursor.execute(sql_check_cart, (customer_id,))
                cart = cursor.fetchone()

                if not cart:
                    # If the user doesn't have a cart, create one
                    sql_create_cart = "INSERT INTO cart (customer_id) VALUES (%s)"
                    cursor.execute(sql_create_cart, (customer_id,))
                    connection.commit()
                else:
                    # If the cart already exists, do nothing
                    pass

                # Retrieve the cart_id after creation or existing cart
                cursor.execute(sql_check_cart, (customer_id,))
                cart = cursor.fetchone()
                cart_id = cart['cart_id']

                try:
                    # Add the product to the cart
                    sql_add_to_cart = "INSERT INTO cart_products (cart_id, product_id) VALUES (%s, %s)"
                    cursor.execute(sql_add_to_cart, (cart_id, product_id))
                    
                    # Decrement the stock of the product
                    #sql_decrement_stock = "UPDATE products SET stock = stock - 1 WHERE product_id = %s"
                    #cursor.execute(sql_decrement_stock, (product_id,))
                    
                    connection.commit()

                    flash('Product added to cart', category='success')
                except IntegrityError:
                    # Handle IntegrityError (e.g., duplicate entry)
                    flash('Product is already in cart', category='error')
                except Exception as e:
                    # Handle other exceptions
                    flash('An error occurred while adding the product to the cart', category='error')

                return redirect(url_for('auth.home'))

        # If it's a GET request or after processing the POST request, fetch products and categories from the database
        with connection.cursor() as cursor:
            # Fetch products based on the selected category
            if selected_category:
                sql_products = "SELECT * FROM products WHERE types = %s"
                cursor.execute(sql_products, (selected_category,))
            else:
                sql_products = "SELECT * FROM products"
                cursor.execute(sql_products)
            
            products = cursor.fetchall()

            # Fetch all distinct categories for the dropdown
            sql_categories = "SELECT DISTINCT types FROM products"
            cursor.execute(sql_categories)
            categories = [category['types'] for category in cursor.fetchall()]

        current_user = session['user']
        return render_template('home.html', user=current_user, products=products, categories=categories, selected_category=selected_category)
    else:
        flash('Please log in to access this page', category='error')
        return redirect(url_for('auth.login'))



@auth.route('/cart', methods=['GET','POST'])
def cart():
    if 'user' in session:
        current_user = session['user']
        customer_id = session['user']['customer_id']

        if request.method == 'GET':
            with connection.cursor() as cursor:
                # Query products from the database
                sql = """
                    SELECT 
                        cp.cart_id, 
                        cp.product_id, 
                        p.product_name, 
                        p.price, 
                        p.image,
                        SUM(p.price) AS total_price
                    FROM 
                        cart_products cp 
                        JOIN products p ON cp.product_id = p.product_id 
                        JOIN cart c ON cp.cart_id = c.cart_id 
                    WHERE 
                        c.customer_id = %s
                    GROUP BY 
                        cp.cart_id, 
                        cp.product_id, 
                        p.product_name, 
                        p.price, 
                        p.image
                    """
                cursor.execute(sql, (customer_id,))
                cartItems = cursor.fetchall()

            # Calculate total price
            total_price = sum(Decimal(item['total_price']) for item in cartItems)

            return render_template('cart.html', user=current_user, cartItems=cartItems, total_price=total_price)

        elif request.method == 'POST':
            product_id = request.form.get('product_id')  # Get product_id from the form data
            with connection.cursor() as cursor:
                # Delete the item from the cart
                sql = "DELETE FROM cart_products WHERE cart_id = (SELECT cart_id FROM cart WHERE customer_id = %s) AND product_id = %s"
                cursor.execute(sql, (customer_id, product_id))
                connection.commit()
            flash('Product removed from cart', category='success')
            return redirect(url_for('auth.cart'))  # Redirect back to the cart page after deletion
    else:
        flash('Please log in to access this page', category='error')
        return redirect(url_for('auth.login'))



@auth.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user' in session:
        current_user = session['user']
        customer_id = session['user']['customer_id']
        
        if request.method == 'POST':
            delivery_address = request.form.get('delivery_address')  
            payment = request.form.get('payment_method')
            
            # Insert the checkout details into the orders table
            with connection.cursor() as cursor:
                sql_insert_order = "INSERT INTO orders (date, delivery_address, payment, customer_id) VALUES (CURRENT_TIMESTAMP, %s, %s, %s)"
                cursor.execute(sql_insert_order, (delivery_address, payment, customer_id))
                connection.commit()
            
            with connection.cursor() as cursor:
                sql_delete_cart = "DELETE FROM cart_products WHERE cart_id IN (SELECT cart_id FROM cart WHERE customer_id = %s)"
                cursor.execute(sql_delete_cart, (customer_id))
                connection.commit()
                
            flash('Order placed successfully!', category='success')
            return redirect(url_for('auth.order'))  # Redirect to home page after placing the order
        
            
        return render_template('checkout.html', user=current_user)
    else:
        flash('Please log in to access this page', category='error')
        return redirect(url_for('auth.login'))



@auth.route('/order', methods=['GET', 'POST'])
def order():
    if 'user' in session:
        current_user = session['user']
        customer_id = session['user']['customer_id']
        
        with connection.cursor() as cursor:
            # Query orders for the current user along with customer's name
            sql_fetch_orders = """
                SELECT o.order_id, o.date, o.delivery_address, o.payment, c.customer_name 
                FROM orders o 
                JOIN customers c ON o.customer_id = c.customer_id 
                WHERE o.customer_id = %s
            """
            cursor.execute(sql_fetch_orders, (customer_id,))
            orders = cursor.fetchall()
            
           
        
        return render_template('order.html', user=current_user, orders=orders)
    else:
        flash('Please log in to access this page', category='error')
        return redirect(url_for('auth.login'))



@auth.route('/logout', methods=['GET', 'POST'])
def logout():
    if 'user' in session:
        session.clear()  # Clear the session data
        flash('You have been logged out', category='success')
        return redirect(url_for('auth.login'))
    else:
        flash('Please log in to access this page', category='error')
        return redirect(url_for('auth.login'))
   