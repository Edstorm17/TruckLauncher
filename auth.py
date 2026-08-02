import requests
import jwt

import mslogin

def authorise_for_minecraft():
    access_token = mslogin.ms_signin()
    xbl_token, userhash = auth_xbl(access_token)
    xsts_token, _ = auth_xsts(xbl_token)
    mc_token = auth_mc(userhash, xsts_token)
    if check_ownership(mc_token):
        print("Minecraft License owned")
        return mc_token
    else:
        print("No ownership found")
        return None

def auth_xbl(access_token) -> tuple[str, str]:
    url = "https://user.auth.xboxlive.com/user/authenticate"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"d={access_token}"
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        xbl_token = data.get("Token")
        userhash = data["DisplayClaims"]["xui"][0].get("uhs")
        print("XboxLive token: ", xbl_token)
        print("UserHash: ", userhash)
        return xbl_token, userhash
    else:
        raise Exception("Failed to authenticate with Xbox Live", response.status_code)

def auth_xsts(xbl_token) -> tuple[str, str]:
    url = "https://xsts.auth.xboxlive.com/xsts/authorize"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "Properties": {
            "SandboxId": "RETAIL",
            "UserTokens": [
                xbl_token
            ]
        },
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        xsts_token = data.get("Token")
        userhash = data["DisplayClaims"]["xui"][0].get("uhs")
        print("XSTS token: ", xsts_token)
        print("UserHash: ", userhash)
        return xsts_token, userhash
    else:
        raise Exception("Failed to authenticate with XSTS", response.status_code)

def auth_mc(userhash, xsts_token) -> str:
    url = "https://api.minecraftservices.com/authentication/login_with_xbox"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "identityToken": f"XBL3.0 x={userhash};{xsts_token}"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        mc_token = data.get("access_token")
        print("Minecraft token: ", mc_token)
        return mc_token
    else:
        raise Exception("Failed to authenticate with Minecraft", response.status_code)

def check_ownership(mc_token) -> bool:
    url = "https://api.minecraftservices.com/entitlements/mcstore"
    headers = {
        "Authorization": f"Bearer {mc_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if len(data.get("items")) == 0:
            return False
        entitlements = verify_signature(data.get("signature"))
        if not entitlements:
            return False
        elif "game_minecraft" in entitlements:
            return True
        return False
    else:
        raise Exception("Failed to check game ownership", response.status_code)

def fetch_profile(mc_token) -> dict:
    url = "https://api.minecraftservices.com/minecraft/profile"
    headers = {
        "Authorization": f"Bearer {mc_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        profile_data = response.json()
        return profile_data
    else:
        raise Exception("Failed to fetch profile", response.status_code)

def verify_signature(jwt_token) -> list:
    with open('public_key.txt', 'r', encoding='utf-8') as f:
        mojang_public_key = f.read()
    payload = jwt.decode(jwt_token, mojang_public_key, algorithms=['RS256'], leeway=10)
    entitlements = [item.get("name") for item in payload.get("entitlements", [])]
    return entitlements