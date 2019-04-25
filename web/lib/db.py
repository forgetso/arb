import pymongo
import web.settings as settings
import datetime


def jobqueue_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_JOBQUEUE]
    return db


def trades_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_TRADES]
    return db


def audit_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_AUDIT]
    return db


def common_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_COMMON]
    return db


def db_connection():
    dbconn = pymongo.MongoClient(host=settings.DB_HOST_JOBQUEUE,
                                 port=settings.DB_PORT_JOBQUEUE)
    return dbconn


def store_trade(trade):
    db = trades_db()
    trade['datetime'] = datetime.datetime.utcnow()
    db.trades.update_one({'_id': trade.get('_id')}, {'$set': trade}, upsert=True)


def store_audit(audit):
    db = audit_db()
    audit['datetime'] = datetime.datetime.utcnow()
    db.audit.insert_one(audit)


def store_fiat_rates(fiat_rates):
    db = common_db()
    fiat_rates['datetime'] = datetime.datetime.utcnow()
    db.fiat_rates.insert_one(fiat_rates)


def get_fiat_rates():
    db = common_db()
    fiat_rates = [x for x in db.fiat_rates.find({}).sort([('datetime', -1)]).limit(1)][0]
    return fiat_rates
