# lab02_2410471011.py  实验二操作一 个人代码片段（学号 2410471011）
# 运行前：窗口A已手动启动 .\server\bin\mongod.exe --dbpath .\data --port 27017 --bind_ip 127.0.0.1
from pymongo import MongoClient

client = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=5000)
print(client.admin.command("ping"))          # {'ok': 1}
print(client.server_info()["version"])       # 4.4.29

database = client["testdb"]
student_id = "2410471011"
collection = database["fruitshop_py_" + student_id]
print(collection.full_name)                  # testdb.fruitshop_py_2410471011

# —— 个人化插入：A01 苹果改为「荔枝」，价格 8.5 -> 19.9 ——
result = collection.insert_one({"_id": "A01", "name": "荔枝", "category": "水果", "price": 19.9, "qty": 10})
print(result.inserted_id)
result = collection.insert_many([
    {"_id": "B01", "name": "香蕉", "category": "水果", "price": 5.5, "qty": 20},
    {"_id": "W01", "name": "饮用水", "category": "饮品", "price": 2.0, "qty": 30},
])
print(result.inserted_ids)
print(collection.find_one({"_id": "A01"}))
print(list(collection.find({"category": "水果"}, {"_id": 0, "name": 1, "price": 1}).sort("price", -1)))

# —— 自己改变条件的查询：阈值 6 -> 10 ——
minimum_price = 10
query = {"price": {"$gte": minimum_price}}
print(list(collection.find(query, {"_id": 0, "name": 1, "price": 1})))

# —— 两次固定更新（重复执行 modified_count 变 0）——
print(collection.find_one({"_id": "W01"}))
result = collection.update_one({"_id": "W01"}, {"$set": {"price": 3.2}})   # 2.5 -> 3.2
print(result.matched_count, result.modified_count)                          # 1 1
result = collection.update_one({"_id": "W01"}, {"$set": {"price": 3.2}})
print(result.matched_count, result.modified_count)                          # 1 0
print(collection.find_one({"_id": "W01"}))

# —— 两次增量更新（每次都真的 +3：30 -> 33 -> 36）——
result = collection.update_one({"_id": "W01"}, {"$inc": {"qty": 3}})
print(result.matched_count, result.modified_count)                          # 1 1
print(collection.find_one({"_id": "W01"}, {"_id": 0, "qty": 1}))            # 33
result = collection.update_one({"_id": "W01"}, {"$inc": {"qty": 3}})
print(result.matched_count, result.modified_count)                          # 1 1
print(collection.find_one({"_id": "W01"}, {"_id": 0, "qty": 1}))            # 36

# —— 聚合：商品种数与库存总数的区别 ——
pipeline = [
    {"$group": {"_id": "$category", "product_count": {"$sum": 1}, "total_qty": {"$sum": "$qty"}}},
    {"$sort": {"_id": 1}},
]
print(list(collection.aggregate(pipeline)))

# —— 指定删除 ——
print(collection.find_one({"_id": "B01"}))
print(collection.count_documents({}))
result = collection.delete_one({"_id": "B01"})
print(result.deleted_count)
print(collection.find_one({"_id": "B01"}))
print(collection.count_documents({}))

# —— 故意制造的重复键错误 ——
from pymongo.errors import DuplicateKeyError
try:
    collection.insert_one({"_id": "A01", "name": "重复编号测试"})
except DuplicateKeyError as error:
    print(type(error).__name__)
    print(collection.find_one({"_id": "A01"}))

# —— 索引与执行计划 ——
print(collection.create_index([("price", 1)]))
print(list(collection.list_indexes()))
query = {"price": {"$gte": 5}}
plan = database.command("explain", {"find": collection.name, "filter": query}, verbosity="executionStats")
print(plan["queryPlanner"]["winningPlan"])
statistics = plan["executionStats"]
print(statistics["nReturned"], statistics["totalDocsExamined"], statistics["totalKeysExamined"])

client.close()
