from sanic import Sanic
from sanic import response
import queue
import configparser
import greenstalk
import json
from threading import Thread
from collections import deque
config = configparser.ConfigParser()
config.read("../config.ini")
#slave_hosts = [i.trim() for i in config["Slave"]["hosts"].split(" ")]

MAX_USER_QUEUE_LEN=1024

req_q = queue.Queue(MAX_USER_QUEUE_LEN)

user_q = deque(maxlen=MAX_USER_QUEUE_LEN)

def master():
    client = greenstalk.Client(host=config["Beanstalkd"]["host"], port=config["Beanstalkd"]["port"], use="job", watch="result")
    while True:
        try:
            job = client.reserve(0.1)
            parsed = json.loads(job.body)
            finished_id = parsed.get("id")
            print("job finished", finished_id)
            rotate_num = 0
            while user_q[0] != finished_id:
                user_q.rotate(-1)
                rotate_num += 1
            user_q.popleft()
            user_q.rotate(rotate_num)
            client.delete(job)
        except greenstalk.TimedOutError:
            pass
        try:
            req = req_q.get(timeout=0.1)
            print("put job queue", req["id"])
            client.put(json.dumps(req))
        except queue.Empty:
            pass

app = Sanic()

@app.route("/queue", methods=['GET'])
async def get_queue(req):
    return response.json([i for i in user_q])

@app.route("/queue", methods=['POST'])
async def put_queue(req):
    try:
        parsed = req.json
        if "id" not in parsed or "op" not in parsed:
            return response.text(str("no op or id field in request"))
        user_q.append(parsed["id"])
        req_q.put(parsed)
        return response.json([i for i in user_q])
    except Exception as e:
        return response.text(str(e))

@app.route("/")
async def index(req):
    return await response.file('./statics/index.html')

app.static('/', './statics')

if __name__ == "__main__":
    try:
        t = Thread(target=master)
        t.start()
        ssl = {'cert': "./ssl/cert.crt", 'key': "./ssl/private.key"}
        app.run(host="0.0.0.0", port=8443, ssl=ssl)
    except Exception as e:
        print(e)
        t.join(100)
        exit()
