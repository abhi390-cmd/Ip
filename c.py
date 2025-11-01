# save_mozilla_cookiejar.py
import requests
import http.cookiejar as cookiejar

s = requests.Session()
s.get("https://www.sheinindia.in/shop/shein")

cj = cookiejar.MozillaCookieJar("cookies.txt")
for c in s.cookies:
    cookie = cookiejar.Cookie(
        version=0, name=c.name, value=c.value,
        port=None, port_specified=False,
        domain=c.domain, domain_specified=bool(c.domain), domain_initial_dot=c.domain.startswith('.'),
        path=c.path, path_specified=True,
        secure=c.secure, expires=c.expires,
        discard=False, comment=None, comment_url=None,
        rest={}, rfc2109=False
    )
    cj.set_cookie(cookie)
cj.save(ignore_discard=True, ignore_expires=True)
print("Saved to cookies.txt")