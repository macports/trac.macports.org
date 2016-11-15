#!/usr/bin/env python

"""trac-github-update hook sending mails with git-multimail"""

import sys
import os
import json
import time
from datetime import datetime

import git_multimail
from git_multimail import GenericEnvironment, Config, ConfigurationException, \
                          OutputMailer, ReferenceChange, Revision, Push, \
                          IncrementalDateTime, read_git_output
from github import Github
import trac.env


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

### CLASSES ###

class IncrementalDateTimeWithStartTime(IncrementalDateTime):
    """Simple wrapper to give incremental date/times.

    Each call will result in a date/time a second later than the previous call,
    starting at the time set with set_time(). This can be used to falsify email
    headers, to increase the likelihood that email clients sort the emails
    correctly."""

    start_time = time.time()

    def __init__(self):
        super(IncrementalDateTimeWithStartTime, self).__init__()
        self.time = IncrementalDateTimeWithStartTime.start_time

### MAIN ###

class TracDB(object):

    def __init__(self, tracenvpath):
        self.env = trac.env.Environment(path=tracenvpath, create=False)
        self.cache = {}

    def get_user(self, username):
        if username in self.cache:
            return self.cache[username]
        row = self.env.db_query("""
            SELECT
                s1.value,
                s2.value
            FROM
                session_attribute s1
            LEFT JOIN
                session_attribute s2
            ON
                s1.sid = s2.sid AND
                s1.authenticated = s2.authenticated AND
                s1.name = 'name' AND
                s2.name = 'email'
            WHERE
                s1.authenticated = 1 AND s2.authenticated = 1 AND
                s1.sid = %s AND s2.sid = %s AND
                s1.name = 'name' AND
                s2.name = 'email'
            """, (username, username))
        for name, email in row:
            self.cache[username] = (name, email)
            return self.cache[username]
        return (None, None)

class GitHubAPI(object):

    def __init__(self, githubtoken):
        self.github = Github(githubtoken)
        self.cache = {}

    def get_user(self, username, knownname=None, knownemail=None):
        if username in self.cache:
            return self.cache[username]
        name = knownname
        if not name:
            name = self.github.get_user(username).name
        # GitHub only lists the primary email address in the payload. We do not
        # want to expose it to the public. The profile may not have any public
        # address. Use a static sender email instead.
        email = knownemail
        if not email:
            email = "%s@users.noreply.github.com" % (username,)
        if name and email:
            self.cache[username] = (name, email)
            return self.cache[username]
        return (None, None)


