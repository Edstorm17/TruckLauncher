import atexit
import os.path
import msal
import platform
from msal import PublicClientApplication
from msal_extensions import (
    FilePersistenceWithDataProtection,
    KeychainPersistence,
    LibsecretPersistence,
    PersistedTokenCache
)

import util

LAUNCHER_NAME: str

SCOPES = ['XboxLive.signin', 'XboxLive.offline_access']
cache_path = 'token_cache.bin'

app: PublicClientApplication

def init(launcher_name):
    global LAUNCHER_NAME
    global app
    LAUNCHER_NAME = launcher_name
    ids = util.read_json_file("ids.json")

    app = msal.PublicClientApplication(
        ids["CLIENT_ID"],
        authority=f'https://login.microsoftonline.com/consumers',
        token_cache=get_encrypted_cache(),
    )

def get_encrypted_cache():
    if platform.system() == 'Windows':
        persistence = FilePersistenceWithDataProtection(cache_path)
    elif platform.system() == 'Darwin':
        persistence = KeychainPersistence(
            cache_path,
            service_name=LAUNCHER_NAME,
            account_name='MinecraftPlayer'
        )
    elif platform.system() == 'Linux':
        persistence = LibsecretPersistence(
            cache_path,
            schema_name='me.edstorm17.trucklauncher',
            attributes={"application": LAUNCHER_NAME}
        )
    else:
        raise Exception('Unsupported platform')

    return PersistedTokenCache(persistence)

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
        raise Exception('Error obtaining microsoft access token', result.get('error_description'))

