# pygologin

REST API provides programmatic access to GoLogin App. Create a new browser profile, get a list of all browser profiles, add a browser profile and running.

## Not Official Package

## Getting Started

GoLogin supports Linux, MacOS and Windows platforms.

### Installation

`pip install pygologin`

or clone this repository

`git clone https://github.com/at146/pygologin.git`

### Usage

Where is token? API token is [here](https://app.gologin.com/#/personalArea/TokenApi).
To have an access to the page below you need [register](https://app.gologin.com/#/createUser) GoLogin account.

![Token API in Settings](https://user-images.githubusercontent.com/12957968/146891933-c3b60b4d-c850-47a5-8adf-bc8c37372664.gif)

### Methods

#### Constructor

- `options` <[Object]> Options for profile
  - `autoUpdateBrowser` <[boolean]> do not ask whether download new browser version (default false)
    - `token` <[string]> your API [token](https://gologin.com/#/personalArea/TokenApi)
    - `profile_id` <[string]> profile ID
    - `executablePath` <[string]> path to executable Orbita file. Orbita will be downloaded automatically if not specified.
  - `remote_debugging_port` <[int]> port for remote debugging
    - `vncPort` <[integer]> port of VNC server if you using it
  - `tmpdir` <[string]> path to temporary directore for saving profiles
  - `extra_params` arrayof <[string]> extra params for browser orbita (ex. extentions etc.)
  - `uploadCookiesToServer` <[boolean]> upload cookies to server after profile stopping (default false)
  - `writeCookesFromServer` <[boolean]> download cookies from server and write to profile cookies file (default true)
  - `port` <[integer]> Orbita start port (uncomment out the lines with "random port" and "port" in `gologin-selenium.py` to select a random launch port)

## Full GoLogin API

**Swagger:** [GoLogin Swagger Documentation](https://api.gologin.com/docs)

**Postman:** [link here](https://documenter.getpostman.com/view/21126834/Uz5GnvaL)
