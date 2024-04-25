import pymysql.cursors

def conn():
    connection = pymysql.connect(
    host='localhost',
    user='root',
    password='simsim',
    database='ecommerce',  
    cursorclass=pymysql.cursors.DictCursor
)
    return(connection)