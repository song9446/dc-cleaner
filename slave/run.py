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

async def gallog_post(id, pw):
    async with Dc() as dc:
        await dc.login(id, pw)
        await dc.remove_gallog_posts()

async def gallog_reply(id, pw):
    async with Dc() as dc:
        await dc.login(id, pw)
        await dc.remove_gallog_replies()

async def gallery(gall_id, nickname, ip, pw):
    async with Dc() as dc:
        await dc.remove_gallery_posts(gall_id, nickname, ip, pw)

def worker():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    #loop = asyncio.get_event_loop()
    while True:
        req = reqq.get(True)
        print("start job")
        try:
            if req["op"] == "gallog":
                if req["post"] == True:
                    loop.run_until_complete(gallog_post(req["id"], req["pw"]))
                if req["reply"] == True:
                    loop.run_until_complete(gallog_reply(req["id"], req["pw"]))
            elif req["op"] == "gallery":
                loop.run_until_complete(gallery(req["gall_id"], req["nickname"], req["ip"], req["pw"]))
        except Exception as e:
            print("Error:", e)
        resq.put(True)
        

def fetcher():
    client = greenstalk.Client(host=config["Beanstalkd"]["host"], port=config["Beanstalkd"]["port"], use="result", watch="job")
    while True:
        print("waiting job..")
        job = client.reserve()
        print("get job", job.body)
        parsed = json.loads(job.body)
        reqq.put(parsed)
        while True:
            try:
                client.touch(job)
                resq.get(timeout=0.5)
                client.delete(job)
                client.put(json.dumps({"id": parsed["id"]}))
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
