import urllib.request, json
data = json.dumps({'username':'joshi_0211','password':'@0420311001000V'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=data, headers={'Content-Type':'application/json'}, method='POST')
try:
    r = urllib.request.urlopen(req)
    print(r.read().decode())
except Exception as e:
    print('ERR')
    print(e)
    try:
        print(e.read().decode())
    except:
        pass
