from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend import auth, chat, users
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()
app = FastAPI(title="Nusantara CaRas API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(users.router, prefix="/users", tags=["users"])

@app.get("/")
def root():
    return {"msg": "Nusantara CaRas API running!"}

# Debug: Print all routes when server starts
@app.on_event("startup")
async def startup_event():
    print("=== Registered Routes ===")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            print(f"{route.methods} {route.path}")
    print("========================")
