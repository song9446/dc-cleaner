import queue
from cleaner import Dc
import asyncio
import greenstalk
import configparser
import json
from threading import Thread

config = configparser.ConfigParser()
config.read("../config.ini")

reqq = queue.Queue()
resq = queue.Queue()

async def majorgall(id, pw):
    async with Dc() as dc:
        await dc.login(id, pw)
        await dc.remove_gallog_posts()
        await dc.remove_gallog_replies()

def worker():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    #loop = asyncio.get_event_loop()
    while True:
        id, pw = reqq.get(True)
        print("start job", id, pw)
        try:
            loop.run_until_complete(majorgall(id, pw))
        except Exception as e:
            print(e)
        resq.put(True)
        

def fetcher():
    client = greenstalk.Client(host=config["Beanstalkd"]["host"], port=config["Beanstalkd"]["port"], use="result", watch="job")
    while True:
        print("wating job..")
        job = client.reserve()
        print("get job", job.body)
        parsed = json.loads(job.body)
        id, pw = parsed["id"], parsed["pw"]
        reqq.put((id, pw))
        while True:
            try:
                client.touch(job)
                resq.get(timeout=0.5)
                client.delete(job)
                client.put(json.dumps({"id": id}))
                break
            except queue.Empty:
                continue
            except Exception as e:
                print(e)
                client.release(job)
                break

if __name__ == "__main__":
    try:
        t = Thread(target=worker)
        t.start()
        fetcher()
    except Exception as e:
        print(e)
        t.join()
