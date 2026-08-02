import threading
import config
import auth
import mslogin
import ui

def main():
    ui_thread = threading.Thread(target=ui.begin)
    ui_thread.start()

    mslogin.init()
    mc_token = auth.authorise_for_minecraft()
    if mc_token is None:
        return
    config.TOKEN = mc_token

    mc_profile = auth.fetch_profile(mc_token)
    config.USERNAME = mc_profile["name"]
    config.UUID = mc_profile["id"]
    print('Username:', config.USERNAME)
    print('UUID:', config.UUID)

    ui_thread.join()

if __name__ == '__main__':
    main()