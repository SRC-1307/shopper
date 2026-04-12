import re
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import NoResultFound
import db_models
from db_connect import db_engine


def get_db_session(engine):
    try:
        Session = sessionmaker(bind=engine)
        session = Session()
        return session
    except Exception as ex:
        print("Error getting DB session : ", ex)
        return None


in_progress_carts = {}


def process_intent(intent, response_parameters, session_id: str):
    match intent:
        case 'track.order':
            return track_order(response_parameters)
        case 'add.items':
            return add_order(response_parameters, session_id)
        case 'order.brand':
            return get_available_brands(response_parameters, session_id)
        case 'view.cart':
            return get_session_cart_items(session_id)
        case 'place.the.order':
            return complete_order(session_id)
        case 'remove.from.cart':
            return remove_order(response_parameters, session_id)
        case default:
            return 'I couldn\'t understand you.'


def get_session_id_from_context(context: str):
    extracted_session_id = re.search(r"/sessions/(.*?)/contexts/", context)
    if extracted_session_id:
        return extracted_session_id.group(1)
    return ""


def track_order(order_parameters: dict):
    order_id = order_parameters['number']
    order_status = ""
    order_price = 0
    try:
        db_session = get_db_session(engine=db_engine)
        order_status = db_session.query(db_models.Order.status).filter(db_models.Order.id == int(order_id)).first()
        order_price = db_session.query(db_models.Order.total_price).filter(db_models.Order.id == int(order_id)).first()
        db_session.close()
    except NoResultFound:
        print("NO DATA FOUND")

    if order_status:
        response_text = (f"Thank you for ordering from shopper. Your order with Order ID: {int(order_id)} of "
                         f"total price: {order_price[0]}$ is in {order_status[0]} status")
    else:
        response_text = (f"Dear customer,We regret to inform you that no order was found with Order ID {int(order_id)} "
                         f"please say new order to a place an order")

    return response_text


def add_order(order_parameters: dict, session_id: str):
    grocery_items = order_parameters['grocery-item']
    grocery_quantity = order_parameters["number"]

    if len(grocery_items) == len(grocery_quantity):
        new_cart_item = {item: {'quantity': int(qty)} for item, qty in zip(grocery_items, grocery_quantity)}
        if session_id in in_progress_carts:
            current_grocery_cart = in_progress_carts[session_id]
            current_grocery_cart.update(new_cart_item)
            in_progress_carts[session_id] = current_grocery_cart
        else:
            in_progress_carts[session_id] = new_cart_item

        list_of_items = list(in_progress_carts[session_id].keys())
        list_of_items_without_brand = []

        for item in list_of_items:
            if "brand" not in in_progress_carts[session_id][item].keys():
                list_of_items_without_brand.append(item)

        response_text = get_item_choices(list_of_items_without_brand)
    else:
        response_text = "Sorry, I did not get that. Please specify grocery items and their quantities clearly."

    return response_text


def get_available_brands(order_parameters: dict, session_id: str):
    grocery_items = order_parameters['grocery-item']
    grocery_brands = order_parameters['brand']
    existing_items = in_progress_carts[session_id]

    for item in grocery_items:
        cart_item = in_progress_carts[session_id]
        if item in cart_item:
            index = grocery_items.index(item)
            cart_item[item]['brand'] = grocery_brands[index]
            brand_name = cart_item[item]['brand'] if cart_item[item]['brand'] != "great\xa0value" else "great value"
            cart_item[item]['price'] = round(get_item_prices(item_name=item, item_brand=brand_name)[0], 2)
            in_progress_carts[session_id] = cart_item

    cart_item_info_str = convert_cart_items_to_str(in_progress_carts[session_id])
    response_text = f"In your cart, you have {cart_item_info_str}. "

    unbranded_items = []

    for key in existing_items.keys():
        if "brand" not in in_progress_carts[session_id][key].keys():
            unbranded_items.append(key)

    if len(unbranded_items) > 0:
        response_text += f"You need to specify brands for {','.join(unbranded_items)}"
    else:
        response_text += "Do you need anything else?"
    return response_text


def convert_cart_items_to_str(grocery_cart: dict):
    cart_items_str = ", ".join(
        [str(str(int(value['quantity'])) + " " + value['brand'] + " " + key + " " if 'brand' in value.keys() else ' ') +
         str('for $' + str(round(value['price'] * int(value['quantity']),2)) if 'price' in value.keys() else '') +
         f"" for key, value in grocery_cart.items()])
    return cart_items_str


