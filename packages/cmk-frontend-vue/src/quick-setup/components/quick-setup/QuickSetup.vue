<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { computed } from 'vue'

import QuickSetupStage from './QuickSetupStage.vue'
import QuickSetupSaveStage from './QuickSetupSaveStage.vue'
import type { QuickSetupProps } from './quick_setup_types'

const props = defineProps<QuickSetupProps>()

const numberOfStages = computed(() => props.regularStages.length)
const showSaveStage = computed(
  () => props.currentStage === numberOfStages.value || props.mode.value === 'overview'
)
</script>

<template>
  <ol class="quick-setup">
    <QuickSetupStage
      v-for="(stg, index) in regularStages"
      :key="index"
      :index="index"
      :current-stage="currentStage"
      :number-of-stages="numberOfStages"
      :mode="props.mode.value"
      :loading="loading"
      :title="stg.title"
      :sub_title="stg.sub_title || null"
      :buttons="stg.buttons || []"
      :content="stg.content || null"
      :recap-content="stg.recapContent || null"
      :errors="stg.errors"
      :go-to-this-stage="stg.goToThisStage || null"
    />
  </ol>
  <QuickSetupSaveStage
    v-if="saveStage && showSaveStage"
    :index="numberOfStages"
    :current-stage="currentStage"
    :number-of-stages="numberOfStages"
    :mode="props.mode.value"
    :loading="loading"
    :content="saveStage.content || null"
    :errors="saveStage.errors || []"
    :buttons="saveStage.buttons || []"
  />
</template>

<style scoped>
.quick-setup {
  margin: 8px 0 0;
  padding-left: 0;
  counter-reset: stage-index;
}

.quick-setup__action {
  padding-left: 40px;
}

.quick-setup__loading {
  display: flex;
  align-items: center;
  padding-top: 12px;
}
</style>
