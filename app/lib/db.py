import pymongo
import app.settings as settings
import datetime
import uuid
from decimal import Decimal
from bson import ObjectId
import os
from app.lib.common import check_pid


# TODO make this a service shared by the job queue so that we're not always connecting to the database?

# Generic Database connection

def db_connection():
    dbconn = pymongo.MongoClient(host=settings.DB_HOST_JOBQUEUE,
                                 port=settings.DB_PORT_JOBQUEUE)
    return dbconn


# Database Connections

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


def exchange_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_EXCHANGE]
    return db


# Database methods

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


def store_balances(exchange, balances):
    db = exchange_db()
    balances_record = {}
    balances_record['balances'] = {symbol: float(amount) for symbol, amount in balances.items()}
    balances_record['datetime'] = datetime.datetime.utcnow()
    balances_record['exchange'] = exchange
    db.balances.insert_one(balances_record)


def get_balances(exchange):
    db = exchange_db()
    balances = {}
    balances_list = [x for x in db.balances.find({'exchange': exchange}).sort([('datetime', -1)]).limit(1)]
    if balances_list:
        balances = {symbol: Decimal(amount) for symbol, amount in balances_list[0].get('balances').items()}
    return balances


# store access times of API methods in case of limits placed on exchanges
def store_api_access_time(exchange, method, access_datetime):
    db = exchange_db()
    db.access_time.insert_one({'datetime': access_datetime, 'exchange': exchange, 'method': method})


# retrieve last accessed time of API method on exchange
def get_api_access_time(exchange, method):
    db = exchange_db()
    # if there is no record of last accessed time then we return a date before today
    # note: datetime.MINYEAR causes this to fail on raspbian stretch (C mktime may not support dates earlier than 1970)
    access_time = datetime.datetime(1970, 1, 1, 0, 0)
    query = {'exchange': exchange, 'method': method}
    access_time_list = [x for x in db.access_time.find(query).sort([('datetime', -1)]).limit(1)]
    if access_time_list:
        access_time = access_time_list[0].get('datetime')

    return access_time


# lock an API method whilst the request is carried out
def lock_api_method(exchange, method, jobqueue_id):
    db = exchange_db()

    db.method_lock.insert_one({'exchange': exchange, 'method': method, 'jobqueue_id': ObjectId(jobqueue_id)})


# unlock an API method after the request has finished
def unlock_api_method(exchange, method, jobqueue_id):
    db = exchange_db()
    db.method_lock.remove({'exchange': exchange, 'method': method, 'jobqueue_id': ObjectId(jobqueue_id)})


# check if an API method is locked
def get_api_method_lock(exchange, method, jobqueue_id):
    result = False
    db = exchange_db()
    record = db.method_lock.find_one({'exchange': exchange, 'method': method, 'jobqueue_id': ObjectId(jobqueue_id)})
    if record:
        result = True
    return result


# Remove any locks on api methods that are not owned by a running jobqueue
def remove_api_method_locks():
    db = jobqueue_db()

    jobqueues_ended = []
    # first check to see if the jobqueues listed in the db are actually running
    # TODO a more thorough check than PID only, although it is fairly unique
    for jobqueue_status_doc in db.status.find({'running': True}):
        # if there is no pid field the use a PID that is too large to be running
        if not check_pid(jobqueue_status_doc.get('pid', 9999999999999)):
            jobqueues_ended.append(jobqueue_status_doc['_id'])

    # remove the jobqueue statuses for jobqueues that are not running
    db.status.remove({'_id': {'$in': jobqueues_ended}})
    db = exchange_db()
    # remove any method locks associated with jobqueues that are not running
    db.method_lock.remove({'_id': {'$in': jobqueues_ended}})


def get_trade_id():
    job_pid = os.getpid()
    db = jobqueue_db()
    this_job = db.jobs.find_one({'job_pid': job_pid})
    if this_job:
        trade_id = this_job.get('_id')
    else:
        # we may be running the job outside of the job queue
        trade_id = uuid.uuid4().hex.replace('-', '')[0:23]
    return str(trade_id)
