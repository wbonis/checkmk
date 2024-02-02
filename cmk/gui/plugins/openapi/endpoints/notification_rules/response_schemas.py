#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from collections.abc import Mapping
from typing import Any, cast, get_args

from marshmallow import post_dump, pre_dump

from cmk.utils.type_defs import (
    BuiltInPluginNames,
    EmailBodyElementsType,
    GroupbyType,
    IlertPriorityType,
    OpsGeniePriorityStrType,
    PluginOptions,
    PushOverPriorityStringType,
    RegexModes,
    SoundType,
    SysLogFacilityStrType,
    SysLogPriorityStrType,
)

from cmk.gui.fields import (
    AuxTagIDField,
    FolderIDField,
    IPField,
    PasswordStoreIDField,
    ServiceLevelField,
    TagGroupIDField,
)
from cmk.gui.fields.utils import BaseSchema
from cmk.gui.plugins.openapi.endpoints.notification_rules.request_example import (
    notification_rule_request_example,
)
from cmk.gui.plugins.openapi.restful_objects.response_schemas import (
    DomainObject,
    DomainObjectCollection,
)
from cmk.gui.rest_api_types.notifications_rule_types import PluginType
from cmk.gui.watolib.tags import load_all_tag_config_read_only

from cmk import fields


class Checkbox(BaseSchema):
    state = fields.String(
        enum=["enabled", "disabled"],
        description="To enable or disable this field",
        example="enabled",
    )


class CheckboxWithStrValue(Checkbox):
    value = fields.String()


class CheckboxWithListOfStr(Checkbox):
    value = fields.List(fields.String)


class SysLogToFromPriorities(BaseSchema):
    from_priority = fields.String(
        enum=list(get_args(SysLogPriorityStrType)),
        example="warning",
        description="",
    )
    to_priority = fields.String(
        enum=list(get_args(SysLogPriorityStrType)),
        example="warning",
        description="",
    )


class CheckboxWithSysLogPriority(Checkbox):
    value = fields.Nested(SysLogToFromPriorities)


class EventConsoleAlertAttrsResponse(BaseSchema):
    match_rule_ids = fields.Nested(CheckboxWithListOfStr)
    match_syslog_priority = fields.Nested(CheckboxWithSysLogPriority)
    match_syslog_facility = fields.Nested(CheckboxWithStrValue)
    match_event_comment = fields.Nested(CheckboxWithStrValue)


class EventConsoleAlertsResponse(Checkbox):
    match_type = fields.String(
        enum=["match_only_event_console_alerts", "do_not_match_event_console_alerts"],
        example="match_only_event_console_events",
        description="",
    )
    values = fields.Nested(EventConsoleAlertAttrsResponse)

    @post_dump
    def _post_dump(self, data, many, **kwargs):
        if data.get("values") == {}:
            del data["values"]
        return data


class MatchEventConsoleAlertsResponse(Checkbox):
    value = fields.Nested(EventConsoleAlertsResponse)


class CheckboxLabel(BaseSchema):
    key = fields.String(example="cmk/os_family")
    value = fields.String(example="linux")


class CheckboxWithListOfLabels(Checkbox):
    value = fields.List(
        fields.Nested(CheckboxLabel),
        description="A list of key, value label pairs",
    )


class ServiceGroupsRegex(BaseSchema):
    match_type = fields.String(
        enum=list(get_args(RegexModes)),
        example="match_alias",
    )
    regex_list = fields.List(
        fields.String,
        uniqueItems=True,
        example=["[A-Z]+123", "[A-Z]+456"],
        description="The text entered in this list is handled as a regular expression pattern",
    )


class CheckboxWithListOfServiceGroupsRegex(Checkbox):
    value = fields.Nested(
        ServiceGroupsRegex,
        description="The service group alias must not match one of the following regular expressions. For host events this condition is simply ignored. The text entered here is handled as a regular expression pattern. The pattern is applied as infix search. Add a leading ^ to make it match from the beginning and/or a tailing $ to match till the end of the text. The match is performed case sensitive. Read more about regular expression matching in Checkmk in our user guide. You may paste a text from your clipboard which contains several parts separated by ';' characters into the last input field. The text will then be split by these separators and the single parts are added into dedicated input field",
    )


class CustomMacro(BaseSchema):
    macro_name = fields.String(
        description="The name of the macro",
        example="macro_1",
    )
    match_regex = fields.String(
        description="The text entered here is handled as a regular expression pattern",
        example="[A-Z]+",
    )


class MatchCustomMacros(Checkbox):
    value = fields.List(fields.Nested(CustomMacro))


class CheckboxWithFolderStr(Checkbox):
    value = FolderIDField(
        description="This condition makes the rule match only hosts that are managed via WATO and that are contained in this folder - either directly or in one of its subfolders.",
    )


