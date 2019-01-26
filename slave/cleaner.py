import aiohttp
import asyncio
import json
import math
from tenacity import *

TIMEOUT = 1
RETRY_NUM = 100
MAX_SEARCH_NUM = 10
DOCS_PER_SEARCH = 10000
DOCS_PER_PAGE = 200
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

class Dc:
    def __init__(self):
        self.sess = aiohttp.ClientSession(headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=TIMEOUT))
        self.id = None
    async def __aenter__(self):
        self.csrf = await self.__csrf("http://m.dcinside.com/board/programming")
        return self
    async def __aexit__(self, exc_type, exc, tb):
        await self.sess.close()
    async def __access(self, token_verify, target_url, conkey_require=True):
        header = XML_HTTP_REQ_HEADERS
        payload = { "token_verify": token_verify }
        con_key = None
        if target_url: header["Referer"] = target_url
        if target_url and conkey_require:
            async with self.sess.get(target_url) as res:
                #parsed = lxml.html.fromstring(await res.text())
                #con_key = parsed.xpath("//input[@id='con_key']")[0].get("value")
                con_key = naive_parse(await res.read(), b'''id="con_key" value="''', b'"').decode()
                if con_key: payload["con_key"] = con_key
        url = "http://m.dcinside.com/ajax/access"
        async with self.sess.post(url, headers=header, data=payload) as res:
            return naive_parse(await res.read(), b'Block_key":"', b'"').decode()
    async def login(self, id, pw):
        con_key = await self.__access("dc_login", "http://m.dcinside.com/auth/login?r_url=http://m.dcinside.com/")
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
                return False
            self.id = id
            return True
    async def logout(self, id, pw):
        self.id = None
        return False
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __gallery_posts_spos_page(self, gall_id, s_pos, page, nickname):
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/ajax/response-list"
        header["Referer"] = "http://m.dcinside.com/board/{}?s_type=name&serval={}&page={}".format(gall_id, nickname, page-1)
        header["X-CSRF-TOKEN"] = self.csrf
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
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __gallery_posts_spos(self, gall_id, s_pos, max_page, nickname):
        return [j for i in (await asyncio.gather(*(self.__gallery_posts_spos_page(gall_id, s_pos, page, nickname) for page in range(1, max_page+1)))) for j in i]
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __gallery_posts(self, gall_id, nickname):
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/ajax/response-list"
        header["Referer"] = "http://m.dcinside.com/board/{}?s_type=name&serval={}".format(gall_id, nickname)
        header["X-CSRF-TOKEN"] = self.csrf
        payload = {"id": gall_id, "page": 1, "serval": nickname, "s_type": "name"}
        cookies = {
            "__gat_mobile_search": 1,
            "list_count": 30,
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            docs_num = int(naive_parse(text, b'"num":', b','))
            s_pos = int(naive_parse(text, b'"first_headnum":', b","))
            estimated_page_num = math.ceil(docs_num/DOCS_PER_PAGE)
        docs = await asyncio.gather(*(self.__gallery_posts_spos(gall_id, s_pos+DOCS_PER_SEARCH*i, estimated_page_num, nickname) for i in range(0, MAX_SEARCH_NUM)))
        return [j for i in docs for j in i]
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __remove_gallery_post(self, gall_id, doc_id, pw):
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/confirmpw/{}/{}?mode=del".format(gall_id, doc_id)
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = self.csrf
        con_key = await self.__access("board_Del", url)#, conkey_require=False)
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
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            text = await res.read()
            return (naive_parse(text, b'result":', b'}') == b'true')
        
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __gallog_page_entries(self, mode, page):
        header = XML_HTTP_REQ_HEADERS
        url = "http://m.dcinside.com/gallog/{}?menu={}".format(self.id, mode)
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = self.csrf
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
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __gallog_entries(self, mode):
        url = "http://m.dcinside.com/gallog/{}?menu={}".format(self.id, mode)
        async with self.sess.get(url) as res:
            text = await res.read()
            docs_num = int(naive_parse(text, b'<span class="count2">(', b')').replace(b',',b''))
            page_num_upper_bound = docs_num//30+10
        docs = await asyncio.gather(*(self.__gallog_page_entries(mode, i) for i in range(1, page_num_upper_bound)))
        return [j for i in docs for j in i]
    async def __csrf(self, url):
        async with self.sess.get(url) as res:
            return naive_parse(await res.read(), b'<meta name="csrf-token" content="', b'"').decode()
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def __remove_gallog_entry(self, mode, docid):
        url = "http://m.dcinside.com/gallog/{}?menu={}".format(self.id, mode)
        #self.csrf = await self.__csrf(url)
        con_key = await self.__access("gallogDel", url)
        header = XML_HTTP_REQ_HEADERS
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = self.csrf
        url = "http://m.dcinside.com/gallog/log-del"
        payload = {"no": docid,
                   "con_key": con_key,
                   "g_id": self.id}
        cookies = {
            "m_gallog_{}".format(self.id): self.id,
            "m_gallog_lately": "{}%7C%uB204%uB974%uC9C0%uB9C8%2C;".format(self.id),
            "_gat_mobile_gallog_G": "1",
            "_gat_mobile_gallog_R": "1"
        }
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            return (naive_parse(await res.read(), b'result":', b'}') == b'true')
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def remove_gallog_posts(self):
        if self.id is None: return None
        mode = "G"
        res = await asyncio.gather(*[self.__remove_gallog_entry(mode, docid) for docid in await self.__gallog_entries(mode)])
    @retry(stop=stop_after_attempt(RETRY_NUM))
    async def remove_gallog_replies(self):
        if self.id is None: return None
        mode = "R"
        res = await asyncio.gather(*[self.__remove_gallog_entry(mode, docid) for docid in await self.__gallog_entries(mode)])
    #@retry(stop=stop_after_attempt(RETRY_NUM))
    async def remove_gallery_posts(self, gall_id, nickname, ip, pw):
        docid_ips = await self.__gallery_posts(gall_id, nickname)
        filtered_doc_id = [docid for docid,_ip in docid_ips if ip==_ip]
        res = await asyncio.gather(*[self.__remove_gallery_post(gall_id, docid, pw) for docid in filtered_doc_id])
        return res

async def main():
    async with Dc() as dc:
        print(await dc.remove_gallery_posts("programming", "ㅇㅇ", "1234", "182.215"))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
