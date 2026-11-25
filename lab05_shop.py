# lab05_shop.py  实验五 商品管理与库存协作
# 学号 2410471063  UTF-8 编码
from pymongo import MongoClient
from redis import Redis

sid = "2410471063"
if not sid.isdigit():
    raise ValueError("请把sid改为本人完整数字学号")

client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
r = Redis(host="127.0.0.1", port=6379, decode_responses=True,
          socket_connect_timeout=3, socket_timeout=3)

products = client.shop_db["products_" + sid]
orders = client.shop_db["orders_" + sid]


def stock_key(pid):
    return "product:stock:" + sid + ":" + pid


def details(pid):
    product = products.find_one({"product_id": pid}, {"_id": 0})
    if product is None:
        return None
    raw = r.get(stock_key(pid))
    product["stock"] = None if raw is None else int(raw)
    return product


def take_stock(pid, qty):
    # WATCH事务版：监视、读取、判断、排队、提交；冲突返回-3。
    from redis.exceptions import WatchError
    if type(qty) is not int or qty <= 0:
        raise ValueError("购买数量必须为正整数")
    key = stock_key(pid)
    with r.pipeline() as p:
        try:
            p.watch(key)
            raw = r.get(key)
            if raw is None:
                return -2
            if int(raw) < qty:
                return -1
            p.multi()
            p.decrby(key, qty)
            return p.execute()[0]
        except WatchError:
            return -3


def buy(pid, qty, request_id):
    if type(qty) is not int or qty <= 0:
        return {"ok": False, "reason": "invalid_qty"}
    p = products.find_one({"product_id": pid})
    if p is None:
        return {"ok": False, "reason": "product_missing"}
    if p.get("status") != "on_sale":
        return {"ok": False, "reason": "off_sale"}
    old = orders.find_one({"request_id": request_id}, {"_id": 0})
    if old is not None:
        if old["product_id"] != pid or old["qty"] != qty:
            return {"ok": False, "reason": "request_conflict"}
        return {"ok": True, "duplicate": True, "order": old}
    left = take_stock(pid, qty)
    if left == -3:
        return {"ok": False, "reason": "stock_changed"}
    if left == -2:
        return {"ok": False, "reason": "stock_missing"}
    if left == -1:
        return {"ok": False, "reason": "insufficient_stock"}
    order = {"request_id": request_id, "product_id": pid, "qty": qty, "stock_after": left}
    orders.insert_one(dict(order))
    return {"ok": True, "duplicate": False, "order": order}
