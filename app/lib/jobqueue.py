from app.lib.db import jobqueue_db
import app.settings as settings
from datetime import timedelta
import threading
import subprocess
import logging
import os
from bson import ObjectId, json_util
import traceback
import datetime
import json
import sys
import calendar

POLL_INTERVAL = timedelta(seconds=2)
STATUS_CREATING = 'CREATING'
STATUS_RUNNING = 'RUNNING'
STATUS_COMPLETE = 'COMPLETE'
STATUS_FAILED = 'FAILED'
JOB_COLLECTION = 'jobs'
JOB_STATUS_COLLECTION = 'status'
MAX_STDLOG_SIZE = 100 * 1024
JOB_DEFINITIONS = {'TRANSACT':
                       {'type': {'type': str, 'valid': ['buy', 'sell']},
                        'exchange': {'type': str},
                        'trade_pair_common': {'type': str},
                        'volume': {'type': str},
                        'price': {'type': str},
                        },
                   'COMPARE':
                       {'curr_x': {'type': str},
                        'curr_y': {'type': str},
                        },
                   'REPLENISH':
                       {'exchange': {'type': str},
                        'currency': {'type': str}
                        }
                   }


# Handles CRUD of jobs, starts jobs, exists as an instance of a "JobQueue" in the database
class Jobqueue:

    def __init__(self):
        self.db = jobqueue_db()
        self.job_collection = JOB_COLLECTION
        self.start_jobs_interval = None
        self._id = None
        self.compare_trade_pairs_intervals = {}
        self.runningjobs = []

    def remove_job(self, _id):
        result = self.db[JOB_COLLECTION].remove({'_id': _id})
        return result

    def add_job(self, job, jobqueue_id):
        _id = None
        jobtype = job['job_type'].upper()
        if jobtype not in JOB_DEFINITIONS:
            raise TypeError('Unknown job type {}'.format(jobtype))

        valid_job = self.validate_job(job, JOB_DEFINITIONS[jobtype])

        if valid_job:
            valid_job['jobqueue_id'] = jobqueue_id
            _id_result = self.db[JOB_COLLECTION].insert_one(valid_job)
            _id = _id_result.inserted_id
        return _id

    def add_jobs(self, jobs):
        _ids = []
        if isinstance(jobs, list):
            for job in jobs:
                _ids.append(self.add_job(job, jobqueue_id=self._id))
        return _ids

    def validate_job(self, job, job_def):
        for param, paramdef in job_def.items():
            if param not in job['job_args']:
                raise ValueError('Job parameter missing: {}'.format(param))
            if not isinstance(job['job_args'][param], paramdef['type']):
                raise TypeError(
                    'Job parameter of wrong type: got {} expecting {}'.format(job['job_args'][param], paramdef['type']))
            if 'valid' in paramdef:
                if job['job_args'][param] not in paramdef['valid']:
                    raise ValueError('Job parameter {} should be one of {}'.format(param, paramdef['valid']))
        valid_job = job.copy()
        valid_job['job_status'] = STATUS_CREATING
        return valid_job

    def update_job(self, job):
        job_copy = job.copy()
        job_copy.pop('_id')
        if isinstance(job, dict):
            _id = self.db[JOB_COLLECTION].update_one({'_id': ObjectId(job['_id'])}, {'$set': job_copy})

    def get_job(self, _id):
        job = self.db[JOB_COLLECTION].find_one({'_id': ObjectId(_id)})
        return job

    def run_command(self, job, safecmd, stdin=None):

        stdin = json_util.dumps({}, ensure_ascii=False, indent=2, cls=JsonEncoder).encode('utf-8')
        # now actually run the cmd
        env = os.environ.copy()
        safecmd = [str(x) for x in safecmd]
        logging.debug('Running command {}'.format(' '.join(['python3', '-m', ] + safecmd)))
        cmd = ['python3', '-m', ] + safecmd
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.PIPE, env=env, close_fds=True)

        job['job_status'] = STATUS_RUNNING
        job['job_pid'] = process.pid

        retcode = process.wait()
        (stdout, stderr) = process.communicate(stdin)

        if retcode == 0:
            print(stdout.strip().decode('ascii'))
            job['job_status'] = STATUS_COMPLETE
            stdout_str = stdout.strip().decode('ascii')
            job['job_result'] = json.loads(stdout_str)
            if len(job['job_result'].get('downstream_jobs', [])):
                self.add_jobs(job['job_result']['downstream_jobs'])
        else:
            logging.error('FAILURE!')
            logging.error(stderr.strip().decode('ascii'))
            job['job_status'] = STATUS_FAILED
            job['job_error'] = stderr.strip().decode('ascii')

        return


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.date):
            millis = int(calendar.timegm(o.timetuple()) * 1000)
            return {"$date": millis}
        return json.JSONEncoder.default(self, o)


def return_value_to_stdout(value=None):
    if value:
        sys.stdout.flush()
        sys.stdout.write(json.dumps(value))
