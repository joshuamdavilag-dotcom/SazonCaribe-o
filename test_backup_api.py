import urllib.request, json

# get token
data = json.dumps({'username':'joshi_0211','password':'@0420311001000V'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=data, headers={'Content-Type':'application/json'}, method='POST')
r = urllib.request.urlopen(req)
token = json.loads(r.read())['access_token']

# create backup
req2 = urllib.request.Request('http://127.0.0.1:8000/api/v1/backups/crear', headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, method='POST')
try:
    r2 = urllib.request.urlopen(req2)
    print(r2.read().decode())
except Exception as e:
    print('ERR')
    try:
        print(e.read().decode())
    except:
        print(e)
