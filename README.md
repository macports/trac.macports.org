# Configuration for MacPorts' Trac instance https://trac.macports.org/

This repository contains the configurations for MacPorts Trac instance except
for the secrets.
	
## Local Install
To run a local copy:

- Install Trac 1.0 in a virtualenv
- Create a database for this Trac environment, for example using SQLite with
  `trac-admin "$TMPDIR/tracenvdummy" initenv MacPorts sqlite:/path/to/this/repo/db/trac.db ; rm -rf $TMPDIR/tracenvdummy`.
  Ignore the dummy environment created in this temporary directory, we only
  need the database, but there is no other way to initalize it.
- To give you admin access, run
  `trac-admin /path/to/this/repo permission add anonymous TRAC_ADMIN`.
- Start a Trac server on port 9000 using
  `tracd --hostname localhost --port 9000 --single-env --auto-reload /path/to/this/repo`.
- Open http://localhost:9000/ in your browser.

The following steps are optional:

- Copy `conf/secrets.ini.example` to `conf/secrets.ini`
- Configure a different database with the connection string in
  `conf/secrets.ini`. See the [Trac documentation on database connection
  strings](https://trac.edgewall.org/wiki/TracEnvironment#DatabaseConnectionStrings)
  for more information.
- Since GitHub login, GitHub group synchronization and GitHub webhooks will not
  work in your test environment, leave `client_id`, `client_secret`,
  `access_token` and `webhook_secret` unconfigured.

## Sending Pull Requests
Feel free to open pull requests for this repository. Talk to
@macports/infrastructure for specific questions and deployment.