def get_item_choices(items):
    db_session = get_db_session(engine=db_engine)
    available_items = db_session.query(db_models.Item.name, db_models.Item.company, db_models.Item.price).filter(
        db_models.Item.name.in_(items)).all()
    available_items_dict = {}

    for item, brand, price in available_items:
        available_items_dict.setdefault(item, set()).add((brand, price))
    available_items_str = ""
    for item, options in available_items_dict.items():
        available_items_str += f"For {item} we have options from: "
        options_list = []
        for brand, price in options:
            options_list.append(f"{brand} for {price}")
        available_items_str += ', '.join(options_list)
        available_items_str += ". "

    return available_items_str


def get_item_prices(item_name: str, item_brand: str):
    db_session = get_db_session(engine=db_engine)
    item_price = (db_session.query(db_models.Item.price)
                  .filter(db_models.Item.name == item_name).filter(db_models.Item.company == item_brand).first())
    if item_price:
        result = item_price
    else:
        result = -1
    return result


def get_total_cart_value(session_id: str):
    total_price = 0
    current_cart = in_progress_carts[session_id]
    print(current_cart)
    print(current_cart.keys())
    for item in current_cart.keys():
        if current_cart[item]['price'] and current_cart[item]['price'] > 0:
            item_price = current_cart[item]['price']
        else:
            item_price = 0
        total_price += item_price * current_cart[item]['quantity']

    return round(total_price,2)


def get_session_cart_items(session_id):
    cart_item_info_str = convert_cart_items_to_str(in_progress_carts[session_id])
    return (f"In your cart, you have {cart_item_info_str}. And your total to pay is {get_total_cart_value(session_id)}."
            f" Do you need anything else?")


def remove_order(order_parameters: dict, session_id: str):
    response_text = ""

    if session_id not in in_progress_carts:
        return "Sorry, Couldn't find your order. Please place a new order by saying \"NEW ORDER\"."
    grocery_items = order_parameters['grocery-item']

    # Normalize grocery_items so we always work with a list of item names,
    # not a single string or a list of characters.
    if isinstance(grocery_items, str):
        grocery_items = [grocery_items]
    elif isinstance(grocery_items, list) and grocery_items and all(isinstance(x, str) and len(x) == 1 for x in grocery_items):
        # Handles cases where a single word like "Salt" was split into ['S', 'a', 'l', 't']
        grocery_items = ["".join(grocery_items)]
    
    present_cart = in_progress_carts[session_id]
    present_cart_list=list(present_cart.keys())

    removed_grocery_items = []
    unknown_grocery_items = []

    for grocery_item in grocery_items:
        print(grocery_item)
        if grocery_item in present_cart_list:
            removed_grocery_items.append(grocery_item)
            print("removed_grocery_items",removed_grocery_items)
            present_cart.pop(grocery_item)
            print("present_cart",present_cart)
        else:
            unknown_grocery_items.append(grocery_item)
            print("unknown_grocery_items",unknown_grocery_items)
    response_text += f"Items {','.join(removed_grocery_items)} are now removed from your cart." \
        if any(removed_grocery_items) else ""
    response_text += f" Sorry You don\'t have following items in your cart: {','.join(unknown_grocery_items)}" \
        if any(unknown_grocery_items) else ""
    response_text += " Your cart is empty." \
        if not any(present_cart.keys()) \
        else (f" You have following items in your cart:{convert_cart_items_to_str(present_cart)}.Do you need anything "
              f"else?")

    return response_text


def complete_order(session_id: str):
    if session_id in in_progress_carts:
        order_id, total_price = save_order(session_id=session_id)
        print(order_id)
        if order_id == -1:
            return "Sorry, I was not able to place order at the moment. Please place a new one after some-time."
        else:
            response_text = (
                f"Your order is placed successfully.The total price of your order is {total_price}$ and your new order id is {order_id}"
                f". Please use your order id to track your delivery. Thank you.")
        del in_progress_carts[session_id]
    else:
        return "Sorry, Couldn't find your order. Please place a new order by saying \"NEW ORDER\"."

    return response_text


def save_order(session_id: str):
    total_price = get_total_cart_value(session_id)
    current_cart = in_progress_carts[session_id]

    items = []

    for item, details in current_cart.items():
        item_details = f"{item}|{details['brand']}|{details['price']}|{details['quantity']}"
        items.append(item_details)

    result = ", ".join(items)
    print(result)

    new_order = db_models.Order(items=items, total_price=total_price)
    db_session = get_db_session(engine=db_engine)
    db_session.add(new_order)
    db_session.commit()
    print(new_order.id)
    db_session.expunge(new_order)
    db_session.close()
    return new_order.id, total_price
