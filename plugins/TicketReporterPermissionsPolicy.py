# -*- coding: utf-8 -*-

# This is based on an example from the Trac CookBook:
# https://trac.edgewall.org/wiki/CookBook/PermissionPolicies#GrantapermissiontotheTicketOwner

from trac.core import *
from trac.perm import IPermissionPolicy
from trac.resource import ResourceNotFound
from trac.ticket.model import Ticket


class TicketReporterPermissionsPolicy(Component):
    """Grants permissions to the ticket reporter."""

    implements(IPermissionPolicy)

    allowed_actions = (
        'TICKET_CHGPROP',
        'TICKET_EDIT_DESCRIPTION')

    # IPermissionPolicy methods

    def check_permission(self, action, username, resource, perm):
        if action in self.allowed_actions and \
                resource is not None and \
                resource.realm == 'ticket' and \
                resource.id is not None:
            try:
                ticket = Ticket(self.env, resource.id)
            except ResourceNotFound:
                pass
            else:
                if ticket['reporter'] == username:
                    return True
