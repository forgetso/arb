import threading
import app.settings as settings
from app.lib.jobqueue import Jobqueue, JOB_STATUS_COLLECTION, JOB_DEFINITIONS, JOB_COLLECTION, STATUS_RUNNING, \
    STATUS_FAILED, STATUS_CREATING, STATUS_COMPLETE, MAX_STDLOG_SIZE
import logging
import traceback
import datetime
from app.lib.setup import update_fiat_rates
from app.lib.db import remove_api_method_locks


# Create an instance of the app! Execute a job queue. Begin scraping prices of crypto. Look for jobs to start based on
# the scrapes.
class JobQueueExecutor:

    def __init__(self):
        self.jq = Jobqueue()
        self.runningjobs = []
        self.compare_trade_pairs_intervals = {}
        self.start_jobs_interval = None
        self._id = None
        self.running = False
        self.finishedjobs = []
        return

    def execute(self):
        # this is the  job queue monitor that polls the database for new, completed, and failed jobs
        # it will periodically run compares for a set list of currency pairs

        self.jq.db[JOB_STATUS_COLLECTION].remove()

        self._id = self.jq.db[JOB_STATUS_COLLECTION].insert({'running': True})

        # remove any api locks that were stored previously
        # TODO tie these locks to the jobqueue ID
        remove_api_method_locks()

        # we are going to constantly check apis for arbitrage opportunities

        for trade_pair in settings.TRADE_PAIRS:
            logging.debug(trade_pair)
            self.compare_trade_pairs_intervals[trade_pair] = call_repeatedly(settings.INTERVAL_COMPARE,
                                                                             self.compare_trade_pair,
                                                                             trade_pair)

        # we periodically update the fiat rate of BTC to identify potential profit

        self.fiat_rate_interval = call_repeatedly(settings.INTERVAL_FIAT_RATE, update_fiat_rates)

        # when opportunities are identified they are added as jobs to the db. this next function will find these jobs
        # and execute them, adding any subsequent downstream jobs to the queue

        self.start_jobs_interval = call_repeatedly(settings.INTERVAL_NEWJOBS, self.start_jobs)

        self.check_running_jobs_interval = call_repeatedly(settings.INTERVAL_RUNNINGJOBS, self.check_running_jobs)

        # TODO jobs to check balances between exchanges and periodically move large amounts
        # job is called REPLENISH

        # TODO job to convert BTC (TODO set this as a master currency) to all live currencies in MASTER EXCHANGE (set in settings)

        # TODO jobs to move crypto into fiat periodically to protect against large price fluctuations

        return

    def start_jobs(self):
        # stop command may have been issued
        self.is_running()
        if not self.running:
            # cancels the interval
            self.start_jobs_interval()

        jobs_to_start = self.jq.db[JOB_COLLECTION].find(
            {'job_status': STATUS_CREATING, 'job_type': {'$nin': settings.JOBS_NOT_RUNNING}})
        for job in jobs_to_start:
            job_type = job['job_type']
            if job_type not in JOB_DEFINITIONS:
                raise TypeError('Unknown job type {}'.format(job_type))

            safecmd = ['app.jobs.{}'.format(job_type.lower())]
            for arg_key, arg_value in job['job_args'].items():
                type_function = None
                try:
                    type_function = JOB_DEFINITIONS[job_type][arg_key].get('type')
                    safecmd.append(type_function(arg_value))
                except:
                    raise TypeError('Invalid job argument supplied: {} should be {}'.format(arg_value, type_function))
            jobthread = JobQueueThread(self.jq, job, safecmd)
            jobthread.setDaemon(True)
            jobthread.start()
            job['job_startat'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            job['job_status'] = STATUS_RUNNING
            job['job_lock'] = True
            self.jq.update_job(job)
            self.runningjobs.append(jobthread)

    def check_running_jobs(self):
        ok = True
        self.finishedjobs = []
        for jobthread in self.runningjobs:
            if not jobthread.is_alive():
                # the thread is /probably/ dead. But it may simply not have quite started yet. Give it a while to join, then check again
                jobthread.join(2)
                if not jobthread.is_alive():
                    self.finishedjobs.append(jobthread)

                # we had an internal error => immediate quit!
                if jobthread.err:
                    # just print it out normally, cron will nab and email it!
                    print(jobthread.err)
                    print(jobthread.job)
                    ok = False

        for jobthread in self.finishedjobs:
            self.runningjobs.remove(jobthread)
            jobthread.job['job_status'] = STATUS_COMPLETE
            self.jq.update_job(jobthread.job)
            # logging.debug('Job has finished {}'.format(jobthread.job['job_pid']))
        return ok

    def compare_trade_pair(self, trade_pair):
        # stop command may have been issued
        self.is_running()
        if not self.running:
            # cancels the interval
            self.compare_trade_pairs_intervals[trade_pair]()

        # logging.info('Now adding compare trade pair jobs')

        # Always run a compare job for each trade pair

        trade_pair_split = trade_pair.split('-')
        curr_x = trade_pair_split[0]
        curr_y = trade_pair_split[1]
        existing_job = self.jq.db[JOB_COLLECTION].find_one({'job_type': 'COMPARE',
                                                            'job_args.curr_x': curr_x,
                                                            'job_args.curr_y': curr_y,
                                                            'job_status':
                                                                {'$in': [STATUS_CREATING,
                                                                         STATUS_RUNNING]
                                                                 }
                                                            })

        if not existing_job:
            # logging.info('Adding comparison job for {}'.format(trade_pair))
            # check for an existing job running under **this** job queue. means old dead RUNNING jobs are ignored.
            self.jq.add_job(
                {
                    'job_type': 'COMPARE',
                    'job_args': {'curr_x': curr_x, 'curr_y': curr_y},
                    'jobqueue_id': self._id
                },
                self._id)
        else:
            logging.debug('Not adding job: Existing job! {}'.format(existing_job))

    def job_finished(self, process):
        retcode = process.wait()
        while retcode != 0:
            self.job_finished(process)
        return

    def is_running(self):
        try:
            self.running = self.jq.db[JOB_STATUS_COLLECTION].find_one({'_id': self._id}).get('running')
        except TypeError:
            self.running = False

    def stop_jobqueue(self):
        self.running = False

        try:
            # cancels the interval
            self.start_jobs_interval()

        except:
            pass

        try:
            # cancel the intervals
            for k in self.compare_trade_pairs_intervals:
                self.compare_trade_pairs_intervals[k]()
        except:
            pass

        self.jq.db.jobs.remove({'job_status': STATUS_RUNNING}, multi=True)

        logging.info('Job queue stopped')


class JobQueueThread(threading.Thread):

    def __init__(self, jq, job, safecmd):
        super(JobQueueThread, self).__init__(target=jq.run_command, args=(job, safecmd))
        self.err = None
        self.safecmd = safecmd
        self.job = job
        self.output = None

    def run(self):
        try:
            super(JobQueueThread, self).run()
        except RunCommandException:
            pass
        except Exception as e:
            if self.safecmd:
                print(self.safecmd)
            if self.job:
                print(self.job)
            raise Exception(e)
            self.err = traceback.format_exc()
        # finally:
        #     runningjobslock.acquire()
        #     runningjobslock.notify()
        #     runningjobslock.release()


class RunCommandException(Exception):
    pass


def call_repeatedly(interval, func, *args):
    stopped = threading.Event()

    def loop():
        while not stopped.wait(interval):  # the first call is in `interval` secs
            ok = func(*args)

    threading.Thread(target=loop).start()
    return stopped.set
