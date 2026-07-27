import mslogin
import auth
from auth import fetch_profile
import launcher

LAUNCHER_NAME = 'TruckLauncher'

def authorise_for_minecraft():
    access_token = mslogin.ms_signin()
    xbl_token, userhash = auth.auth_xbl(access_token)
    xsts_token, _ = auth.auth_xsts(xbl_token)
    mc_token = auth.auth_mc(userhash, xsts_token)
    if auth.check_ownership(mc_token):
        print("Minecraft License owned")
        return mc_token
    else:
        print("No ownership found")
        return None

def main():
    mslogin.init(LAUNCHER_NAME)
    mc_token = authorise_for_minecraft()
    if mc_token is None:
        return
    mc_profile = fetch_profile(mc_token)
    print(mc_profile)
    username = mc_profile.get("name")
    uuid = mc_profile.get("id")
    print('Username: ' + username)
    print('UUID: ' + uuid)
    print("Launching minecraft")
    launcher.launch('1.21.11', username, uuid, mc_token)

if __name__ == '__main__':
    main()