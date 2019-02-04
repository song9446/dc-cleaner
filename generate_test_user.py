import dc_api
import time
SOURCES = ["fashion_new1", "pants", "watch", "footwear", "fashion_acc", "tattoo", "cosmetic", "hair"] 
#def fetch_any():
#    gens = [dc_api.board(board_id=i) for i in SOURCES]
#    while True:
#        for i in gens:
#            yield next(i)

"""
dc_api.login("eunchulsong9", "song4627")
while True:
    for k, i in enumerate(dc_api.board("baseball_new6", start_page=1200)):
        imgs = "".join(["<img src='{}'/>".format(src) for src in i["images"]])
        dc_api.write_document("baseball_new7", title=i["title"], contents=imgs + i["contents"])
        time.sleep(60)
        print(i["title"], i["contents"])
"""


dc_api.login("eunchulsong9", "song4627")
while True: 
    try:
        i = sorted([i for i in dc_api.board("baseball_new7", num=10)], key=lambda x: x["comment_num"])[-1]
        print(dc_api.write_comment("baseball_new7", i['id'], contents="ㅋㅋ"))
        time.sleep(30)
    except Exception as e:
        time.sleep(1)
        print(e)
