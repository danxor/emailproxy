# A simple SMTP-proxy for sending email using Microsoft 365
This project is a small SMTP-proxy that can be used together with accounts in Microsoft 365. The proxy server accepts emails from any machine that can reach it and sends them using [Microsoft Graph](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0&tabs=http) to recipient provided.

The proxy utilizes the [device authorization](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code) flow against a registered application in [Entra ID](https://www.microsoft.com/en-us/security/business/identity-access/microsoft-entra-id). This enables the proxy to send emails as an actual user in Microsoft 365; i.e. the user that completes the device authorization grant flow.

## Installation

Just build the docker image using the supplied Dockerfile and then start the container using your preferred method.

```console
$ docker build -t danxor/emailproxy .
```

Once you've build the email proxy you can start it in a container with the following command. You will need to supply you own values for atleast *OAUTH2_CLIENT_ID*. How this can get your value is described in the section [Registering an application](#register-an-application)

```console
$ docker run \
    --it \
    --rm \
    --name emailproxy \
    -e SMTP_SERVER_BIND=127.0.0.1 \
    -e SMTP_SERVER_PORT=1587 \
    -e OAUTH2_CLIENT_ID=00000000-0000-0000-0000-000000000000 \
    -e OAUTH2_AUTHORIZE_URL=https://login.microsoftonline.com/common/oauth2/v2.0/devicecode \
    -e OAUTH2_TOKEN_URL=https://login.microsoftonline.com/openbox.se/oauth2/v2.0/token \
    -v ./data:/app/data \
    danxor/emailproxy
```

My use-case is that I use it in conjunction with [Vaultwarden](https://hub.docker.com/r/vaultwarden/server), a self-hosted [Bitwarden](https://bitwarden.com/) API-compatible password vault. Which can be setup with the docker-compose.

```yaml
# Vaultwarden with emailproxy
version: '3.9'

services:
  vaultwarden:
    image: vaultwarden/server
    restart: unless-stopped
    environment:
      SMTP_HOST: emailproxy
      SMTP_FROM: me@example.com
      SMTP_PORT: 1587
      SMTP_SECURITY: off
    volumes:
      - ./vaultwarden-data:/data
    ports:
        - 80:80
    networks:
      - external
      - internal

  emailproxy:
    image: danxor/emailproxy
    restart: unless-stopped
    environment:
      SMTP_SERVER_BIND: 0.0.0.0
      SMTP_SERVER_PORT: 1587
      OAUTH2_CLIENT_ID: 00000000-0000-0000-0000-000000000000 # Change me based on the app registration
      OAUTH2_AUTHORIZE_URL: https://login.microsoftonline.com/common/oauth2/v2.0/devicecode
      OAUTH2_TOKEN_URL: https://login.microsoftonline.com/common/oauth2/v2.0/token
    volumes:
      - ./emailproxy-data:/app/data
    networks:
      - internal

  networks:
    external:
      driver: bridge
      external: true
    internal:
      driver: overlay
```

## Register an application

This section describes what is needed in order to register an application in [Microsoft Entra admin center](https://entra.microsoft.com/azure.com).

1. Sign into [Microsoft Entra admin center](https://entra.microsoft.com/azure.com)</li>
2. Browse to **Identity** > **Applications** > **App registrations** and select **New registration**.
3. Enter a **Name** for your application. This is something which you will see when completing the device authorization grant flow. If you want to change the name later you can do so.
4. Specify who can use the application, sometimes called its *sign-in audience*. In my case I chose **Accounts in this organizational directory only**.
5. Leave **Redirect URI (optional)** blank as its not required for our use-case.
6. Select **Register** to complete the initial app registration.

Once completed you will now see your **App registration**. In the overview pane you can see the value for *OAUTH2_CLIENT_ID* in the field **Application (client) ID**. Congratulations you now have an application that you can authenticate users in your tenant against; however, once the users are authenticated you cannot do much with the access token. Which means that we need to grant **API permissions** to the app registration.

1. In the menu to the left in the pane you need to click **API permissions** and then on the **Add a permission** button.
2. In the side pane you needto select **Microsoft Graph**.
3. Once again in the side pane you need to select **Delegated permissions**. The reason why we use delegated permissions is because we want to use the user that completes the *device authoriztion grant flow* as the sender of the emails.
4. In the same pane you can search for and select the permission **Mail.Send** - *Send mail as a user*.
5. You also need add the permission of **offline_access** - *Maintain access to data you have given it accesss to* in order to have to complete the *device authorization grant flow* every hour.
6. Select the **Add permission** button in order to give the **App registration** the selected permissions.

Congratulations you've now completed the setup of the **App registration** and you can now start sending emails.

## Advanced use cases

Most of the code is written in [Python](https://www.python.org/) and the individual scripts can most of the time be run seperately. Below I will explain what the different scripts are and what they can be used for.

When using this path you can store your settings in a file called **.env**. This file will be loaded by the [config.py](config.py) script and the settings store within it will be used.

### [auth.py](auth.py)

This script is responsible for handling the OAuth2 authentication against Microsoft 365. When run from the command-line the script will make sure that you're authenticated and also ensure that the token-cache is working as intended. Therefore if you run the script multiple times you should only be required to authenticate the first time; once an access token and refresh token has been acquired the script should give you an access token without entering a device code.

```console
$ python auth.py
Please navigate to https://microsoft.com/devicelogin and enter the code XXXXXXXXX to authenticate.
Waiting ...
...
Waiting ...
Access token: eyJ...xxx
Access token: eyJ...xxx
```

If you run the auth.py command again with valid credentials store you will not be asked to authenticate using a code again. The saved credentials will be used which will result in an output like the one below.


```console
$ python auth.py
Access token: eyJ...xxx
Access token: eyJ...xxx
Access token: eyJ...yyy
```

### [smtp.py](smtp.py)

This script will start an SMTP-server that listens on the configured host (*SMTP_SERVER_BIND*) and port (*SMTP_SERVER_PORT*). When the server receives an email it will save it to disc as the file test.eml; overwriting the file if it already exists. This file can also be used to verify sending of emails using the [mail.py](#mailpy) script.

```console
$ python smtp.py
SMTP-server started on 127.0.0.1:1587
```

When you have reached this stage you can try sending emails to the started *SMTP-server* using you preferred method. Any messages send to the server will be stored in the current folder and the filename *test.eml*. The contents of the file will look something like this.

```console
$ cat test.eml
Message-ID: <xxx@example.com>
Subject: Test
...

Test
```

You can send try sending the email that stored in test.eml by using the [mail.py](#mailpy) script.

### [mail.py](mail.py)

This script will try to send an email stored in *test.eml* by using the credentials as configured previously. If you have problems getting an access token you can revisit the [auth.py](#authpy) script.

```console
$ python mail.py
Mail sent to Me <me@example.com>
```

If you get the output above you should have received an email in your inbox from the user that completed the *device authorization grant flow*.