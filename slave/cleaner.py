import aiohttp
import asyncio
import json
import math
import time
from tenacity import *

CONNECTION_LIMIT = 8
TIMEOUT = 3
RETRY_NUM = 10
MAX_SEARCH_NUM = 1
DOCS_PER_SEARCH = 10000
DOCS_PER_PAGE = 200

GALLOG_REMOVE_SPEED = 100

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Mobile Safari/537.36",
     }
ALTERNATIVE_GET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.67 Safari/537.36",
    }
XML_HTTP_REQ_HEADERS = {
    "Accept": "*/*",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Mobile Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "X-Requested-With": "XMLHttpRequest",
    }
POST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Mobile Safari/537.36"
    }

import logging
logger = logging.getLogger(__name__)
def log(retry_state):
    if retry_state.attempt_number < 1:
        loglevel = logging.INFO
    else:
        loglevel = logging.WARNING
    logger.log(
        loglevel, 'Retrying %s: attempt %s ended with: %s',
        retry_state.fn, retry_state.attempt_number, retry_state.outcome)


def naive_parse(text, start_token, end_token):
    i = text.find(start_token)
    if i<0: return start_token[0:0]
    else: i += len(start_token)
    j = text.find(end_token, i)
    if j<0: return start_token[0:0]
    return text[i:j]

def naive_parse_all(text, start_token, end_token):
    j=0
    while True:
        i = text.find(start_token, j)
        if i<0: return None
        else: i += len(start_token)
        j = text.find(end_token, i)
        if j<0: return None
        else: 
            yield text[i:j]
            j += len(end_token)

async def wrapper(coru, semaphore, sec):
    async with semaphore:
        r = await coru
        await asyncio.sleep(sec)
        return r
def limited_api(n, sec, corus):
    semaphore = asyncio.Semaphore(n)
    return asyncio.gather(*[wrapper(coru, semaphore, sec) for coru in corus])

