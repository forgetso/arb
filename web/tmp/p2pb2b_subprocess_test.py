import json, datetime, calendar
import logging
import sys
from subprocess import PIPE, Popen
from threading import Thread
from queue import Queue, Empty  # python 3.x


def main():
    logging.basicConfig(format='%(levelname)s:%(message)s', level='DEBUG')
    cmd = ['python3', 'web/tmp/p2pb2b_test.py']
    execute(cmd, '/home/chris/dev/arb')
    exit(0)
    # env = os.environ.copy()
    # stdin = json_util.dumps({}, ensure_ascii=False, indent=2, cls=JsonEncoder).encode('utf-8')
    # process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    #                            stdin=subprocess.PIPE, env=env, close_fds=True)
    # retcode = process.wait()
    # (stdout, stderr) = process.communicate(stdin)
    #
    # if retcode == 0:
    #     print(stdout.strip().decode('ascii'))
    #     stdout_str = stdout.strip().decode('ascii')
    #     print(stderr.strip().decode('ascii'))


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.date):
            millis = int(calendar.timegm(o.timetuple()) * 1000)
            return {"$date": millis}
        return json.JSONEncoder.default(self, o)


ON_POSIX = 'posix' in sys.builtin_module_names


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


def execute(cmd, path):
    p = Popen(cmd, stdout=PIPE, bufsize=1, close_fds=ON_POSIX, shell=False, cwd=path)
    q = Queue()
    t = Thread(target=enqueue_output, args=(p.stdout, q))
    t.daemon = True  # thread dies with the program
    t.start()
    # read line without blocking
    try:
        line = q.get_nowait()  # or q.get(timeout=.1)
    except Empty:
        print('no output yet')
    else:
        print
        line


for i in range(0, 5):
    main()
