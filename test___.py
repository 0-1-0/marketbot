from pymongo import MongoClient
# u'orders', u'logs', u'convos', u'bots'
db = MongoClient()['marketbot']['convos']
# print client.convos.find_one({'bot_token': '254157126:AAEe38QmOnGynK3ohsd7uu2cFWDWOOgG3CA'})
# print(db.collection_names())
# print(db.database_names())
for doc in db.find({'bot_token': '254157126:AAEe38QmOnGynK3ohsd7uu2cFWDWOOgG3CA'}):
    print doc['chat_id']
