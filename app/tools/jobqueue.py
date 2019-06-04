import argparse
from app.execute import JobQueueExecutor
from app.lib.db import jobqueue_db
import logging
from app.settings import LOGLEVEL
import sys
import signal


def main(action):
    if action == 'execute':
        jobqueue = JobQueueExecutor()
        jobqueue.execute()
        logging.info('Job queue running with id {}'.format(jobqueue._id))

    if action == 'show':
        jq_db = jobqueue_db()
        jobs = jq_db.jobs.find({}).sort([('_id', -1)]).limit(10)
        import pprint
        for job in jobs:
            pprint.pprint(job)

    if action == 'stop':
        jq_db = jobqueue_db()
        jq_db.status.update({}, {'running': False})

    def signal_handler(sig, frame):
        jobqueue.stop_jobqueue()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('action', type=str, help='What to do with the jobqueue [execute, show, stop]')
    args = parser.parse_args()
    action = args.action
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)
    if action not in ['execute', 'show', 'stop']:
        raise ValueError('Argument "action" must be one of "execute", "show", or "stop"')
    main(action)


setup()
