import msal
from msal import PublicClientApplication

import util

SCOPES = ['XboxLive.signin']
app: PublicClientApplication

def init():
    global app
    ids = util.read_json_file("ids.json")

    app = msal.PublicClientApplication(
        ids["CLIENT_ID"],
        authority=f'https://login.microsoftonline.com/consumers'
    )

def ms_signin() -> str:
    accounts = app.get_accounts()

    if accounts:
        print('Found existing account, authenticating')
        result = app.acquire_token_silent(SCOPES, accounts[0])
    else:
        print('No cached account found, opening browser')
        result = app.acquire_token_interactive(
            scopes=SCOPES,
            prompt='select_account',
            port=80
        )

    if 'access_token' in result:
        token = result['access_token']
        print('Access token acquired successfully!')
        print('Token:', token)
        return token
    else:
        print('Error:', result.get('error_description'))

