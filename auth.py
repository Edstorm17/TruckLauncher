import requests

def auth_xbl(access_token) -> (str, str):
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

def auth_xsts(xbl_token) -> (str, str):
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