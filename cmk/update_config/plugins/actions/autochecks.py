#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from logging import Logger

from cmk.update_config.registry import update_action_registry, UpdateAction
from cmk.update_config.update_state import UpdateActionState

from ..lib.autochecks import rewrite_yielding_errors


class UpdateAutochecks(UpdateAction):
    def __call__(self, logger: Logger, update_action_state: UpdateActionState) -> None:
        # just consume to trigger rewriting. We already warned in pre-action.
        for _error in rewrite_yielding_errors(write=True):
            pass


update_action_registry.register(
    UpdateAutochecks(
        name="autochecks",
        title="Autochecks",
        sort_index=40,
    )
)
