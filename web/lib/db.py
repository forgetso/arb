import pymongo
import web.settings as settings


def jobqueue_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_JOBQUEUE]
    return db


def trades_db():
    dbconn = db_connection()
    db = dbconn[settings.DB_NAME_TRADES]
    return db


def db_connection():
    dbconn = pymongo.MongoClient(host=settings.DB_HOST_JOBQUEUE,
                                 port=settings.DB_PORT_JOBQUEUE)
    return dbconn
