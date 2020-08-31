from conductor.lib import api_client


def inject_sentry():
    import sentry_sdk
    sentry_sdk.init(dsn='https://76bc995e897d4244860276e2f99bc967@o306892.ingest.sentry.io/5302663',
                    environment=conductor.CONFIG['auth_url'].replace('https://', '').replace('/', ''),
                    in_app_include=['conductor.'])
    with sentry_sdk.configure_scope() as scope:
        bearer = api_client.get_bearer_token()
        account = api_client.account_id_from_jwt(bearer.value)
        scope.user = {'id': account}

