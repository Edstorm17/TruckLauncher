import mslogin
import auth

def authorise_for_minecraft():
    access_token = mslogin.ms_signin()
    xbl_token, userhash = auth.auth_xbl(access_token)
    xsts_token, _ = auth.auth_xsts(xbl_token)
    mc_token = auth.auth_mc(userhash, xsts_token)

if __name__ == '__main__':
    mslogin.init()
