// Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the
// terms and conditions defined in the file COPYING, which is part of this
// source code package.

#include "livestatus/TableStateHistory.h"

#include <bitset>
#include <chrono>
#include <compare>
#include <stdexcept>
#include <utility>
#include <vector>

#include "livestatus/ChronoUtils.h"
#include "livestatus/Column.h"
#include "livestatus/DoubleColumn.h"
#include "livestatus/Filter.h"
#include "livestatus/ICore.h"
#include "livestatus/IntColumn.h"
#include "livestatus/Interface.h"
#include "livestatus/LogCache.h"
#include "livestatus/LogEntry.h"
#include "livestatus/Logger.h"
#include "livestatus/Query.h"
#include "livestatus/Row.h"
#include "livestatus/StringColumn.h"
#include "livestatus/StringUtils.h"
#include "livestatus/TableHosts.h"
#include "livestatus/TableServices.h"
#include "livestatus/TimeColumn.h"
#include "livestatus/User.h"

using row_type = HostServiceState;

using namespace std::chrono_literals;

TableStateHistory::TableStateHistory(ICore *mc, LogCache *log_cache)
    : log_cache_{log_cache}, abort_query_{false} {
    addColumns(this, *mc, "", ColumnOffsets{});
}

// static
void TableStateHistory::addColumns(Table *table, const ICore &core,
                                   const std::string &prefix,
                                   const ColumnOffsets &offsets) {
    table->addColumn(std::make_unique<TimeColumn<row_type>>(
        prefix + "time", "Time of the log event (seconds since 1/1/1970)",
        offsets, [](const row_type &row) { return row._time; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "lineno", "The number of the line in the log file", offsets,
        [](const row_type &row) { return row._lineno; }));
    table->addColumn(std::make_unique<TimeColumn<row_type>>(
        prefix + "from", "Start time of state (seconds since 1/1/1970)",
        offsets, [](const row_type &row) { return row._from; }));
    table->addColumn(std::make_unique<TimeColumn<row_type>>(
        prefix + "until", "End time of state (seconds since 1/1/1970)", offsets,
        [](const row_type &row) { return row._until; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "duration", "Duration of state (until - from)", offsets,
        [](const row_type &row) {
            return mk::ticks<std::chrono::seconds>(row._duration);
        }));
    table->addColumn(std::make_unique<DoubleColumn<row_type>>(
        prefix + "duration_part",
        "Duration part in regard to the query timeframe", offsets,
        [](const row_type &row) { return row._duration_part; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "state",
        "The state of the host or service in question - OK(0) / WARNING(1) / CRITICAL(2) / UNKNOWN(3) / UNMONITORED(-1)",
        offsets, [](const row_type &row) { return row._state; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "host_down", "Shows if the host of this service is down",
        offsets, [](const row_type &row) { return row._host_down; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "in_downtime", "Shows if the host or service is in downtime",
        offsets, [](const row_type &row) { return row._in_downtime; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "in_host_downtime",
        "Shows if the host of this service is in downtime", offsets,
        [](const row_type &row) { return row._in_host_downtime; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "is_flapping", "Shows if the host or service is flapping",
        offsets, [](const row_type &row) { return row._is_flapping; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "in_notification_period",
        "Shows if the host or service is within its notification period",
        offsets,
        [](const row_type &row) { return row._in_notification_period; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "notification_period",
        "The notification period of the host or service in question", offsets,
        [](const row_type &row) { return row._notification_period; }));
    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "in_service_period",
        "Shows if the host or service is within its service period", offsets,
        [](const row_type &row) { return row._in_service_period; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "service_period",
        "The service period of the host or service in question", offsets,
        [](const row_type &row) { return row._service_period; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "debug_info", "Debug information", offsets,
        [](const row_type &row) { return row._debug_info; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "host_name", "Host name", offsets,
        [](const row_type &row) { return row._host_name; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "service_description", "Description of the service", offsets,
        [](const row_type &row) { return row._service_description; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "log_output", "Logfile output relevant for this state",
        offsets, [](const row_type &row) { return row._log_output; }));
    table->addColumn(std::make_unique<StringColumn<row_type>>(
        prefix + "long_log_output",
        "Complete logfile output relevant for this state", offsets,
        [](const row_type &row) { return row._long_log_output; }));

    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "duration_ok", "OK duration of state ( until - from )",
        offsets, [](const row_type &row) {
            return mk::ticks<std::chrono::seconds>(row._duration_ok);
        }));
    table->addColumn(std::make_unique<DoubleColumn<row_type>>(
        prefix + "duration_part_ok",
        "OK duration part in regard to the query timeframe", offsets,
        [](const row_type &row) { return row._duration_part_ok; }));

    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "duration_warning", "WARNING duration of state (until - from)",
        offsets, [](const row_type &row) {
            return mk::ticks<std::chrono::seconds>(row._duration_warning);
        }));
    table->addColumn(std::make_unique<DoubleColumn<row_type>>(
        prefix + "duration_part_warning",
        "WARNING duration part in regard to the query timeframe", offsets,
        [](const row_type &row) { return row._duration_part_warning; }));

    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "duration_critical",
        "CRITICAL duration of state (until - from)", offsets,
        [](const row_type &row) {
            return mk::ticks<std::chrono::seconds>(row._duration_critical);
        }));
    table->addColumn(std::make_unique<DoubleColumn<row_type>>(
        prefix + "duration_part_critical",
        "CRITICAL duration part in regard to the query timeframe", offsets,
        [](const row_type &row) { return row._duration_part_critical; }));

    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "duration_unknown", "UNKNOWN duration of state (until - from)",
        offsets, [](const row_type &row) {
            return mk::ticks<std::chrono::seconds>(row._duration_unknown);
        }));
    table->addColumn(std::make_unique<DoubleColumn<row_type>>(
        prefix + "duration_part_unknown",
        "UNKNOWN duration part in regard to the query timeframe", offsets,
        [](const row_type &row) { return row._duration_part_unknown; }));

    table->addColumn(std::make_unique<IntColumn<row_type>>(
        prefix + "duration_unmonitored",
        "UNMONITORED duration of state (until - from)", offsets,
        [](const row_type &row) {
            return mk::ticks<std::chrono::seconds>(row._duration_unmonitored);
        }));
    table->addColumn(std::make_unique<DoubleColumn<row_type>>(
        prefix + "duration_part_unmonitored",
        "UNMONITORED duration part in regard to the query timeframe", offsets,
        [](const row_type &row) { return row._duration_part_unmonitored; }));

    // join host and service tables
    TableHosts::addColumns(
        table, core, prefix + "current_host_",
        offsets.add([](Row r) { return r.rawData<row_type>()->_host; }),
        LockComments::yes, LockDowntimes::yes);
    TableServices::addColumns(
        table, core, prefix + "current_service_",
        offsets.add([](Row r) { return r.rawData<row_type>()->_service; }),
        TableServices::AddHosts::no, LockComments::yes, LockDowntimes::yes);
}

std::string TableStateHistory::name() const { return "statehist"; }

std::string TableStateHistory::namePrefix() const { return "statehist_"; }

const Logfile::map_type *LogEntryForwardIterator::getEntries() {
    return it_logs_->second->getEntriesFor({
        .max_lines_per_log_file = max_lines_per_log_file_,
        .log_entry_classes =
            LogEntryClasses{}
                .set(static_cast<int>(LogEntry::Class::alert))
                .set(static_cast<int>(LogEntry::Class::program))
                .set(static_cast<int>(LogEntry::Class::state)),
    });
}

LogEntry *LogEntryForwardIterator::getNextLogentry() {
    if (it_entries_ != entries_->end()) {
        ++it_entries_;
    }

    while (it_entries_ == entries_->end()) {
        auto it_logs_cpy = it_logs_;
        if (++it_logs_cpy == log_files_->end()) {
            return nullptr;
        }
        ++it_logs_;
        entries_ = getEntries();
        it_entries_ = entries_->begin();
    }
    return it_entries_->second.get();
}

namespace {
class TimeperiodTransition {
public:
    explicit TimeperiodTransition(const std::string &str) {
        auto fields = mk::split(str, ';');
        if (fields.size() != 3) {
            throw std::invalid_argument("expected 3 arguments");
        }
        name_ = fields[0];
        from_ = std::stoi(fields[1]);
        to_ = std::stoi(fields[2]);
    }

    [[nodiscard]] std::string name() const { return name_; }
    [[nodiscard]] int from() const { return from_; }
    [[nodiscard]] int to() const { return to_; }

private:
    std::string name_;
    int from_;
    int to_;
};
}  // namespace

// static
std::unique_ptr<Filter> TableStateHistory::createPartialFilter(
    const Query &query) {
    return query.partialFilter(
        "current host/service columns", [](const std::string &columnName) {
            // NOTE: This is quite brittle and must be kept in sync with its
            // usage in TableStateHistory::insert_new_state()!
            return (
                // joined via HostServiceState::_host
                columnName.starts_with("current_host_") ||
                // joined via HostServiceState::_service
                columnName.starts_with("current_service_") ||
                // HostServiceState::_host_name
                columnName == "host_name" ||
                // HostServiceState::_service_description
                columnName == "service_description");
        });
}

void TableStateHistory::answerQuery(Query &query, const User &user,
                                    const ICore &core) {
    log_cache_->apply(
        [this, &query, &user, &core](const LogFiles &log_files,
                                     size_t /*num_cached_log_messages*/) {
            LogEntryForwardIterator it{log_files, core.maxLinesPerLogFile()};
            answerQueryInternal(query, user, core, it);
        });
}

namespace {
// Set still unknown hosts / services to unmonitored
void set_unknown_to_unmonitored(
    bool in_nagios_initial_states,
    const TableStateHistory::state_info_t &state_info) {
    if (in_nagios_initial_states) {
        for (const auto &[key, hss] : state_info) {
            if (hss->_may_no_longer_exist) {
                hss->_has_vanished = true;
            }
        }
    }
}

void handle_log_initial_states(
    const LogEntry *entry, const TableStateHistory::state_info_t &state_info) {
    // This feature is only available if log_initial_states is set to 1. If
    // log_initial_states is set, each nagios startup logs the initial states of
    // all known hosts and services. Therefore we can detect if a host is no
    // longer available after a nagios startup. If it still exists an INITIAL
    // HOST/SERVICE state entry will follow up shortly.
    for (const auto &[key, hss] : state_info) {
        if (!hss->_has_vanished) {
            hss->_last_known_time = entry->time();
            hss->_may_no_longer_exist = true;
        }
    }
}
}  // namespace

bool LogEntryForwardIterator::rewind_to_start(const LogPeriod &period,
                                              Logger *logger) {
    if (log_files_->begin() == log_files_->end()) {
        Debug(logger) << "no log files found";
        return false;
    }

    // Switch to last logfile (we have at least one)
    --it_logs_;
    auto newest_log = it_logs_;

    // Now find the log where 'since' starts.
    while (it_logs_ != log_files_->begin() &&
           it_logs_->second->since() >= period.since) {
        --it_logs_;  // go back in history
    }

    if (it_logs_->second->since() >= period.until) {
        Debug(logger) << "all log files are newer than " << period;
        return false;
    }

    // Now it_logs points to the newest log file that starts strictly before the
    // query period. If there is no such log file, it points to the first one.
    // In other words, we are at the newest log file with the guarantee that
    // older log files do not contain entries withing the query period.
    Debug(logger) << "starting state history computation at "
                  << *it_logs_->second;

    // Determine initial log entry, setting entries_ and it_entries_
    entries_ = getEntries();
    if (entries_->empty()) {
        it_entries_ = entries_->begin();
        return true;
    }
    if (it_logs_ == newest_log) {
        it_entries_ = entries_->begin();
        return true;
    }
    it_entries_ = entries_->end();
    // If the last entry is younger than the start of the query period, then we
    // use this log file, too.
    if (--it_entries_ != entries_->begin() &&
        it_entries_->second->time() >= period.since) {
        it_entries_ = entries_->begin();
    }
    return true;
}

// NOLINTNEXTLINE(readability-function-cognitive-complexity)
void TableStateHistory::answerQueryInternal(Query &query, const User &user,
                                            const ICore &core,
                                            LogEntryForwardIterator &it) {
    auto object_filter = createPartialFilter(query);

    // This flag might be set to true by the return value of processDataset(...)
    abort_query_ = false;

    // Keep track of the historic state of services/hosts here
    state_info_t state_info;

    // Store hosts/services that we have filtered out here
    object_blacklist_t object_blacklist;

    auto *logger = core.loggerLivestatus();
    auto period = LogPeriod::make(query);
    if (period.empty()) {
        Debug(logger) << "empty query period " << period;
        return;
    }

    if (!it.rewind_to_start(period, logger)) {
        return;
    }

    // From now on use getNextLogentry()
    bool only_update = true;
    bool in_nagios_initial_states = false;

    // Notification periods information, name: active(1)/inactive(0)
    notification_periods_t notification_periods;

    while (LogEntry *entry = it.getNextLogentry()) {
        if (abort_query_ || entry->time() >= period.until) {
            break;
        }

        if (only_update && entry->time() >= period.since) {
            // Reached start of query timeframe. From now on let's produce real
            // output. Update _from time of every state entry
            for (const auto &[key, hss] : state_info) {
                hss->_from = period.since;
                hss->_until = period.since;
            }
            only_update = false;
        }

        switch (entry->kind()) {
            case LogEntryKind::none:
            case LogEntryKind::core_starting:
            case LogEntryKind::core_stopping:
            case LogEntryKind::log_version:
            case LogEntryKind::acknowledge_alert_host:
            case LogEntryKind::acknowledge_alert_service:
                set_unknown_to_unmonitored(in_nagios_initial_states,
                                           state_info);
                in_nagios_initial_states = false;
                break;
            case LogEntryKind::state_service_initial:
                handle_state_entry(query, user, core, entry, only_update,
                                   notification_periods, false, state_info,
                                   object_blacklist, *object_filter, period);
                break;
            case LogEntryKind::alert_service:
            case LogEntryKind::state_service:
            case LogEntryKind::downtime_alert_service:
            case LogEntryKind::flapping_service:
                set_unknown_to_unmonitored(in_nagios_initial_states,
                                           state_info);
                handle_state_entry(query, user, core, entry, only_update,
                                   notification_periods, false, state_info,
                                   object_blacklist, *object_filter, period);
                in_nagios_initial_states = false;
                break;
            case LogEntryKind::state_host_initial:
                handle_state_entry(query, user, core, entry, only_update,
                                   notification_periods, true, state_info,
                                   object_blacklist, *object_filter, period);
                break;
            case LogEntryKind::alert_host:
            case LogEntryKind::state_host:
            case LogEntryKind::downtime_alert_host:
            case LogEntryKind::flapping_host:
                set_unknown_to_unmonitored(in_nagios_initial_states,
                                           state_info);
                handle_state_entry(query, user, core, entry, only_update,
                                   notification_periods, true, state_info,
                                   object_blacklist, *object_filter, period);
                in_nagios_initial_states = false;
                break;
            case LogEntryKind::timeperiod_transition:
                set_unknown_to_unmonitored(in_nagios_initial_states,
                                           state_info);
                handle_timeperiod_transition(query, user, core, period, entry,
                                             only_update, notification_periods,
                                             state_info);
                in_nagios_initial_states = false;
                break;
            case LogEntryKind::log_initial_states:
                set_unknown_to_unmonitored(in_nagios_initial_states,
                                           state_info);
                handle_log_initial_states(entry, state_info);
                in_nagios_initial_states = true;
                break;
        }
    }

    if (!abort_query_) {
        final_reports(query, user, state_info, period);
    }
}

void TableStateHistory::handle_state_entry(
    Query &query, const User &user, const ICore &core, const LogEntry *entry,
    bool only_update, const notification_periods_t &notification_periods,
    bool is_host_entry, state_info_t &state_info,
    object_blacklist_t &object_blacklist, const Filter &object_filter,
    const LogPeriod &period) {
    const auto *entry_host = core.find_host(entry->host_name());
    const auto *entry_service =
        core.find_service(entry->host_name(), entry->service_description());

    HostServiceKey key =
        is_host_entry
            ? (entry_host == nullptr ? nullptr
                                     : entry_host->handleForStateHistory())
            : (entry_service == nullptr
                   ? nullptr
                   : entry_service->handleForStateHistory());
    if (key == nullptr) {
        return;
    }

    if (object_blacklist.contains(key)) {
        // Host/Service is not needed for this query and has already been
        // filtered out.
        return;
    }

    if (!state_info.contains(key)) {
        insert_new_state(query, user, entry, only_update, notification_periods,
                         state_info, object_blacklist, object_filter, period,
                         entry_host, entry_service, key);
    }
    update(query, user, core, period, entry, *state_info[key], only_update,
           notification_periods);
}

// static
// NOLINTNEXTLINE(readability-function-cognitive-complexity)
void TableStateHistory::insert_new_state(
    Query &query, const User &user, const LogEntry *entry, bool only_update,
    const notification_periods_t &notification_periods,
    state_info_t &state_info, object_blacklist_t &object_blacklist,
    const Filter &object_filter, const LogPeriod &period,
    const IHost *entry_host, const IService *entry_service,
    HostServiceKey key) {
    auto state = std::make_unique<HostServiceState>();
    state->_is_host = entry->service_description().empty();
    state->_host = entry_host;
    state->_service = entry_service;
    state->_host_name = entry->host_name();
    state->_service_description = entry->service_description();

    // No state found. Now check if this host/services is filtered out.
    // Note: we currently do not filter out hosts since they might be needed
    // for service states
    if (!entry->service_description().empty()) {
        // NOTE: The filter is only allowed to inspect those fields of state
        // which are set by now, see createPartialFilter()!
        if (!object_filter.accepts(Row{&state}, user, query.timezoneOffset())) {
            object_blacklist.insert(key);
            return;
        }
    }

    // Host/Service relations
    if (state->_is_host) {
        for (const auto &[key, hss] : state_info) {
            if (hss->_host != nullptr &&
                hss->_host->handleForStateHistory() ==
                    state->_host->handleForStateHistory()) {
                state->_services.push_back(hss.get());
            }
        }
    } else {
        auto it_inh = state_info.find(state->_host->handleForStateHistory());
        if (it_inh != state_info.end()) {
            it_inh->second->_services.push_back(state.get());
        }
    }

    state->_from = period.since;

    // Get notification period of host/service. If this host/service is no
    // longer available in nagios -> set to ""
    state->_notification_period =
        state->_service != nullptr ? state->_service->notificationPeriodName()
        : state->_host != nullptr  ? state->_host->notificationPeriodName()
                                   : "";

    // Same for service period.
    state->_service_period =
        state->_service != nullptr ? state->_service->servicePeriodName()
        : state->_host != nullptr  ? state->_host->servicePeriodName()
                                   : "";

    // Determine initial in_notification_period status
    auto tmp_period = notification_periods.find(state->_notification_period);
    if (tmp_period != notification_periods.end()) {
        state->_in_notification_period = tmp_period->second;
    } else {
        state->_in_notification_period = 1;
    }

    // Same for service period
    tmp_period = notification_periods.find(state->_service_period);
    if (tmp_period != notification_periods.end()) {
        state->_in_service_period = tmp_period->second;
    } else {
        state->_in_service_period = 1;
    }

    // If this key is a service try to find its host and apply its
    // _in_host_downtime and _host_down parameters
    if (!state->_is_host) {
        auto my_host = state_info.find(state->_host->handleForStateHistory());
        if (my_host != state_info.end()) {
            state->_in_host_downtime = my_host->second->_in_host_downtime;
            state->_host_down = my_host->second->_host_down;
        }
    }

    // Log UNMONITORED state if this host or service just appeared within
    // the query timeframe. It gets a grace period of ten minutes (nagios
    // startup)
    if (!only_update && entry->time() - period.since > 10min) {
        state->_debug_info = "UNMONITORED ";
        state->_state = -1;
    }

    // Store this state object for tracking state transitions
    state_info[key] = std::move(state);
}

void TableStateHistory::handle_timeperiod_transition(
    Query &query, const User &user, const ICore &core, const LogPeriod &period,
    const LogEntry *entry, bool only_update,
    notification_periods_t &notification_periods,
    const state_info_t &state_info) {
    try {
        const TimeperiodTransition tpt(entry->options());
        notification_periods[tpt.name()] = tpt.to();
        for (const auto &[key, hss] : state_info) {
            updateHostServiceState(query, user, core, period, entry, *hss,
                                   only_update, notification_periods);
        }
    } catch (const std::logic_error &e) {
        Warning(core.loggerLivestatus())
            << "Error: Invalid syntax of TIMEPERIOD TRANSITION: "
            << entry->message();
    }
}

void TableStateHistory::final_reports(Query &query, const User &user,
                                      const state_info_t &state_info,
                                      const LogPeriod &period) {
    for (const auto &[key, hss] : state_info) {
        // No trace since the last two nagios startup -> host/service has
        // vanished
        if (hss->_may_no_longer_exist) {
            // Log last known state up to nagios restart
            hss->_time = hss->_last_known_time;
            hss->_until = hss->_last_known_time;
            process(query, user, period, *hss);

            // Set absent state
            hss->_state = -1;
            hss->_debug_info = "UNMONITORED";
            hss->_log_output = "";
            hss->_long_log_output = "";
        }

        // A slight hack: We put the final HostServiceStates a tiny bit before
        // the end of the query period. Conceptually, they are exactly at
        // period.until, but rows with such a timestamp would get filtered out:
        // The query period is a half-open interval.
        hss->_time = period.until - 1s;
        hss->_until = hss->_time;

        process(query, user, period, *hss);
    }
}

void TableStateHistory::update(
    Query &query, const User &user, const ICore &core, const LogPeriod &period,
    const LogEntry *entry, HostServiceState &state, bool only_update,
    const notification_periods_t &notification_periods) {
    auto state_changed =
        updateHostServiceState(query, user, core, period, entry, state,
                               only_update, notification_periods);
    // Host downtime or state changes also affect its services
    if (entry->kind() == LogEntryKind::alert_host ||
        entry->kind() == LogEntryKind::state_host ||
        entry->kind() == LogEntryKind::downtime_alert_host) {
        if (state_changed == ModificationStatus::changed) {
            for (auto &svc : state._services) {
                updateHostServiceState(query, user, core, period, entry, *svc,
                                       only_update, notification_periods);
            }
        }
    }
}

// NOLINTNEXTLINE(readability-function-cognitive-complexity)
TableStateHistory::ModificationStatus TableStateHistory::updateHostServiceState(
    Query &query, const User &user, const ICore &core, const LogPeriod &period,
    const LogEntry *entry, HostServiceState &hss, bool only_update,
    const notification_periods_t &notification_periods) {
    ModificationStatus state_changed{ModificationStatus::changed};

    // Revive host / service if it was unmonitored
    if (entry->kind() != LogEntryKind::timeperiod_transition &&
        hss._has_vanished) {
        hss._time = hss._last_known_time;
        hss._until = hss._last_known_time;
        if (!only_update) {
            process(query, user, period, hss);
        }

        hss._may_no_longer_exist = false;
        hss._has_vanished = false;
        // Set absent state
        hss._state = -1;
        hss._debug_info = "UNMONITORED";
        hss._in_downtime = 0;
        hss._in_notification_period = 0;
        hss._in_service_period = 0;
        hss._is_flapping = 0;
        hss._log_output = "";
        hss._long_log_output = "";

        // Apply latest notification period information and set the host_state
        // to unmonitored
        auto it_status = notification_periods.find(hss._notification_period);
        if (it_status != notification_periods.end()) {
            hss._in_notification_period = it_status->second;
        } else {
            // No notification period information available -> within
            // notification period
            hss._in_notification_period = 1;
        }

        // Same for service period
        it_status = notification_periods.find(hss._service_period);
        if (it_status != notification_periods.end()) {
            hss._in_service_period = it_status->second;
        } else {
            // No service period information available -> within service period
            hss._in_service_period = 1;
        }
    }

    // Update basic information
    hss._time = entry->time();
    hss._lineno = entry->lineno();
    hss._until = entry->time();

    // A timeperiod entry never brings an absent host or service into
    // existence..
    if (entry->kind() != LogEntryKind::timeperiod_transition) {
        hss._may_no_longer_exist = false;
    }

    switch (entry->kind()) {
        case LogEntryKind::none:
        case LogEntryKind::core_starting:
        case LogEntryKind::core_stopping:
        case LogEntryKind::log_version:
        case LogEntryKind::log_initial_states:
        case LogEntryKind::acknowledge_alert_host:
        case LogEntryKind::acknowledge_alert_service:
            break;
        case LogEntryKind::state_host:
        case LogEntryKind::state_host_initial:
        case LogEntryKind::alert_host: {
            if (hss._is_host) {
                if (hss._state != entry->state()) {
                    if (!only_update) {
                        process(query, user, period, hss);
                    }
                    hss._state = entry->state();
                    hss._host_down = static_cast<int>(entry->state() > 0);
                    hss._debug_info = "HOST STATE";
                } else {
                    state_changed = ModificationStatus::unchanged;
                }
            } else if (hss._host_down != static_cast<int>(entry->state() > 0)) {
                if (!only_update) {
                    process(query, user, period, hss);
                }
                hss._host_down = static_cast<int>(entry->state() > 0);
                hss._debug_info = "SVC HOST STATE";
            }
            break;
        }
        case LogEntryKind::state_service:
        case LogEntryKind::state_service_initial:
        case LogEntryKind::alert_service: {
            if (hss._state != entry->state()) {
                if (!only_update) {
                    process(query, user, period, hss);
                }
                hss._debug_info = "SVC ALERT";
                hss._state = entry->state();
            }
            break;
        }
        case LogEntryKind::downtime_alert_host: {
            const int downtime_active =
                entry->state_type().starts_with("STARTED") ? 1 : 0;

            if (hss._in_host_downtime != downtime_active) {
                if (!only_update) {
                    process(query, user, period, hss);
                }
                hss._debug_info =
                    hss._is_host ? "HOST DOWNTIME" : "SVC HOST DOWNTIME";
                hss._in_host_downtime = downtime_active;
                if (hss._is_host) {
                    hss._in_downtime = downtime_active;
                }
            } else {
                state_changed = ModificationStatus::unchanged;
            }
            break;
        }
        case LogEntryKind::downtime_alert_service: {
            const int downtime_active =
                entry->state_type().starts_with("STARTED") ? 1 : 0;
            if (hss._in_downtime != downtime_active) {
                if (!only_update) {
                    process(query, user, period, hss);
                }
                hss._debug_info = "DOWNTIME SERVICE";
                hss._in_downtime = downtime_active;
            }
            break;
        }
        case LogEntryKind::flapping_host:
        case LogEntryKind::flapping_service: {
            const int flapping_active =
                entry->state_type().starts_with("STARTED") ? 1 : 0;
            if (hss._is_flapping != flapping_active) {
                if (!only_update) {
                    process(query, user, period, hss);
                }
                hss._debug_info = "FLAPPING ";
                hss._is_flapping = flapping_active;
            } else {
                state_changed = ModificationStatus::unchanged;
            }
            break;
        }
        case LogEntryKind::timeperiod_transition: {
            try {
                const TimeperiodTransition tpt(entry->options());
                // if no _host pointer is available the initial status of
                // _in_notification_period (1) never changes
                if (hss._host != nullptr &&
                    tpt.name() == hss._notification_period) {
                    if (tpt.to() != hss._in_notification_period) {
                        if (!only_update) {
                            process(query, user, period, hss);
                        }
                        hss._debug_info = "TIMEPERIOD ";
                        hss._in_notification_period = tpt.to();
                    }
                }
                // same for service period
                if (hss._host != nullptr && tpt.name() == hss._service_period) {
                    if (tpt.to() != hss._in_service_period) {
                        if (!only_update) {
                            process(query, user, period, hss);
                        }
                        hss._debug_info = "TIMEPERIOD ";
                        hss._in_service_period = tpt.to();
                    }
                }
            } catch (const std::logic_error &e) {
                Warning(core.loggerLivestatus())
                    << "Error: Invalid syntax of TIMEPERIOD TRANSITION: "
                    << entry->message();
            }
            break;
        }
    }

    if (entry->kind() != LogEntryKind::timeperiod_transition) {
        const bool fix_me =
            (entry->kind() == LogEntryKind::state_host_initial ||
             entry->kind() == LogEntryKind::state_service_initial) &&
            entry->plugin_output() == "(null)";
        hss._log_output = fix_me ? "" : entry->plugin_output();
        hss._long_log_output = entry->long_plugin_output();
    }

    return state_changed;
}

void TableStateHistory::process(Query &query, const User &user,
                                const LogPeriod &period,
                                HostServiceState &hss) {
    hss._duration = hss._until - hss._from;
    hss.computePerStateDurations(period.duration());

    // if (hss._duration > 0)
    abort_query_ =
        user.is_authorized_for_object(hss._host, hss._service, false) &&
        !query.processDataset(Row{&hss});

    hss._from = hss._until;
}

std::shared_ptr<Column> TableStateHistory::column(std::string colname) const {
    try {
        // First try to find column in the usual way
        return Table::column(colname);
    } catch (const std::runtime_error &e) {
        // Now try with prefix "current_", since our joined tables have this
        // prefix in order to make clear that we access current and not historic
        // data and in order to prevent mixing up historic and current fields
        // with the same name.
        return Table::column("current_" + colname);
    }
}
