<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import type * as FormSpec from '@/form/components/vue_formspec_components'
import { useValidation, type ValidationMessages } from '@/form/components/utils/validation'
import FormEdit from '@/form/components/FormEdit.vue'
import FormValidation from '@/form/components/FormValidation.vue'
import { ref } from 'vue'
import { immediateWatch } from '../utils/watch'
import { useId } from '@/form/utils'
import HelpText from '@/components/HelpText.vue'

const props = defineProps<{
  spec: FormSpec.OptionalChoice
  backendValidation: ValidationMessages
}>()

const data = defineModel<unknown>('data', { required: true })
const [validation, value] = useValidation<unknown>(
  data,
  props.spec.validators,
  () => props.backendValidation
)

const embeddedValidation = ref<ValidationMessages>([])

immediateWatch(
  () => props.backendValidation,
  (newValidation: ValidationMessages) => {
    embeddedValidation.value = newValidation
      .filter((msg) => msg.location.length > 1)
      .map((msg) => {
        return {
          location: msg.location.slice(1),
          message: msg.message,
          invalid_value: msg.invalid_value
        }
      })
  }
)

const componentId = useId()
</script>

<template>
  <input
    :id="`${componentId}_input`"
    :checked="value !== null"
    type="checkbox"
    @change="value = value === null ? spec.parameter_form_default_value : null"
  />
  <label :for="`${componentId}_input`">
    {{ spec.i18n.label }}
  </label>
  <HelpText :help="spec.help" />
  <div v-if="value !== null" class="embedded">
    <span v-if="spec.parameter_form.title" class="embedded_title">
      {{ spec.parameter_form.title }}
    </span>
    <FormEdit
      v-model:data="value"
      :spec="spec.parameter_form"
      :backend-validation="embeddedValidation"
    />
  </div>
  <FormValidation :validation="validation"></FormValidation>
</template>

<style scoped>
span.embedded_title {
  margin-right: 3px;
}

div.embedded {
  margin-left: 40px;
}
</style>
