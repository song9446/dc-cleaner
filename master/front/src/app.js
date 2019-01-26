var app = {
    post(path, json) {
        return new Promise((resolve, reject) => {
            let xhr = new XMLHttpRequest();
            xhr.open("POST", path);
            xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
            xhr.onload = () => {
                if (xhr.status == 200)
                    try {
                        resolve(xhr.response);
                    }catch(err){
                        reject(err);
                    }
                else
                    reject(`${xhr.responseText}: ${xhr.status}(${xhr.statusText})`)
            };
            xhr.onerror = () => reject(xhr.statusText);
            xhr.send(JSON.stringify(json));
        });
    },
    get(path, json) {
        return new Promise((resolve, reject) => {
            let xhr = new XMLHttpRequest();
            if(json) path += "?" + encodeURI(Object.keys(json).map(key=>`${key}=${json[key]}`).join("&"));
            xhr.open("GET", path);
            xhr.onload = () => {
                if (xhr.status == 200)
                    try {
                        resolve(xhr.response);
                    }catch(err){
                        reject(err);
                    }
                else
                    reject(`${xhr.responseText}: ${xhr.status}(${xhr.statusText})`)
            };
            xhr.onerror = () => reject(xhr.statusText);
            xhr.send();
        });
    },
    set_cookie(cname, cvalue, exdays) {
        var d = new Date();
        d.setTime(d.getTime() + (exdays*24*60*60*1000));
        var expires = "expires="+ d.toUTCString();
        document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
    },
    cookie(cname) {
        cname = encodeURIComponent(cname);
        let ca = document.cookie.split('; ');
        for(let i=0; i<ca.length; ++i) {
            let nv = ca[i].split("=");
            if(nv[0].startsWith(cname))
                return decodeURIComponent(nv[1]);
        }
        return "";
    },
    queue(payload=null){
        if(payload != null)
            return app.post("/queue", payload);
        else
            return app.get("/queue");
    },
};
