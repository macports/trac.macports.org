#!/usr/bin/env python

"""trac-github-update hook sending mails with git-multimail"""

import sys
import os
import json

import git_multimail
from git_multimail import GenericEnvironment, Config, ConfigurationException, \
                          OutputMailer, ReferenceChange, Push
from github import Github


### TEMPLATES ###

git_multimail.REFCHANGE_INTRO_TEMPLATE = """\
%(pusher)s pushed a change to %(refname_type)s %(short_refname)s
in repository %(repo_shortname)s.

"""

git_multimail.REVISION_INTRO_TEMPLATE = """\
%(pusher)s pushed a commit to %(refname_type)s %(short_refname)s
in repository %(repo_shortname)s.

"""

git_multimail.COMBINED_INTRO_TEMPLATE = """\
%(pusher)s pushed a commit to %(refname_type)s %(short_refname)s
in repository %(repo_shortname)s.

"""

# Remove footer, unsubscribing is offered by mailing list
git_multimail.FOOTER_TEMPLATE = "\n"
git_multimail.REVISION_FOOTER_TEMPLATE = "\n"
git_multimail.COMBINED_FOOTER_TEMPLATE = "\n"

git_multimail.LINK_TEXT_TEMPLATE = """\
View on GitHub:
%(browse_url)s

"""

git_multimail.LINK_HTML_TEMPLATE = """\
<p><a href="%(browse_url)s">%(browse_url)s</a></p>
"""


### MAIN ###


class GitHubWebhookEnvironment(GenericEnvironment):
    def __init__(self, github, **kw):
        self._github = github
        self._data = None
        self._pusher = None
        self._pusher_email = None
        super(GenericEnvironment, self).__init__(**kw)

    def load_payload(self, payload):
        self._data = json.loads(payload)
        return self._data

    def get_pusher(self):
        if self._pusher:
            return self._pusher
        if not self._data:
            return super(GenericEnvironment).get_pusher()
        login = self._data['pusher']['name'].encode('utf-8')
        realname = self._github.get_user(login).name
        if realname:
            self._pusher = "%s (%s)" % (realname, login)
        else:
            self._pusher = login
        return self._pusher

    def get_pusher_email(self):
        if self._pusher_email:
            return self._pusher_email
        if not self._data:
            return super(GenericEnvironment).get_pusher_email()
        login = self._data['pusher']['name'].encode('utf-8')
        name = self._github.get_user(login).name or login
        # GitHub only lists the primary email address in the payload. We do not
        # want to expose it to the public, and sending with these addresses
        # would also violate SPF. Use a static sender email instead.
        email = "%s@users.noreply.github.com" % (login,)
        self._pusher_email = "%s <%s>" % (name, email)
        return self._pusher_email


def run_as_github_webhook(environment, mailer):
    payload = environment.load_payload(sys.stdin.read())

    environment.check()
    send_filter_regex, send_is_inclusion_filter = environment.get_ref_filter_regex(True)
    ref_filter_regex, is_inclusion_filter = environment.get_ref_filter_regex(False)

    # https://developer.github.com/v3/activity/events/types/#pushevent
    refname = payload['ref'].encode('utf-8')
    oldrev = payload['before'].encode('utf-8')
    newrev = payload['after'].encode('utf-8')

    if not git_multimail.include_ref(refname, ref_filter_regex, is_inclusion_filter):
        return
    if not git_multimail.include_ref(refname, send_filter_regex, send_is_inclusion_filter):
        return

    change = ReferenceChange.create(environment, oldrev, newrev, refname)

    push = Push(environment, [change])
    push.send_emails(mailer, body_filter=environment.filter_body)

    if hasattr(mailer, '__del__'):
        mailer.__del__()


def main(args):

    # Specify which "git config" section contains the configuration for
    # git-multimail:
    config = Config('multimailhook')

    token = os.getenv("GITHUB_ACCESS_TOKEN")
    if not token:
        token = config.get("githubAccessToken")
    if not token:
        sys.stderr.write("Set GITHUB_ACCESS_TOKEN in environment or " +
                         "'git config multimailhook.githubAccessToken <token>'!\n")
        sys.exit(1)

    github = Github(token)

    # Select the type of environment:
    try:
        environment = GitHubWebhookEnvironment(github, config=config)
    except ConfigurationException:
        sys.stderr.write("%s\n" % sys.exc_info()[1])
        sys.exit(1)

    # Choose the method of sending emails based on the git config:
    mailer = git_multimail.choose_mailer(config, environment)

    if "-n" in args:
        # OutputMailer is intended only for testing; it writes the emails to
        # the specified file stream.
        mailer = OutputMailer(sys.stdout)

    # Send notification emails:
    run_as_github_webhook(environment, mailer)

    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])