class MatchHostTags(BaseSchema):
    tag_type = fields.String(
        example="aux_tag",
        description="If it's an aux tag id or a group tag tag id.",
    )
    tag_group_id = TagGroupIDField(
        example="agent",
        required=False,
        description="If the tag_type is 'tag_group', the id of that group is shown here.",
    )
    operator = fields.String(
        description="This describes the matching action",
    )
    tag_id = AuxTagIDField(
        example="checkmk-agent",
        description="Tag groups tag ids are available via the host tag group endpoint.",
    )


class CheckboxMatchHostTags(Checkbox):
    value = fields.List(fields.Nested(MatchHostTags))

    @pre_dump(pass_many=True)
    def pre_dump(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        tag_config = load_all_tag_config_read_only()
        aux_tags = [tag.id for tag in tag_config.aux_tag_list]
        tag_groups_n_tags = [
            (group.id, [tag.id for tag in group.tags]) for group in tag_config.tag_groups
        ]

        if (raw_value := data.get("value")) is not None:
            data["value"] = []

            for tag_id in raw_value:
                raw_id = tag_id.replace("!", "")
                if raw_id in aux_tags:
                    auxtag = {
                        "tag_type": "aux_tag",
                        "tag_id": raw_id,
                        "operator": "is_not_set" if tag_id[0] == "!" else "is_set",
                    }
                    data["value"].append(auxtag)

                for tag_group_id, tag_ids in tag_groups_n_tags:
                    if raw_id in tag_ids:
                        grouptag = {
                            "tag_type": "tag_group",
                            "tag_group_id": tag_group_id,
                            "operator": "is_not" if tag_id[0] == "!" else "is",
                            "tag_id": raw_id,
                        }
                        data["value"].append(grouptag)

        return data


class FromToNotificationNumbers(BaseSchema):
    beginning_from = fields.Integer(
        example=1,
        description="Let through notifications counting from this number. The first notification always has the number 1",
    )
    up_to = fields.Integer(
        example=999999,
        description="Let through notifications counting upto this number",
    )


class CheckboxRestrictNotificationNumbers(Checkbox):
    value = fields.Nested(FromToNotificationNumbers)


class ThrottlePeriodicNotifications(BaseSchema):
    beginning_from = fields.Integer(
        example=10,
        description="Beginning notification number",
    )
    send_every_nth_notification = fields.Integer(
        example=5,
        description="The rate then you will receive the notification 1 through 10 and then 15, 20, 25... and so on",
    )


class CheckboxThrottlePeriodicNotifcations(Checkbox):
    value = fields.Nested(ThrottlePeriodicNotifications)


class FromToServiceLevels(BaseSchema):
    from_level = ServiceLevelField()
    to_level = ServiceLevelField()


class CheckboxWithFromToServiceLevels(Checkbox):
    value = fields.Nested(
        FromToServiceLevels,
        description="Host or service must be in the following service level to get notification",
    )


class HostOrServiceEventTypeCommon(BaseSchema):
    start_or_end_of_flapping_state = fields.Boolean(example=True)
    start_or_end_of_scheduled_downtime = fields.Boolean(example=True)
    acknowledgement_of_problem = fields.Boolean(example=False)
    alert_handler_execution_successful = fields.Boolean(example=True)
    alert_handler_execution_failed = fields.Boolean(example=False)


class HostEventType(HostOrServiceEventTypeCommon):
    up_down = fields.Boolean(example=True)
    up_unreachable = fields.Boolean(example=False)
    down_up = fields.Boolean(example=True)
    down_unreachable = fields.Boolean(example=False)
    unreachable_down = fields.Boolean(example=False)
    unreachable_up = fields.Boolean(example=False)
    any_up = fields.Boolean(example=False)
    any_down = fields.Boolean(example=True)
    any_unreachable = fields.Boolean(example=True)


class ServiceEventType(HostOrServiceEventTypeCommon):
    ok_warn = fields.Boolean(example=True)
    ok_ok = fields.Boolean(example=True)
    ok_crit = fields.Boolean(example=False)
    ok_unknown = fields.Boolean(example=True)
    warn_ok = fields.Boolean(example=False)
    warn_crit = fields.Boolean(example=False)
    warn_unknown = fields.Boolean(example=False)
    crit_ok = fields.Boolean(example=True)
    crit_warn = fields.Boolean(example=True)
    crit_unknown = fields.Boolean(example=True)
    unknown_ok = fields.Boolean(example=True)
    unknown_warn = fields.Boolean(example=True)
    unknown_crit = fields.Boolean(example=True)
    any_ok = fields.Boolean(example=False)
    any_warn = fields.Boolean(example=False)
    any_crit = fields.Boolean(example=True)
    any_unknown = fields.Boolean(example=False)


class CheckboxHostEventType(Checkbox):
    value = fields.Nested(
        HostEventType,
        description="Select the host event types and transitions this rule should handle. Note: If you activate this option and do not also specify service event types then this rule will never hold for service notifications! Note: You can only match on event types created by the core.",
    )


class CheckboxServiceEventType(Checkbox):
    value = fields.Nested(
        ServiceEventType,
        description="Select the service event types and transitions this rule should handle. Note: If you activate this option and do not also specify host event types then this rule will never hold for host notifications! Note: You can only match on event types created by the core",
    )


# Plugin Responses --------------------------------------------------
class PluginName(BaseSchema):
    plugin_name = fields.String(
        enum=list(get_args(BuiltInPluginNames)),
        description="The plugin name.",
        example="mail",
    )


class EmailAndDisplayName(BaseSchema):
    address = fields.String(
        description="",
        example="mat@tribe29.com",
    )
    display_name = fields.String(
        description="",
        example="",
    )


class FromEmailAndNameCheckbox(Checkbox):
    value = fields.Nested(
        EmailAndDisplayName,
        description="The email address and visible name used in the From header of notifications messages. If no email address is specified the default address is OMD_SITE@FQDN is used. If the environment variable OMD_SITE is not set it defaults to checkmk",
    )


class ToEmailAndNameCheckbox(Checkbox):
    value = fields.Nested(
        EmailAndDisplayName,
        description="The email address and visible name used in the Reply-To header of notifications messages",
    )


class SubjectForHostNotificationsCheckbox(Checkbox):
    value = fields.String(
        description="Here you are allowed to use all macros that are defined in the notification context.",
        example="Check_MK: $HOSTNAME$ - $EVENT_TXT$",
    )


class SubjectForServiceNotificationsCheckbox(Checkbox):
    value = fields.String(
        description="Here you are allowed to use all macros that are defined in the notification context.",
        example="Check_MK: $HOSTNAME$/$SERVICEDESC$ $EVENT_TXT$",
    )


class CheckboxSortOrderValue(Checkbox):
    value = fields.String(
        enum=["oldest_first", "newest_first"],
        description="With this option you can specify, whether the oldest (default) or the newest notification should get shown at the top of the notification mail",
        example="oldest_first",
    )


class MailCommonParams(PluginName):
    from_details = fields.Nested(FromEmailAndNameCheckbox)
    reply_to = fields.Nested(ToEmailAndNameCheckbox)
    subject_for_host_notifications = fields.Nested(SubjectForHostNotificationsCheckbox)
    subject_for_service_notifications = fields.Nested(SubjectForServiceNotificationsCheckbox)
    sort_order_for_bulk_notificaions = fields.Nested(CheckboxSortOrderValue)
    send_separate_notification_to_every_recipient = fields.Nested(Checkbox)


# Ascii Email -------------------------------------------------------


class AsciiEmailParamsResponse(MailCommonParams):
    body_head_for_both_host_and_service_notifications = fields.Nested(CheckboxWithStrValue)
    body_tail_for_host_notifications = fields.Nested(CheckboxWithStrValue)
    body_tail_for_service_notifications = fields.Nested(CheckboxWithStrValue)


# HTML Email --------------------------------------------------------


class CheckboxWithListOfEmailInfoStrs(Checkbox):
    value = fields.List(
        fields.String(enum=list(get_args(EmailBodyElementsType))),
        description="Information to be displayed in the email body.",
        example=["abstime", "graph"],
        uniqueItems=True,
    )


class HtmlSectionBetweenBodyAndTableCheckbox(Checkbox):
    value = fields.String(
        description="Insert HTML section between body and table",
        example="<HTMLTAG>CONTENT</HTMLTAG>",
    )


class URLPrefixForLinksToCheckMk(BaseSchema):
    option = fields.String(
        enum=["manual", "automatic"],
        example="automatic",
    )
    schema = fields.String(
        enum=["http", "https"],
        example="http",
    )
    url = fields.String(
        example="http://example_url_prefix",
    )


class URLPrefixForLinksToCheckMkCheckbox(Checkbox):
    value = fields.Nested(
        URLPrefixForLinksToCheckMk,
        description="If you use Automatic HTTP/s, the URL prefix for host and service links within the notification is filled automatically. If you specify an URL prefix here, then several parts of the notification are armed with hyperlinks to your Check_MK GUI. In both cases, the recipient of the notification can directly visit the host or service in question in Check_MK. Specify an absolute URL including the .../check_mk/",
    )


class Authentication(BaseSchema):
    method = fields.String(
        enum=["plaintext"],
        description="",
        example="plaintext",
    )
    user = fields.String(
        description="",
        example="",
    )
    password = fields.String(
        description="",
        example="",
    )


class AuthenticationValue(Checkbox):
    value = fields.Nested(Authentication)


class EnableSynchronousDeliveryViaSMTP(BaseSchema):
    auth = fields.Nested(
        AuthenticationValue,
    )
    encryption = fields.String(
        description="",
        example="ssl/tls",
    )
    port = fields.Integer(
        description="",
        example=25,
    )
    smarthosts = fields.List(
        fields.String(),
        uniqueItems=True,
    )


class EnableSynchronousDeliveryViaSMTPValue(Checkbox):
    value = fields.Nested(EnableSynchronousDeliveryViaSMTP)


class GraphsPerNotification(Checkbox):
    value = fields.Integer(
        description="Sets a limit for the number of graphs that are displayed in a notification",
        example=5,
    )


class BulkNotificationsWithGraphs(Checkbox):
    value = fields.Integer(
        description="Sets a limit for the number of notifications in a bulk for which graphs are displayed. If you do not use bulk notifications this option is ignored. Note that each graph increases the size of the mail and takes time to renderon the monitoring server. Therefore, large bulks may exceed the maximum size for attachements or the plugin may run into a timeout so that a failed notification is produced",
        example=5,
    )


class HTMLEmailParamsResponse(MailCommonParams):
    info_to_be_displayed_in_the_email_body = fields.Nested(CheckboxWithListOfEmailInfoStrs)
    insert_html_section_between_body_and_table = fields.Nested(
        HtmlSectionBetweenBodyAndTableCheckbox
    )
    url_prefix_for_links_to_checkmk = fields.Nested(URLPrefixForLinksToCheckMkCheckbox)
    enable_sync_smtp = fields.Nested(EnableSynchronousDeliveryViaSMTPValue)
    display_graphs_among_each_other = fields.Nested(Checkbox)
    graphs_per_notification = fields.Nested(GraphsPerNotification)
    bulk_notifications_with_graphs = fields.Nested(BulkNotificationsWithGraphs)


# Cisco -------------------------------------------------------------


class ExplicitOrStoreOptions(BaseSchema):
    option = fields.String(
        enum=["store", "explicit"],
        example="store",
    )


class WebhookURLResponse(ExplicitOrStoreOptions):
    store_id = PasswordStoreIDField()
    url = fields.URL(example="http://example_webhook_url.com")


DISABLE_SSL_CERT_VERIFICATION = fields.Nested(
    Checkbox,
    description="Ignore unverified HTTPS request warnings. Use with caution.",
)


URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE = fields.Nested(
    URLPrefixForLinksToCheckMkCheckbox,
)


class HttpProxy(BaseSchema):
    option = fields.String(
        enum=["no_proxy", "environment", "url"],
        example="",
    )
    url = fields.String(
        example="http://example_proxy",
    )


class HttpProxyValue(Checkbox):
    value = fields.Nested(
        HttpProxy,
        description="Use the proxy settings from the environment variables. The variables NO_PROXY, HTTP_PROXY and HTTPS_PROXY are taken into account during execution. Have a look at the python requests module documentation for further information. Note that these variables must be defined as a site-user in ~/etc/environment and that this might affect other notification methods which also use the requests module",
    )


HTTP_PROXY_RESPONSE = fields.Nested(
    HttpProxyValue,
    example={},
    description="",
)


class CiscoWebexPluginResponse(PluginName):
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    webhook_url = fields.Nested(WebhookURLResponse)
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    http_proxy = HTTP_PROXY_RESPONSE


# Ilert -------------------------------------------------------------


PASSWORD_STORE_ID_SHOULD_EXIST = PasswordStoreIDField()


class IlertKeyResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    key = fields.String(example="example_key")


class IlertPluginResponse(PluginName):
    notification_priority = fields.String(
        enum=list(get_args(IlertPriorityType)),
        description="HIGH - with escalation, LOW - without escalation",
        example="HIGH",
    )
    custom_summary_for_host_alerts = fields.String(
        example="$NOTIFICATIONTYPE$ Host Alert: $HOSTNAME$ is $HOSTSTATE$ - $HOSTOUTPUT$",
        description="A custom summary for host alerts",
    )
    custom_summary_for_service_alerts = fields.String(
        example="$NOTIFICATIONTYPE$ Service Alert: $HOSTALIAS$/$SERVICEDESC$ is $SERVICESTATE$ - $SERVICEOUTPUT$",
        description="A custom summary for service alerts",
    )
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    api_key = fields.Nested(IlertKeyResponse)
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    http_proxy = HTTP_PROXY_RESPONSE


# Jira --------------------------------------------------------------


class JiraPluginResponse(PluginName):
    jira_url = fields.String(
        example="http://jira_url_example.com",
        description="Configure the JIRA URL here",
    )
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    username = fields.String(
        example="username_a",
        description="Configure the user name here",
    )
    password = fields.String(
        example="example_pass_123&*",
        description="The password entered here is stored in plain text within the monitoring site. This usually needed because the monitoring process needs to have access to the unencrypted password because it needs to submit it to authenticate with remote systems",
    )
    project_id = fields.String(
        example="",
        description="The numerical JIRA project ID. If not set, it will be retrieved from a custom user attribute named jiraproject. If that is not set, the notification will fail",
    )
    issue_type_id = fields.String(
        example="",
        description="The numerical JIRA issue type ID. If not set, it will be retrieved from a custom user attribute named jiraissuetype. If that is not set, the notification will fail",
    )
    host_custom_id = fields.String(
        example="",
        description="The numerical JIRA custom field ID for host problems",
    )
    service_custom_id = fields.String(
        example="",
        description="The numerical JIRA custom field ID for service problems",
    )
    monitoring_url = fields.String(
        example="",
        description="Configure the base URL for the Monitoring Web-GUI here. Include the site name. Used for link to check_mk out of jira",
    )
    site_custom_id = fields.Nested(CheckboxWithStrValue)
    priority_id = fields.Nested(CheckboxWithStrValue)
    host_summary = fields.Nested(CheckboxWithStrValue)
    service_summary = fields.Nested(CheckboxWithStrValue)
    label = fields.Nested(CheckboxWithStrValue)
    resolution_id = fields.Nested(CheckboxWithStrValue)
    optional_timeout = fields.Nested(CheckboxWithStrValue)


# MkEvent -----------------------------------------------------------


class CheckboxSysLogFacilityToUseValue(Checkbox):
    value = fields.String(
        enum=list(get_args(SysLogFacilityStrType)),
        description="",
        example="",
    )


class CheckBoxIPAddressValue(Checkbox):
    value = IPField(ip_type_allowed="ipv4")


class MkEventParamsResponse(PluginName):
    syslog_facility_to_use = fields.Nested(CheckboxSysLogFacilityToUseValue)
    ip_address_of_remote_event_console = fields.Nested(CheckBoxIPAddressValue)


# MSTeams -----------------------------------------------------------


class MSTeamsPluginResponse(PluginName):
    affected_host_groups = fields.Nested(Checkbox)
    host_details = fields.Nested(CheckboxWithStrValue)
    service_details = fields.Nested(CheckboxWithStrValue)
    host_summary = fields.Nested(CheckboxWithStrValue)
    service_summary = fields.Nested(CheckboxWithStrValue)
    host_title = fields.Nested(CheckboxWithStrValue)
    service_title = fields.Nested(CheckboxWithStrValue)
    http_proxy = HTTP_PROXY_RESPONSE
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    webhook_url = fields.Nested(WebhookURLResponse)


# OpenGenie ---------------------------------------------------------


class OpsGeniePasswordResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    key = fields.String(example="example key")


class CheckboxOpsGeniePriorityValue(Checkbox):
    value = fields.String(
        enum=list(get_args(OpsGeniePriorityStrType)),
        description="",
        example="moderate",
    )


class OpenGeniePluginResponse(PluginName):
    api_key = fields.Nested(OpsGeniePasswordResponse)
    domain = fields.Nested(CheckboxWithStrValue)
    http_proxy = fields.Nested(HttpProxyValue)
    owner = fields.Nested(CheckboxWithStrValue)
    source = fields.Nested(CheckboxWithStrValue)
    priority = fields.Nested(CheckboxOpsGeniePriorityValue)
    note_while_creating = fields.Nested(CheckboxWithStrValue)
    note_while_closing = fields.Nested(CheckboxWithStrValue)
    desc_for_host_alerts = fields.Nested(CheckboxWithStrValue)
    desc_for_service_alerts = fields.Nested(CheckboxWithStrValue)
    message_for_host_alerts = fields.Nested(CheckboxWithStrValue)
    message_for_service_alerts = fields.Nested(CheckboxWithStrValue)
    responsible_teams = fields.Nested(CheckboxWithListOfStr)
    actions = fields.Nested(CheckboxWithListOfStr)
    tags = fields.Nested(CheckboxWithListOfStr)
    entity = fields.Nested(CheckboxWithStrValue)


# PagerDuty ---------------------------------------------------------


class PagerDutyIntegrationKeyResponse(ExplicitOrStoreOptions):
    key = fields.String(example="some_key_example")
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST


class PagerDutyPluginResponse(PluginName):
    integration_key = fields.Nested(PagerDutyIntegrationKeyResponse)
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    http_proxy = HTTP_PROXY_RESPONSE


# PushOver ----------------------------------------------------------


class PushOverPriority(Checkbox):
    value = fields.String(
        enum=list(get_args(PushOverPriorityStringType)),
        description="The pushover priority level",
        example="normal",
    )


class Sounds(Checkbox):
    value = fields.String(
        enum=list(get_args(SoundType)),
        description="See https://pushover.net/api#sounds for more information and trying out available sounds.",
        example="none",
    )


class PushOverPluginResponse(PluginName):
    api_key = fields.String(
        example="azGDORePK8gMaC0QOYAMyEEuzJnyUi",
        description="You need to provide a valid API key to be able to send push notifications using Pushover. Register and login to Pushover, thn create your Check_MK installation as application and obtain your API key",
        pattern="^[a-zA-Z0-9]{30,40}$",
    )
    user_group_key = fields.String(
        example="azGDORePK8gMaC0QOYAMyEEuzJnyUi",
        description="Configure the user or group to receive the notifications by providing the user or group key here. The key can be obtained from the Pushover website.",
        pattern="^[a-zA-Z0-9]{30,40}$",
    )
    url_prefix_for_links_to_checkmk = fields.Nested(CheckboxWithStrValue)
    priority = fields.Nested(PushOverPriority)
    sound = fields.Nested(Sounds)
    http_proxy = HTTP_PROXY_RESPONSE


# ServiceNow --------------------------------------------------------


class ServiceNowPasswordResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    password = fields.String(example="http://example_webhook_url.com")


class CheckBoxUseSiteIDPrefix(Checkbox):
    value = fields.String(
        enum=["use_site_id_prefix", "deactivated"],
        description="",
        example="use_site_id",
    )


class ManagementTypeStates(BaseSchema):
    start_predefined = fields.String(
        example="hold",
    )
    start_integer = fields.Integer(
        example=1,
    )
    end_predefined = fields.String(
        example="resolved",
    )
    end_integer = fields.Integer(
        example=0,
    )


class CheckboxWithManagementTypeStateValue(Checkbox):
    value = fields.Nested(ManagementTypeStates)


class ManagementTypeParams(BaseSchema):
    host_description = fields.Nested(CheckboxWithStrValue)
    service_description = fields.Nested(CheckboxWithStrValue)
    host_short_description = fields.Nested(CheckboxWithStrValue)
    service_short_description = fields.Nested(CheckboxWithStrValue)
    caller = fields.String()
    urgency = fields.Nested(CheckboxWithStrValue)
    impact = fields.Nested(CheckboxWithStrValue)
    state_recovery = fields.Nested(CheckboxWithManagementTypeStateValue)
    state_acknowledgement = fields.Nested(CheckboxWithManagementTypeStateValue)
    state_downtime = fields.Nested(CheckboxWithManagementTypeStateValue)
    priority = fields.Nested(CheckboxWithStrValue)


class ServiceNowMngmtType(BaseSchema):
    option = fields.String(
        enum=["case", "incident"],
        description="The management type",
        example="case",
    )
    params = fields.Nested(
        ManagementTypeParams,
    )


class ServiceNowPluginResponse(PluginName):
    servicenow_url = fields.String(
        example="https://myservicenow.com",
        description="Configure your ServiceNow URL here",
    )
    username = fields.String(
        example="username_a",
        description="Configure the user name here",
    )

    user_password = fields.Nested(
        ServiceNowPasswordResponse,
        description="The password for ServiceNow Plugin.",
        example={"option": "password", "password": "my_unique_password"},
    )
    http_proxy = HTTP_PROXY_RESPONSE
    use_site_id_prefix = fields.Nested(CheckBoxUseSiteIDPrefix)
    optional_timeout = fields.Nested(CheckboxWithStrValue)
    management_type = fields.Nested(ServiceNowMngmtType)


# Signl4 ------------------------------------------------------------


class SignL4TeamSecretResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    secret = fields.String(example="http://example_webhook_url.com")


class Signl4PluginResponse(PluginName):
    team_secret = fields.Nested(
        SignL4TeamSecretResponse,
        description="The password for SignL4 Plugin.",
        example={"option": "password", "password": "my_unique_password"},
    )
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    http_proxy = HTTP_PROXY_RESPONSE


# Slack -------------------------------------------------------------


class SlackWebhookURLResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    url = fields.String(example="http://example_webhook_url.com")


class SlackPluginResponse(PluginName):
    webhook_url = fields.Nested(SlackWebhookURLResponse)
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    http_proxy = HTTP_PROXY_RESPONSE


# SMS API -----------------------------------------------------------


class SMSAPIPAsswordResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    password = fields.String(example="http://example_webhook_url.com")


class SMSAPIPluginResponse(PluginName):
    modem_type = fields.String(
        enum=["trb140"],
        example="trb140",
        description="Choose what modem is used. Currently supported is only Teltonika-TRB140.",
    )
    modem_url = fields.URL(
        example="https://mymodem.mydomain.example",
        description="Configure your modem URL here",
    )
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    username = fields.String(
        example="username_a",
        description="Configure the user name here",
    )
    timeout = fields.String(
        example="10",
        description="Here you can configure timeout settings",
    )
    user_password = fields.Nested(SMSAPIPAsswordResponse)
    http_proxy = HTTP_PROXY_RESPONSE


# SMS ---------------------------------------------------------------


class SMSPluginResponse(PluginName):
    params = fields.List(
        fields.String,
        uniqueItems=True,
        description="The given parameters are available in scripts as NOTIFY_PARAMETER_1, NOTIFY_PARAMETER_2, etc. You may paste a text from your clipboard which contains several parts separated by ';' characters into the last input field. The text will then be split by these separators and the single parts are added into dedicated input fields.",
        example=["NOTIFY_PARAMETER_1", "NOTIFY_PARAMETER_1"],
    )


# Spectrum ----------------------------------------------------------


class SpectrumPluginResponse(PluginName):
    destination_ip = IPField(
        ip_type_allowed="ipv4",
        description="IP Address of the Spectrum server receiving the SNMP trap",
    )
    snmp_community = fields.String(
        example="",
        description="SNMP Community for the SNMP trap. The password entered here is stored in plain text within the monitoring site. This usually needed because the monitoring process needs to have access to the unencrypted password because it needs to submit it to authenticate with remote systems",
    )
    base_oid = fields.String(
        example="1.3.6.1.4.1.1234",
        description="The base OID for the trap content",
    )


# Victorops ---------------------------------------------------------


class SplunkRESTEndpointResponse(ExplicitOrStoreOptions):
    store_id = PASSWORD_STORE_ID_SHOULD_EXIST
    url = fields.String(
        example="https://alert.victorops.com/integrations/example",
    )


class VictoropsPluginResponse(PluginName):
    splunk_on_call_rest_endpoint = fields.Nested(SplunkRESTEndpointResponse)
    url_prefix_for_links_to_checkmk = URL_PREFIX_FOR_LINKS_TO_CHECKMK_RESPONSE
    disable_ssl_cert_verification = DISABLE_SSL_CERT_VERIFICATION
    http_proxy = HTTP_PROXY_RESPONSE


#  --------------------------------------------------------------


class RulePropertiesAttributes(BaseSchema):
    description = fields.String(
        description="A description or title of this rule.",
        example="Notify all contacts of a host/service via HTML email",
    )
    comment = fields.String(
        description="An optional comment that may be used to explain the purpose of this object.",
        example="An example comment",
    )
    documentation_url = fields.String(
        description="An optional URL pointing to documentation or any other page. This will be displayed as an icon and open a new page when clicked.",
        example="http://link/to/documentation",
    )
    do_not_apply_this_rule = fields.Nested(
        Checkbox,
        description="Disabled rules are kept in the configuration but are not applied.",
        example={"state": "enabled"},
    )
    allow_users_to_deactivate = fields.Nested(
        Checkbox,
        description="If you set this option then users are allowed to deactivate notifications that are created by this rule.",
        example={"state": "enabled"},
    )


class PluginBase(BaseSchema):
    option = fields.String(
        enum=[
            PluginOptions.CANCEL.value,
            PluginOptions.WITH_PARAMS.value,
            PluginOptions.WITH_CUSTOM_PARAMS.value,
        ],
        example=PluginOptions.CANCEL.value,
    )

    plugin_params = fields.Dict(
        description="The plugin name and configuration parameters defined.",
    )

    def dump(self, obj: dict[str, Any], *args: Any, **kwargs: Any) -> Mapping:
        if obj["plugin_params"]["plugin_name"] not in list(get_args(BuiltInPluginNames)):
            return obj

        schema_mapper: Mapping[BuiltInPluginNames, type[BaseSchema]] = {
            "mail": HTMLEmailParamsResponse,
            "cisco_webex_teams": CiscoWebexPluginResponse,
            "mkeventd": MkEventParamsResponse,
            "asciimail": AsciiEmailParamsResponse,
            "ilert": IlertPluginResponse,
            "jira_issues": JiraPluginResponse,
            "opsgenie_issues": OpenGeniePluginResponse,
            "pagerduty": PagerDutyPluginResponse,
            "pushover": PushOverPluginResponse,
            "servicenow": ServiceNowPluginResponse,
            "signl4": Signl4PluginResponse,
            "slack": SlackPluginResponse,
            "sms_api": SMSAPIPluginResponse,
            "sms": SMSPluginResponse,
            "spectrum": SpectrumPluginResponse,
            "victorops": VictoropsPluginResponse,
            "msteams": MSTeamsPluginResponse,
        }

        plugin_params: PluginType = obj["plugin_params"]
        plugin_name = cast(BuiltInPluginNames, plugin_params["plugin_name"])
        schema_to_use = schema_mapper[plugin_name]
        obj.update({"plugin_params": schema_to_use().dump(plugin_params)})
        return obj


class NotificationBulkingCommonAttributes(Checkbox):
    time_horizon = fields.Integer(
        description="Notifications are kept back for bulking at most for this time (seconds)",
        example=60,
    )
    max_bulk_size = fields.Integer(
        description="At most that many Notifications are kept back for bulking. A value of 1 essentially turns off notification bulking.",
        example="1000",
    )
    notification_bulks_based_on = fields.List(
        fields.String(enum=list(get_args(GroupbyType))),
        uniqueItems=True,
    )
    notification_bulks_based_on_custom_macros = fields.List(
        fields.String,
        description="If you enter the names of host/service-custom macros here then for each different combination of values of those macros a separate bulk will be created. Service macros match first, if no service macro is found, the host macros are searched. This can be used in combination with the grouping by folder, host etc. Omit any leading underscore. Note: If you are using Nagios as a core you need to make sure that the values of the required macros are present in the notification context. This is done in check_mk_templates.cfg. If you macro is _FOO then you need to add the variables NOTIFY_HOST_FOO and NOTIFY_SERVICE_FOO. You may paste a text from your clipboard which contains several parts separated by ';' characters into the last input field. The text will then be split by these separators and the single parts are added into dedicated input fields",
        example="",
    )
    subject_for_bulk_notifications = fields.Nested(
        CheckboxWithStrValue,
    )


class BulkOutsideTimePeriodValue(Checkbox):
    value = fields.Nested(
        NotificationBulkingCommonAttributes,
    )


class NotificationBulking(NotificationBulkingCommonAttributes):
    time_period = fields.String(
        description="",
        example="24X7",
    )
    bulk_outside_timeperiod = fields.Nested(
        BulkOutsideTimePeriodValue,
    )


class WhenToBulk(BaseSchema):
    when_to_bulk = fields.String(
        enum=["always", "timeperiod"],
        description="Bulking can always happen or during a set time period",
        example="always",
    )
    params = fields.Nested(
        NotificationBulking,
    )


class NotificationBulkingCheckbox(Checkbox):
    value = fields.Nested(WhenToBulk)


class NotificationPlugin(BaseSchema):
    notify_plugin = fields.Nested(PluginBase)
    notification_bulking = fields.Nested(NotificationBulkingCheckbox)


class ContactSelectionAttributes(BaseSchema):
    all_contacts_of_the_notified_object = fields.Nested(Checkbox)
    all_users = fields.Nested(Checkbox)
    all_users_with_an_email_address = fields.Nested(Checkbox)
    the_following_users = fields.Nested(CheckboxWithListOfStr)
    members_of_contact_groups = fields.Nested(CheckboxWithListOfStr)
    explicit_email_addresses = fields.Nested(CheckboxWithListOfStr)
    restrict_by_custom_macros = fields.Nested(MatchCustomMacros)
    restrict_by_contact_groups = fields.Nested(CheckboxWithListOfStr)


class ConditionsAttributes(BaseSchema):
    match_sites = fields.Nested(CheckboxWithListOfStr)
    match_folder = fields.Nested(CheckboxWithFolderStr)
    match_host_tags = fields.Nested(CheckboxMatchHostTags)
    match_host_labels = fields.Nested(CheckboxWithListOfLabels)
    match_host_groups = fields.Nested(CheckboxWithListOfStr)
    match_hosts = fields.Nested(CheckboxWithListOfStr)
    match_exclude_hosts = fields.Nested(CheckboxWithListOfStr)
    match_service_labels = fields.Nested(CheckboxWithListOfLabels)
    match_service_groups = fields.Nested(CheckboxWithListOfStr)
    match_exclude_service_groups = fields.Nested(CheckboxWithListOfStr)
    match_service_groups_regex = fields.Nested(CheckboxWithListOfServiceGroupsRegex)
    match_exclude_service_groups_regex = fields.Nested(CheckboxWithListOfServiceGroupsRegex)
    match_services = fields.Nested(CheckboxWithListOfStr)
    match_exclude_services = fields.Nested(CheckboxWithListOfStr)
    match_check_types = fields.Nested(CheckboxWithListOfStr)
    match_plugin_output = fields.Nested(CheckboxWithStrValue)
    match_contact_groups = fields.Nested(CheckboxWithListOfStr)
    match_service_levels = fields.Nested(CheckboxWithFromToServiceLevels)
    match_only_during_time_period = fields.Nested(CheckboxWithStrValue)
    match_host_event_type = fields.Nested(CheckboxHostEventType)
    match_service_event_type = fields.Nested(CheckboxServiceEventType)
    restrict_to_notification_numbers = fields.Nested(CheckboxRestrictNotificationNumbers)
    throttle_periodic_notifications = fields.Nested(CheckboxThrottlePeriodicNotifcations)
    match_notification_comment = fields.Nested(CheckboxWithStrValue)
    event_console_alerts = fields.Nested(MatchEventConsoleAlertsResponse)


class NotificationRuleAttributes(BaseSchema):
    rule_properties = fields.Nested(RulePropertiesAttributes)
    notification_method = fields.Nested(NotificationPlugin)
    contact_selection = fields.Nested(ContactSelectionAttributes)
    conditions = fields.Nested(ConditionsAttributes)


class NotificationRuleConfig(BaseSchema):
    rule_config = fields.Nested(NotificationRuleAttributes)


class NotificationRuleResponse(DomainObject):
    domainType = fields.Constant(
        "rule_notifications",
        description="The domain type of the object.",
    )
    extensions = fields.Nested(
        NotificationRuleConfig,
        description="The configuration attributes of a notification rule.",
        example={"rule_config": notification_rule_request_example()},
    )


class NotificationRuleResponseCollection(DomainObjectCollection):
    domainType = fields.Constant(
        "rule_notifications",
        description="The domain type of the objects in the collection.",
    )
    value = fields.List(
        fields.Nested(NotificationRuleResponse),
        description="A list of notification rule objects.",
        example=[
            {
                "links": [],
                "domainType": "rule_notifications",
                "id": "1",
                "title": "Rule Description",
                "members": {},
                "extensions": {"rule_config": notification_rule_request_example()},
            }
        ],
    )
