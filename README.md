# Configuration for MacPorts' Trac instance https://trac.macports.org/

This repository contains the configurations for MacPorts Trac instance except
for the secrets.
	
## Local Install
To run a local copy:

- Install Trac 1.0 in a virtualenv
- Copy `conf/secrets.ini.example` to `conf/secrets.ini`
- Configure a database connection string in `conf/secrets.ini`. See the
  [Trac documentation on database connection strings][1] for more information.
- Since GitHub login, GitHub group synchronization and GitHub webhooks will not
  work in your test environment, leave `client_id`, `client_secret`,
  `access_token` and `webhook_secret` unconfigured.
- To give you admin access, run `trac-admin /path/to/this/repo permission add
  anonymous TRAC_ADMIN`
- Start a Trac server on port 9000 using `tracd --port 9000 --single-env
  /path/to/this/repo`.

## Sending Pull Requests
Feel free to open pull requests for this repository. Feel free to ping
@macports/infrastructure.

[1] https://trac.edgewall.org/wiki/TracEnvironment#DatabaseConnectionStrings
