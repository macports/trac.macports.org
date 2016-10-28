#!/usr/bin/env python

"""trac-github-update hook sending mails with git-multimail"""

import sys
import json

import git_multimail
from git_multimail import GenericEnvironment, Config, ConfigurationException, \
                          OutputMailer, ReferenceChange, Push

# Remove footer, unsubscribing is offered by mailing list
git_multimail.FOOTER_TEMPLATE = "\n"
git_multimail.REVISION_FOOTER_TEMPLATE = "\n"
git_multimail.COMBINED_FOOTER_TEMPLATE = "\n"



class GitHubWebhookEnvironment(GenericEnvironment):
    def __init__(self, **kw):
        self._data = None
        super(GenericEnvironment, self).__init__(**kw)

    def load_payload(self, payload):
        self._data = json.loads(payload)
        return self._data

    def get_pusher(self):
        if not self._data:
            return super(GenericEnvironment).get_pusher()
        return self._data['pusher']['name'].encode('utf-8')

    def get_pusher_email(self):
        if not self._data:
            return super(GenericEnvironment).get_pusher_email()
        # GitHub always lists the primary email address in the payload,
        # but we do not want to expose those to the public
        # XXX: in lack of a better solution, always use a static sender email
        name = self._data['pusher']['name'].encode('utf-8')
        email = "%s@users.noreply.github.com" % (name,)
        return "%s <%s>" % (name, email)


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

    # Select the type of environment:
    try:
        environment = GitHubWebhookEnvironment(config=config)
    except ConfigurationException:
        sys.stderr.write("%s\n" % sys.exc_info()[1])
        sys.exit(1)

    # Choose the method of sending emails based on the git config:
    mailer = git_multimail.choose_mailer(config, environment)

    # OutputMailer is intended only for testing; it writes the emails to
    # the specified file stream.
    #mailer = OutputMailer(sys.stdout)

    # Send notification emails:
    run_as_github_webhook(environment, mailer)

    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])
