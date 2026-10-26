from app.api.endpoints import auth
for r in auth.router.routes:
    print(r.path, r.methods)
