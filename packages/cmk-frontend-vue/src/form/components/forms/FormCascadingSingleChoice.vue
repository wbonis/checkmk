<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { computed, ref, watch, toRaw } from 'vue'
import FormEdit from '@/form/components/FormEdit.vue'
import { immediateWatch } from '@/form/components/utils/watch'
import type {
  CascadingSingleChoice,
  CascadingSingleChoiceElement,
  FormSpec
} from '@/form/components/vue_formspec_components'
import { useId } from '@/form/utils'
import FormValidation from '@/form/components/FormValidation.vue'
import { validateValue, type ValidationMessages } from '@/form/components/utils/validation'
import HelpText from '@/components/HelpText.vue'
import ToggleButtonGroup from '@/components/ToggleButtonGroup.vue'
import DropDown from '@/components/DropDown.vue'

const props = defineProps<{
  spec: CascadingSingleChoice
  backendValidation: ValidationMessages
}>()

const validation = ref<Array<string>>([])
const elementValidation = ref<ValidationMessages>([])

watch(
  () => props.backendValidation,
  (newValidation: ValidationMessages) => {
    validation.value = []
    elementValidation.value = []
    newValidation.forEach((msg) => {
      if (msg.location.length === 0) {
        validation.value.push(msg.message)
        return
      }
      elementValidation.value.push({
        location: msg.location.slice(1),
        message: msg.message,
        invalid_value: msg.invalid_value
      })
    })
  },
  { immediate: true }
)

const data = defineModel<[string, unknown]>('data', { required: true })

const currentValues: Record<string, unknown> = {}
immediateWatch(
  () => props.spec.elements,
  (newValue) => {
    newValue.forEach((element: CascadingSingleChoiceElement) => {
      const key = element.name
      if (data.value[0] === key) {
        currentValues[key] = data.value[1]
      } else {
        currentValues[key] = structuredClone(toRaw(element.default_value))
      }
    })
  }
)

const selectedOption = computed({
  get(): string {
    return data.value[0] as string
  },
  set(value: string) {
    // keep old data in case user switches back and they don't loose their modifications
    currentValues[data.value[0]] = data.value[1]

    validation.value = []
    const newValue: [string, unknown] = [value, currentValues[value]]
    validateValue(value, props.spec.validators!).forEach((error) => {
      validation.value = [error]
    })
    data.value = newValue
  }
})

interface ActiveElement {
  spec: FormSpec
  validation: ValidationMessages
}

const activeElement = computed((): ActiveElement | null => {
  const element = props.spec.elements.find(
    (element: CascadingSingleChoiceElement) => element.name === data.value[0]
  )
  if (element === undefined) {
    return null
  }
  return {
    spec: element!.parameter_form,
    validation: []
  }
})

const componentId = useId()

interface LayoutSettings {
  display_style: string
  side_by_side: boolean
}

const layoutSettings = computed((): LayoutSettings => {
  return {
    display_style: props.spec.layout === 'vertical' ? 'inline' : 'inline-block',
    side_by_side: props.spec.layout === 'button_group'
  }
})

const buttonGroupButtons = computed((): Array<{ label: string; value: string }> => {
  return props.spec.elements.map((element: CascadingSingleChoiceElement) => {
    return { label: element.title, value: element.name }
  })
})
</script>

<template>
  <span class="form-cascading-single-choice__choice">
    <label v-if="$props.spec.label" :for="componentId">{{ props.spec.label }}</label>
    <template v-if="!layoutSettings.side_by_side">
      <DropDown
        v-model:selected-option="selectedOption"
        :component-id="componentId"
        :options="spec.elements"
        :input_hint="props.spec.input_hint as string"
      />
    </template>
    <template v-else>
      <ToggleButtonGroup v-model="selectedOption" :options="buttonGroupButtons" />
    </template>
  </span>
  <span class="form-cascading-single-choice__cascade">
    <template v-if="activeElement !== null">
      <HelpText :help="activeElement.spec.help" />
      <FormEdit
        :key="data[0]"
        v-model:data="data[1]"
        :spec="activeElement.spec"
        :backend-validation="elementValidation"
      ></FormEdit>

      <FormValidation :validation="validation"></FormValidation>
    </template>
  </span>
</template>

<style scoped>
span.form-cascading-single-choice__choice,
span.form-cascading-single-choice__cascade {
  vertical-align: top;
}

span.form-cascading-single-choice__choice {
  margin-right: 5px;
}

span.form-cascading-single-choice__cascade {
  display: v-bind('layoutSettings.display_style');
}
</style>
