<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import CmkButton from './CmkButton.vue'

export type ToggleButtonOption = {
  label: string
  value: string
}

export interface ToggleButtonGroupProps {
  options: ToggleButtonOption[]
  value?: string | null
}

defineProps<ToggleButtonGroupProps>()
const model = defineModel<string>({ required: true })

const isSelected = (value: string) => value === model.value
function setSelectedOption(value: string) {
  model.value = value
}
</script>

<template>
  <div class="toggle_buttons_container">
    <CmkButton
      v-for="option in options"
      :key="option.value"
      class="toggle_option"
      :class="{ selected: isSelected(option.value) }"
      :aria-label="`Toggle ${option.label}`"
      @click.prevent="setSelectedOption(option.value)"
      >{{ option.label }}</CmkButton
    >
  </div>
</template>

<style scoped>
.toggle_buttons_container {
  width: max-content;
  padding: 5px;
  border-radius: 5px;
  border: 2px solid var(--default-border-color);
  background-color: transparent;
}

.toggle_option {
  height: auto;
  min-width: 150px;
  border: none;
  background-color: transparent;
  padding: 3px;
}

.selected {
  background-color: var(--default-form-element-bg-color);
}
</style>
