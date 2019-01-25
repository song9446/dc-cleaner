import aiohttp
import asyncio
import lxml.html
import json

TIMEOUT = 5
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

if __name__ == "__main__":
    print(naive_parse("123456712", "1", "1"))
    print([i for i in naive_parse_all("123456 12 131313 141214", "1", "1")])
class Dc:
    def __init__(self):
        self.sess = aiohttp.ClientSession(headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=TIMEOUT))
    async def __aenter__(self):
        self.csrf = await self.__csrf("http://m.dcinside.com/board/programming")
        return self
    async def __aexit__(self, exc_type, exc, tb):
        await self.sess.close()
    async def __access(self, token_verify, target_url):
        header = XML_HTTP_REQ_HEADERS
        payload = { "token_verify": token_verify }
        con_key = None
        if target_url:
            header["Referer"] = target_url
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
        header["Host"] = "dcid.dcinside.com"
        header["Origin"] = "http://m.dcinside.com"
        payload = {
                "user_id": id,
                "user_pw": pw,
                "id_chk": "on",
                "con_key": con_key,
                "r_url": "http://m.dcinside.com/" }
        async with self.sess.post(url, headers=header, data=payload) as res:
            self.id = id
            return await res.text()
    async def __gallog_docs(self):
        page = 1
        while True:
            url = "http://m.dcinside.com/gallog/{}?menu=G&page={}".format(self.id, page)
            async with self.sess.get(url) as res:
                docs = [i for i in naive_parse_all(await res.read(), b""""del-rt" no= '""", b"'")]
                if not docs: break
                for i in docs: yield i
            page += 1
    async def __csrf(self, url):
        async with self.sess.get(url) as res:
            return naive_parse(await res.read(), b'<meta name="csrf-token" content="', b'"').decode()
    async def __remove_gallog_doc(self, docid):
        url = "http://m.dcinside.com/gallog/{}?menu=G".format(self.id)
        #self.csrf = await self.__csrf(url)
        con_key = await self.__access("gallogDel", url)
        header = XML_HTTP_REQ_HEADERS
        header["Referer"] = url
        header["Origin"] = "http://m.dcinside.com"
        header["Host"] = "m.dcinside.com"
        header["X-CSRF-TOKEN"] = self.csrf
        url = "http://m.dcinside.com/gallog/log-del"
        payload = {"no": docid,
                   "con_key": con_key,
                   "g_id": self.id}
        cookies = {
            "m_gallog_{}".format(self.id): self.id,
            "m_gallog_lately": "{}%7C%uB204%uB974%uC9C0%uB9C8%2C;".format(self.id),
            "_gat_mobile_gallog_G": "1"
        }
        print(payload)
        print(header)
        async with self.sess.post(url, headers=header, data=payload, cookies=cookies) as res:
            return (await res.text(encoding='utf8')).encode().decode()
    async def remove_gallog_docs_all(self):
        async for docid in self.__gallog_docs():
            print(await self.__remove_gallog_doc(docid.decode()))

async def main():
    async with Dc() as dc:
        print(await dc.login("bot123", "1q2w3e4r!"))
        print(await dc.remove_gallog_docs_all())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
