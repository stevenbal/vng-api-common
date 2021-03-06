import warnings
from typing import Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from rest_framework import permissions
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.request import Request

from .scopes import Scope


def get_required_scopes(view) -> Union[Scope, None]:
    if not hasattr(view, 'required_scopes'):
        raise ImproperlyConfigured("The View(Set) must have a `required_scopes` attribute")

    scopes_required = view.required_scopes.get(view.action)
    return scopes_required


def bypass_permissions(request: Request) -> bool:
    """
    Bypass permission checks in DBEUG when using the browsable API renderer
    """
    return settings.DEBUG and isinstance(request.accepted_renderer, BrowsableAPIRenderer)


class ActionScopesRequired(permissions.BasePermission):
    """
    Look at the scopes required for the current action and check that they
    are present in the JWT
    """

    def has_permission(self, request: Request, view) -> bool:
        if bypass_permissions(request):
            return True

        scopes_needed = get_required_scopes(view)
        # TODO: if no scopes are needed, what do???
        warnings.warn("The JWT-Payload based auth is deprecated, it will be "
                      "removed before July 22nd 2019", DeprecationWarning)
        return request.jwt_payload.has_scopes(scopes_needed)


class ScopesRequired(permissions.BasePermission):
    """
    Very simple scope-based permission, does not map to HTTP method or action.
    """

    def has_permission(self, request: Request, view) -> bool:
        # don't enforce them in the browsable API during debugging/development
        if bypass_permissions(request):
            return True

        if not hasattr(view, 'required_scopes'):
            raise ImproperlyConfigured("The View(Set) must have a `required_scopes` attribute")

        warnings.warn("The JWT-Payload based auth is deprecated, it will be "
                      "removed before July 22nd 2019", DeprecationWarning)
        return request.jwt_payload.has_scopes(view.required_scopes)


class ClientIdRequired(permissions.BasePermission):
    """
    Look at the client_id of an object and check that it equals client_id in the JWT
    """

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if bypass_permissions(request):
            return True

        if request.method in permissions.SAFE_METHODS:
            return True
        else:
            warnings.warn("The JWT-Payload based auth is deprecated, it will be "
                          "removed before July 22nd 2019", DeprecationWarning)
            return request.jwt_payload['client_id'] == obj.client_id


class AuthScopesRequired(permissions.BasePermission):
    """
    Look at the scopes required for the current action
    and check that they are present in the AC for this client
    """

    def get_zaaktype(self, obj):
        return None

    def get_vertrouwelijkheidaanduiding(self, obj):
        return None

    def get_zaaktype_from_request(self, request):
        return None

    def get_vertrouwelijkheidaanduiding_from_request(self, request):
        return None

    def has_permission(self, request: Request, view) -> bool:
        if bypass_permissions(request):
            return True

        scopes_required = get_required_scopes(view)
        if view.action == 'create':
            zaaktype = self.get_zaaktype_from_request(request)
            vertrouwelijkheidaanduiding = self.get_vertrouwelijkheidaanduiding_from_request(request)
            return request.jwt_auth.has_auth(scopes_required, zaaktype, vertrouwelijkheidaanduiding)
        elif view.action == 'list':
            return request.jwt_auth.has_auth(scopes_required, None, None)

        return True

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if bypass_permissions(request):
            return True

        scopes_required = get_required_scopes(view)
        zaaktype = self.get_zaaktype(obj)
        vertrouwelijkheidaanduiding = self.get_vertrouwelijkheidaanduiding(obj)
        return request.jwt_auth.has_auth(scopes_required, zaaktype, vertrouwelijkheidaanduiding)