class GitHubWebhookEnvironment(GenericEnvironment):

    def __init__(self, githubtoken, tracenvpath, **kw):
        self._github = GitHubAPI(githubtoken)
        self._tracdb = TracDB(tracenvpath)
        self._data = None
        self._pusher = None
        self._pusher_email = None
        super(GitHubWebhookEnvironment, self).__init__(**kw)

    def load_payload(self, payload):
        self._data = json.loads(payload)
        self._commits = {}
        for commit in self._data['commits']:
            self._commits[commit['id']] = commit
        return self._data

    def _get_username(self, username):
        result = None
        # Get name from Trac DB
        name, _ = self._tracdb.get_user(username)
        if name:
            result = "%s (%s)" % (name, username)
        # If user was not in Trac DB, ask GitHub API
        if not result:
            name, _ = self._github.get_user(username)
            if name:
                result = "%s (%s)" % (name, username)
            else:
                result = username
        return result

    def _get_username_email(self, username, knownname=None, knownemail=None):
        result = None
        # Get name and email from Trac DB
        name, email = self._tracdb.get_user(username)
        if name and email:
            result = "%s <%s>" % (name, email)
        # If user was not in Trac DB, ask GitHub API
        if not result:
            name, email = self._github.get_user(username, knownname, knownemail)
            if name:
                result = "%s <%s>" % (name, email)
            else:
                result = "%s <%s@users.noreply.github.com>" % (username, username)
        return result

    def get_fromaddr(self, change=None):
        if change:
            if isinstance(change, ReferenceChange):
                return self.get_pusher_email()
            elif isinstance(change, Revision):
                author = None
                commit = self._commits[change.rev.sha1]
                if 'username' in commit['author']:
                    username = commit['author']['username']
                    if 'name' in commit['author']:
                        knownname = commit['author']['name']
                    else:
                        knownname = None
                    if 'email' in commit['author']:
                        knownemail = commit['author']['email']
                    else:
                        knownemail = None
                    author = self._get_username_email(username, knownname, knownemail)
                if not author:
                    author = "%s <%s>" % (commit['author']['name'], commit['author']['email'])
                return author.encode('utf-8')
        return super(GitHubWebhookEnvironment, self).get_fromaddr(change)

    def get_pusher(self):
        if self._pusher:
            return self._pusher.encode('utf-8')
        if not self._data:
            return super(GitHubWebhookEnvironment, self).get_pusher()
        username = self._data['pusher']['name']
        self._pusher = self._get_username(username)
        return self._pusher.encode('utf-8')

    def get_pusher_email(self):
        if self._pusher_email:
            return self._pusher_email.encode('utf-8')
        if not self._data:
            return super(GitHubWebhookEnvironment, self).get_pusher_email()
        username = self._data['pusher']['name']
        self._pusher_email = self._get_username_email(username)
        return self._pusher_email.encode('utf-8')

    def get_reply_to_refchange(self, refchange):
        reply_to = []
        reply_to_extra = self.config.get('replyTo')
        if reply_to_extra:
            reply_to.append(reply_to_extra)
        return ", ".join(reply_to).encode('utf-8')

    def get_reply_to_commit(self, revision):
        reply_to = []
        reply_to_extra = self.config.get('replyTo')
        reply_to_committer = None
        commit = self._commits[revision.rev.sha1]
        author = commit['author']
        committer = commit['committer']
        if 'username' in author and 'username' in committer:
            if author['username'] != committer['username']:
                username = commit['committer']['username']
                if 'name' in commit['committer']:
                    knownname = commit['committer']['name']
                else:
                    knownname = None
                if 'email' in commit['committer']:
                    knownemail = commit['committer']['email']
                else:
                    knownemail = None
                reply_to_committer = self._get_username_email(username, knownname, knownemail)
        else:
            if author['email'] != committer['email']:
                name = commit['committer']['name']
                email = commit['committer']['email']
                reply_to_committer = "%s <%s>" % (name, email)
        if reply_to_committer:
            reply_to.append(reply_to_committer)
        if reply_to_extra:
            reply_to.append(reply_to_extra)
        return ", ".join(reply_to).encode('utf-8')

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

    # get committer time of the newest revision that was pushed
    timestamp = read_git_output(['log', '--no-walk', '--format=%ct', change.new.sha1])
    # monkey patch it into git_multimail
    IncrementalDateTimeWithStartTime.start_time = float(timestamp)
    git_multimail.IncrementalDateTime = IncrementalDateTimeWithStartTime

    push = Push(environment, [change])
    push.send_emails(mailer, body_filter=environment.filter_body)

    if hasattr(mailer, '__del__'):
        mailer.__del__()


def main(args):

    # Specify which "git config" section contains the configuration for
    # git-multimail:
    config = Config('multimailhook')

    # GitHub API
    githubtoken = os.getenv("GITHUB_ACCESS_TOKEN")
    if not githubtoken:
        githubtoken = config.get("githubAccessToken")
    if not githubtoken:
        sys.stderr.write("Set GITHUB_ACCESS_TOKEN in environment or " +
                         "'git config multimailhook.githubAccessToken <token>'!\n")
        sys.exit(1)

    # Trac Environment
    tracenvpath = os.getenv("TRAC_ENV")
    if not tracenvpath:
        tracenvpath = config.get("tracEnv")
    if not tracenvpath:
        sys.stderr.write("Set TRAC_ENV in environment or " +
                         "'git config multimailhook.tracEnv <path>'!\n")
        sys.exit(1)

    # Select the type of environment:
    try:
        environment = GitHubWebhookEnvironment(githubtoken, tracenvpath, config=config)
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
