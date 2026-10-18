"""Static consumer fixture; no broker is contacted by indexing."""


@broker.subscriber("orders.created")  # noqa: F821
def process_order():
    cursor.execute("INSERT INTO order_history VALUES (?)", (1,))  # noqa: F821
