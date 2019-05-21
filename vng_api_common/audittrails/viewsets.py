import logging

from django.db import transaction

from rest_framework import viewsets

from ..constants import CommonResourceAction
from ..viewsets import NestedViewSetMixin
from .api.serializers import AuditTrailSerializer
from .models import AuditTrail

logger = logging.getLogger(__name__)


class AuditTrailMixin:
    audit = None

    def get_audittrail_main_object_url(self, data, main_resource):
        """
        Retrieve the URL that points to the main resource
        """
        if hasattr(self, 'audittrail_main_resource_key'):
            return data[self.audittrail_main_resource_key]
        return data[main_resource]

    def create_audittrail(self, status_code, action, version_before_edit, version_after_edit, unique_representation):
        """
        Create the audittrail for the action that has been carried out.
        """
        data = version_after_edit if version_after_edit else version_before_edit
        if self.basename == self.audit.main_resource:
            main_object = data['url']
        else:
            main_object = self.get_audittrail_main_object_url(data, self.audit.main_resource)

        # Django 2.2 compatibility
        if hasattr(self.request, 'headers'):
            headers_attr = 'headers'
        else:
            headers_attr = 'META'

        applications = self.request.jwt_auth.applicaties
        if len(applications) > 1:
            logger.warning("Unexpectedly found %d applications, expected at most one", len(applications))

        if applications:
            application = applications[0]
            app_id, app_presentation = str(application.uuid), application.label
        else:
            app_id = getattr(self.request, headers_attr).get('HTTP_X_NLX_REQUEST_APPLICATION_ID')
            app_presentation = app_id  # we don't have any extra information...

        user_id = self.request.jwt_auth.payload.get('user_id', '')
        if not user_id:
            user_id = getattr(self.request, headers_attr).get('HTTP_X_NLX_REQUEST_USER_ID', '')

        trail = AuditTrail(
            bron=self.audit.component_name,
            applicatie_id=app_id,
            applicatie_weergave=app_presentation,
            actie=action,
            actie_weergave=CommonResourceAction.labels.get(action, ''),
            gebruikers_id=user_id,
            gebruikers_weergave=self.request.jwt_auth.payload.get('user_representation', ''),
            resultaat=status_code,
            hoofd_object=main_object,
            resource=self.basename,
            resource_url=data['url'],
            resource_weergave=unique_representation,
            oud=version_before_edit,
            nieuw=version_after_edit,
        )
        trail.save()


class AuditTrailCreateMixin(AuditTrailMixin):
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        instance = self.queryset.order_by('-id')[0]
        self.create_audittrail(
            response.status_code,
            CommonResourceAction.create,
            version_before_edit=None,
            version_after_edit=response.data,
            unique_representation=instance.unique_representation()
        )
        return response


class AuditTrailUpdateMixin(AuditTrailMixin):
    def update(self, request, *args, **kwargs):
        # Retrieve the data stored in the object before updating
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        version_before_edit = serializer.data

        action = CommonResourceAction.partial_update if kwargs.get('partial', False) else CommonResourceAction.update

        response = super().update(request, *args, **kwargs)
        self.create_audittrail(
            response.status_code,
            action,
            version_before_edit=version_before_edit,
            version_after_edit=response.data,
            unique_representation=instance.unique_representation()
        )
        return response


class AuditTrailDestroyMixin(AuditTrailMixin):
    def destroy(self, request, *args, **kwargs):
        # Retrieve the data stored in the object before updating
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        version_before_edit = serializer.data

        # If the resource being deleted is the main resource, delete all the
        # audittrails associated with it
        if self.basename == self.audit.main_resource:
            with transaction.atomic():
                response = super().destroy(request, *args, **kwargs)
                self._destroy_related_audittrails(version_before_edit['url'])
                return response
        else:
            response = super().destroy(request, *args, **kwargs)
            self.create_audittrail(
                response.status_code,
                CommonResourceAction.destroy,
                version_before_edit=version_before_edit,
                version_after_edit=None,
                unique_representation=instance.unique_representation()
            )
            return response

    def _destroy_related_audittrails(self, main_object_url):
        AuditTrail.objects.filter(hoofd_object=main_object_url).delete()


class AuditTrailViewsetMixin(AuditTrailCreateMixin,
                             AuditTrailUpdateMixin,
                             AuditTrailDestroyMixin):
    pass


class AuditTrailViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet that shows the Audit trails for a resource (e.g. a Zaak)

    In order to create an AuditTrailViewSet for a specific resource, this class
    must be inherited from in the viewsets of the component where this resource
    lives, and the `main_resource_lookup_field` must be set to the identifier
    of the resource (usually uuid)

    Example usage for a AuditTrailViewSet for the `Zaak`-resource:

        class ZaakAuditTrailViewset(AuditTrailViewset):
            main_resource_lookup_field = 'zaak_uuid'
    """
    queryset = AuditTrail.objects.all().order_by('aanmaakdatum')
    serializer_class = AuditTrailSerializer
    lookup_field = 'uuid'

    main_resource_lookup_field = None   # Must be overwritten by subclasses

    def get_queryset(self):
        qs = super().get_queryset()
        identifier = self.kwargs.get(self.main_resource_lookup_field)
        if identifier:
            return qs.filter(hoofd_object__contains=identifier)
        return qs