class Dc:
    def __init__(self):
        #self.semaphore = asyncio.Semaphore(CONNECTION_LIMIT)
        self.gen_session()
        self.id = None
        self.pw = None
    def gen_session(self):
        connector = aiohttp.TCPConnector(limit=CONNECTION_LIMIT)
        self.sess = aiohttp.ClientSession(connector=connector, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=TIMEOUT))
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        await self.sess.close()
    async def __access(self, token_verify, target_url):
        header = XML_HTTP_REQ_HEADERS
        payload = { "token_verify": token_verify }
        con_key = None
        header["Referer"] = target_url
        async with self.sess.get(target_url) as res:
            #parsed = lxml.html.fromstring(await res.text())
            #con_key = parsed.xpath("//input[@id='con_key']")[0].get("value")
            text = await res.read()
            con_key = naive_parse(text, b'''id="con_key" value="''', b'"').decode()
            csrf = self.__fetch_csrf(text)
            if con_key: payload["con_key"] = con_key
        url = "http://m.dcinside.com/ajax/access"
        async with self.sess.post(url, headers=header, data=payload) as res:
            return naive_parse(await res.read(), b'Block_key":"', b'"').decode(), csrf
    async def login(self, id, pw):
        print("login..", id)
        con_key, _ = await self.__access("dc_login", "http://m.dcinside.com/auth/login?r_url=http://m.dcinside.com/")
        url = "https://dcid.dcinside.com/join/mobile_login_ok_new.php"
        header = POST_HEADERS
        header["Referer"] = "http://m.dcinside.com/"
        payload = {
                "user_id": id,
                "user_pw": pw,
                "id_chk": "on",
                "con_key": con_key,
                "r_url": "http://m.dcinside.com/" }
        async with self.sess.post(url, headers=header, data=payload) as res:
            if "rucode" in await res.text():
                print(await res.text())
                return False
            self.id = id
            self.pw = pw
            return True
    async def logout(self, id, pw):
        self.id = None
        self.pw = None
        return False
    @retry(before_sleep=log, reraise=True, retry=retry_if_exception_type(asyncio.TimeoutError), stop=stop_after_attempt(RETRY_NUM))
    async def __gallery_posts_spos_page(self, gall_id, s_pos, page, nickname, csrf):
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/ajax/response-list"
        header["Referer"] = "http://m.dcinside.com/board/{}?s_type=name&serval={}&page={}".format(gall_id, nickname, page-1)
        header["X-CSRF-TOKEN"] = csrf
        payload = {"id": gall_id, "page": page, "serval": nickname, "s_type": "name", "s_pos": s_pos}
        cookies = {
            "__gat_mobile_search": 1,
            "list_count": 200,
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            no = [int(i) for i in naive_parse_all(text, b'"no":', b",")]
            ip = [i.decode() for i in naive_parse_all(text, b'"ip":"', b'"')]
            return zip(no, ip)
            #return [int(i) for i in naive_parse_all(text, b'"no":', b",")]
    async def __gallery_posts_spos(self, gall_id, s_pos, max_page, nickname, csrf):
        return [j for i in (await asyncio.gather(*(self.__gallery_posts_spos_page(gall_id, s_pos, page, nickname, csrf) for page in range(2, max_page+1)))) for j in i]
    async def __gallery_posts(self, gall_id, nickname):
        print("collect gallery posts..")
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/board/{}?s_type=name&serval={}".format(gall_id, nickname)
        cookies = {
            "__gat_mobile_search": 1,
            "list_count": 200,
        }
        async with self.sess.get(url, cookies=cookies) as res:
            text = await res.read()
            csrf = self.__fetch_csrf(text)
            docids = [int(i) for i in naive_parse_all(text, b'http://m.dcinside.com/board/'+gall_id.encode()+b'/', b'?')]
            ips = [i.split(b'|')[1].decode() for i in naive_parse_all(text, b'="blockInfo">', b'</span>')]
            first_data = list(zip(docids, ips))
        header["Referer"] = url
        url = "http://m.dcinside.com/ajax/response-list"
        header["X-CSRF-TOKEN"] = csrf
        payload = {"id": gall_id, "page": 2, "serval": nickname, "s_type": "name"}
        cookies = {
            "__gat_mobile_search": 1,
            "list_count": 200,
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            docs_num = int(naive_parse(text, b'"num":', b','))
            s_pos = int(naive_parse(text, b'"first_headnum":', b","))
            estimated_page_num = math.ceil(docs_num/DOCS_PER_PAGE)
        docs = await asyncio.gather(*(self.__gallery_posts_spos(gall_id, s_pos+DOCS_PER_SEARCH*i, estimated_page_num, nickname, csrf) for i in range(0, MAX_SEARCH_NUM)))
        return first_data + [j for i in docs for j in i]
    @retry(before_sleep=log, reraise=True, retry=retry_if_exception_type(asyncio.TimeoutError), stop=stop_after_attempt(RETRY_NUM)) 
    async def __remove_gallery_post(self, gall_id, doc_id, pw):
        #async with self.semaphore:
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/confirmpw/{}/{}?mode=del".format(gall_id, doc_id)
        con_key, csrf = await self.__access("board_Del", url)#, conkey_require=False)
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = csrf
        payload = {
            "_token": "",
            "board_pw": pw,
            "id": gall_id,
            "no": doc_id,
            "mode": "del",
            "con_key": con_key
        }
        url = "http://m.dcinside.com/del/board"
        cookies = {
            "m_dcinside_{}".format(gall_id): gall_id,
            "m_dcinside_lately": "{}%7C%uB204%uB974%uC9C0%uB9C8%2C;".format(gall_id),
            "_gat_mobile_all":1, 
            "_gat_m_gall_search":1,
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            if b"\\uc7a0\\uc2dc\\ud6c4" in text: 
                await self.sess.close()
                self.gen_session()
                if self.id is not None:
                    await self.login(self.id, self.pw)
                print("timeout occured..raise timeout error")
                raise asyncio.TimeoutError
            return (naive_parse(text, b'result":', b'}') == b'true')

    async def remove_gallery_posts(self, gall_id, nickname, ip, pw):
        docid_ips = await self.__gallery_posts(gall_id, nickname)
        filtered_doc_id = [docid for docid,_ip in docid_ips if ip==_ip]
        res = await asyncio.gather(*[self.__remove_gallery_post(gall_id, docid, pw) for docid in filtered_doc_id])
        #res = await asyncio.gather(*[self.__remove_gallery_post(gall_id, docid, pw) for docid in filtered_doc_id])
        return res
        
    @retry(before_sleep=log, reraise=True, retry=retry_if_exception_type(asyncio.TimeoutError), stop=stop_after_attempt(RETRY_NUM))
    async def __gallog_page_entries(self, mode, page, csrf):
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/gallog/{}?menu={}".format(self.id, mode)
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = csrf
        url = "http://m.dcinside.com/ajax/response-galloglist"
        payload = {"g_id": self.id, "menu": mode, "page": page, "list_more": 1}
        cookies = {
            "m_gallog_{}".format(self.id): self.id,
            "m_gallog_lately": "{}%7C%uB204%uB974%uC9C0%uB9C8%2C;".format(self.id),
            "_gat_mobile_gallog_G": "1",
            "_gat_mobile_gallog_R": "1"
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            return [int(i) for i in naive_parse_all(text, b'"no":', b",")]
        '''
        url = "http://m.dcinside.com/gallog/{}?menu={}&page={}".format(self.id, mode, page)
        async with self.sess.get(url) as res:
            return [int(i) for i in naive_parse_all(await res.read(), b""""del-rt" no= '""", b"'")]
        '''
    async def __gallog_entries(self, mode):
        print("collect gallog entries..")
        url = "http://m.dcinside.com/gallog/{}?menu={}".format(self.id, mode)
        async with self.sess.get(url) as res:
            text = await res.read()
            csrf = self.__fetch_csrf(text)
            print(text)
            docs_num = int(naive_parse(text, b'<span class="count2">(', b')').replace(b',',b''))
            page_num_upper_bound = docs_num//30+1
        docs = await asyncio.gather(*(self.__gallog_page_entries(mode, i, csrf) for i in range(1, page_num_upper_bound+1)))
        return [j for i in docs for j in i]
    @retry(before_sleep=log, reraise=True, retry=retry_if_exception_type(asyncio.TimeoutError), stop=stop_after_attempt(RETRY_NUM))
    async def __csrf(self, url):
        async with self.sess.get(url) as res:
            return __fetch_csrf(await res.read())
    def __fetch_csrf(self, html):
            return naive_parse(html, b'<meta name="csrf-token" content="', b'"').decode()
    @retry(before_sleep=log, reraise=True, retry=retry_if_exception_type(asyncio.TimeoutError), stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def __remove_gallog_entry(self, mode, docid):
        url = "http://m.dcinside.com/gallog/{}?menu={}".format(self.id, mode)
        con_key, csrf = await self.__access("gallogDel", url)
        header = XML_HTTP_REQ_HEADERS
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = csrf
        url = "http://m.dcinside.com/gallog/log-del"
        payload = {"no": docid,
                   "con_key": con_key,
                   "g_id": self.id}
        cookies = {
            "m_gallog_{}".format(self.id): self.id,
            "m_gallog_lately": "{}%7C%uB204%uB974%uC9C0%uB9C8%2C;".format(self.id),
            "_gat_mobile_gallog_{}".format(mode): "1",
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            if b"\\uc7a0\\uc2dc\\ud6c4" in text: 
                #await self.sess.close()
                #self.gen_session()
                #if self.id is not None:
                #    await self.login(self.id, self.pw)
                print("timeout occured..raise timeout error")
                raise asyncio.TimeoutError
            return (naive_parse(await res.read(), b'result":', b'}') == b'true')
    async def remove_gallog_posts(self):
        if self.id is None: return None
        mode = "G"
        corus = [self.__remove_gallog_entry(mode, docid) for docid in await self.__gallog_entries(mode)]
        if not len(corus):
            return None
        L = 50
        for i in range(len(corus)//L+1):
            await asyncio.gather(*corus[L*i:L*(i+1)])
            await self.sess.close()
            self.gen_session()
            if self.id is not None:
                await self.login(self.id, self.pw)
        #res = await limited_api(10, 1.0, corus)
        #res = await asyncio.gather(*[self.__remove_gallog_entry(mode, docid) for docid in await self.__gallog_entries(mode)])
        return None
    async def remove_gallog_replies(self):
        if self.id is None: return None
        mode = "R"
        corus = [self.__remove_gallog_entry(mode, docid) for docid in await self.__gallog_entries(mode)]
        if not len(corus):
            return None
        L = 50
        for i in range(len(corus)//L+1):
            await asyncio.gather(*corus[L*i:L*(i+1)])
            await self.sess.close()
            self.gen_session()
            if self.id is not None:
                await self.login(self.id, self.pw)
        #res = await limited_api(1, 0.1, corus)
        #res = await asyncio.gather(*[self.__remove_gallog_entry(mode, docid) for docid in await self.__gallog_entries(mode)])
        return None
    async def remove_test(self,docid): 
        return await self.__remove_gallog_entry("G", docid)

async def main():
    async with Dc() as dc:
        await dc.login("s3014", "")
        print(await dc.remove_gallog_posts())
        print(await dc.remove_gallog_replies())
        #print(await dc.remove_gallog_posts())
        #print(await dc.remove_test(10000))
        #print(await dc.remove_gallery_posts("baseball_new7", "ㅇㅇ", "58.126", "1234"))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
