/**
 * Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
 * This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
 * conditions defined in the file COPYING, which is part of this source code package.
 */

import "core-js/stable";
import "cmk_figures_plugins";

import * as activation from "activation";
import * as ajax from "ajax";
import * as async_progress from "async_progress";
import * as availability from "availability";
import * as background_job from "background_job";
import * as backup from "backup";
import * as bi from "bi";
import * as cmk_figures from "cmk_figures";
import {figure_registry} from "cmk_figures";
import {EventStats, HostStats, ServiceStats} from "cmk_stats";
import {TableFigure} from "cmk_table";
import crossfilter from "crossfilter2";
import * as d3 from "d3";
import * as d3Sankey from "d3-sankey";
import * as dashboard from "dashboard";
import * as dc from "dc";
import * as element_dragging from "element_dragging";
import * as foldable_container from "foldable_container";
import * as forms from "forms";
import * as graph_integration from "graph_integration";
import * as graphs from "graphs";
import * as help from "help";
import * as host_diagnose from "host_diagnose";
import * as hover from "hover";
import $ from "jquery";
import * as keyboard_shortcuts from "keyboard_shortcuts";
import * as number_format from "number_format";
import * as page_menu from "page_menu";
import * as password_meter from "password_meter";
import * as popup_menu from "popup_menu";
import * as prediction from "prediction";
import * as profile_replication from "profile_replication";
import {render_qr_codes} from "qrcode_rendering";
import * as quicksearch from "quicksearch";
import * as reload_pause from "reload_pause";
import * as selection from "selection";
import * as service_discovery from "service_discovery";
import * as sidebar from "sidebar";
import * as sites from "sites";
import * as sla from "sla";
import {render_stats_table} from "tracking_display";
import * as transfer from "transfer";
import {RequireConfirmation} from "types";
import * as utils from "utils";
import * as valuespecs from "valuespecs";
import * as views from "views";
import * as visibility_detection from "visibility_detection";
import * as wato from "wato";
import * as webauthn from "webauthn";

import * as nodevis from "./modules/nodevis/main";

// Optional import is currently not possible using the ES6 imports
let graphs_cee;
let ntop_host_details;
let ntop_alerts;
let ntop_flows;
let ntop_top_talkers;
let ntop_utils;
let license_usage_timeseries_graph;
let register;

function registerRawFigureBaseClasses() {
    figure_registry.register(TableFigure);
    figure_registry.register(HostStats);
    figure_registry.register(ServiceStats);
    figure_registry.register(EventStats);
}

registerRawFigureBaseClasses();
if (process.env.ENTERPRISE !== "no") {
    register = require("register");
    register.registerEnterpriseFigureBaseClasses();
    require("cmk_figures_plugins_cee");
    graphs_cee = require("graphs_cee");
    ntop_host_details = require("ntop_host_details");
    ntop_alerts = require("ntop_alerts");
    ntop_flows = require("ntop_flows");
    ntop_top_talkers = require("ntop_top_talkers");
    ntop_utils = require("ntop_utils");
    license_usage_timeseries_graph = require("license_usage_timeseries_graph");
} else {
    graphs_cee = null;
    ntop_host_details = null;
    ntop_alerts = null;
    ntop_flows = null;
    ntop_top_talkers = null;
    ntop_utils = null;
    license_usage_timeseries_graph = null;
}

type CallableFunctionOptions = {[key: string]: string};
type CallableFunction = (
    node: HTMLElement,
    options: CallableFunctionOptions
) => Promise<void>;

// See cmk.gui.htmllib.generator:KnownTSFunction
// The type on the Python side and the available keys in this dictionary MUST MATCH.
const callable_functions: {[name: string]: CallableFunction} = {
    render_stats_table: render_stats_table,
    //   "render_qr_codes": render_qr_codes,
};

$(() => {
    utils.update_header_timer();
    forms.enable_dynamic_form_elements();
    // TODO: only register when needed?
    element_dragging.register_event_handlers();
    keyboard_shortcuts.register_shortcuts();
    // add a confirmation popup for each for that has a valid confirmation text

    // See cmk.gui.htmllib.generator:HTMLWriter.call_ts_function
    document
        .querySelectorAll<HTMLElement>("*[data-cmk_call_ts_function]")
        .forEach((container, _) => {
            const data = container.dataset;
            const function_name: string = data.cmk_call_ts_function!;
            let options: CallableFunctionOptions;
            if (data.cmk_call_ts_options) {
                options = JSON.parse(data.cmk_call_ts_options);
            } else {
                options = {};
            }
            const ts_function = callable_functions[function_name];
            // The function has the responsibility to take the container and do it's thing with it.
            ts_function(container, options);
        });

    document
        .querySelectorAll<HTMLFormElement>("form[data-cmk_form_confirmation]")
        .forEach((form, _) => {
            const confirmation: RequireConfirmation = JSON.parse(
                form.dataset.cmk_form_confirmation!
            );
            forms.add_confirm_on_submit(form, confirmation);
        });
    render_qr_codes();
});

export const cmk_export = {
    crossfilter: crossfilter,
    d3: d3,
    dc: dc,
    d3Sankey: d3Sankey,
    cmk: {
        activation: activation,
        ajax: ajax,
        async_progress: async_progress,
        availability: availability,
        background_job: background_job,
        backup: backup,
        bi: bi,
        dashboard: dashboard,
        element_dragging: element_dragging,
        figures: cmk_figures,
        foldable_container: foldable_container,
        forms: forms,
        graph_integration: graph_integration,
        graphs: graphs,
        graphs_cee: graphs_cee,
        help: help,
        host_diagnose: host_diagnose,
        hover: hover,
        keyboard_shortcuts: keyboard_shortcuts,
        license_usage: {
            timeseries_graph: license_usage_timeseries_graph,
        },
        nodevis: nodevis,
        ntop: {
            host_details: ntop_host_details,
            alerts: ntop_alerts,
            flows: ntop_flows,
            top_talkers: ntop_top_talkers,
            utils: ntop_utils,
        },
        number_format: number_format,
        page_menu: page_menu,
        popup_menu: popup_menu,
        prediction: prediction,
        profile_replication: profile_replication,
        quicksearch: quicksearch,
        reload_pause: reload_pause,
        render_stats_table: render_stats_table,
        selection: selection,
        service_discovery: service_discovery,
        sidebar: sidebar /* needed for add snapin page */,
        sites: sites,
        sla: sla,
        transfer: transfer,
        utils: utils,
        valuespecs: valuespecs,
        views: views,
        visibility_detection: visibility_detection,
        wato: wato,
        webauthn: webauthn,
    },
};

password_meter.initPasswordStrength();
