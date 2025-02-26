<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { ref, watch } from 'vue'

import CmkButton from '@/components/CmkButton.vue'
import CmkIcon from '@/components/CmkIcon.vue'
import CmkSpace from '@/components/CmkSpace.vue'
import FormEdit from '@/form/components/FormEdit.vue'
import type { List } from '@/form/components/vue_formspec_components'
import FormValidation from '@/form/components/FormValidation.vue'
import {
  groupIndexedValidations,
  validateValue,
  type ValidationMessages
} from '@/form/components/utils/validation'
import useDragging from '@/lib/useDragging'

const props = defineProps<{
  spec: List
  backendValidation: ValidationMessages
}>()

const backendData = defineModel<unknown[]>('data', { required: true })

type ElementIndex = number
const data = ref<Record<ElementIndex, unknown>>({})
const validation = ref<Array<string>>([])
const elementValidation = ref<Record<ElementIndex, ValidationMessages>>({})
const frontendOrder = ref<ElementIndex[]>([])
const newElementIndex = ref<ElementIndex>(0)

function initialize(newBackendData: unknown[]) {
  data.value = {}
  validation.value.splice(0)
  elementValidation.value = {}
  frontendOrder.value.splice(0)
  newBackendData.forEach((value, i) => {
    data.value[i] = value
    elementValidation.value[i] = []
    frontendOrder.value.push(i)
  })
  newElementIndex.value = newBackendData.length
}

watch(
  [backendData, () => props.backendValidation],
  ([newBackendData, newBackendValidation]) => {
    initialize(newBackendData)
    setValidation(newBackendValidation)
  },
  { immediate: true }
)

function setValidation(newBackendValidation: ValidationMessages) {
  const [_listValidations, _elementValidations] = groupIndexedValidations(
    newBackendValidation,
    backendData.value.length
  )
  validation.value = _listValidations
  elementValidation.value = _elementValidations
}

const { tableRef, dragStart, dragEnd, dragging } = useDragging()

function dragElement(event: DragEvent) {
  const dragReturn = dragging(event)
  if (dragReturn === null) {
    return
  }
  const movedEntry = frontendOrder.value.splice(dragReturn.draggedIndex, 1)[0]!
  frontendOrder.value.splice(dragReturn.targetIndex, 0, movedEntry)
  sendDataUpstream()
}

function validateList() {
  validation.value.splice(0)
  validateValue(backendData.value, props.spec.validators!).forEach((error) => {
    validation.value.push(error)
  })
}

function removeElement(index: ElementIndex) {
  frontendOrder.value.splice(frontendOrder.value.indexOf(index), 1)
  sendDataUpstream()
  validateList()
}

function addElement() {
  data.value[newElementIndex.value] = JSON.parse(JSON.stringify(props.spec.element_default_value))
  elementValidation.value[newElementIndex.value] = []
  frontendOrder.value.push(newElementIndex.value)
  newElementIndex.value += 1
  sendDataUpstream()
  validateList()
}

function updateElementData(newValue: unknown, index: ElementIndex) {
  data.value[index] = newValue
  sendDataUpstream()
}

function sendDataUpstream() {
  backendData.value.splice(0)
  frontendOrder.value.forEach((index: ElementIndex) => {
    backendData.value.push(data.value[index])
  })
}
</script>

<template>
  <table ref="tableRef" class="valuespec_listof">
    <template v-for="backendIndex in frontendOrder" :key="backendIndex">
      <tr class="listof_element">
        <td class="vlof_buttons">
          <CmkButton
            v-if="props.spec.editable_order"
            variant="transparent"
            aria-label="Drag to reorder"
            :draggable="true"
            @dragstart="dragStart"
            @drag="dragElement"
            @dragend="dragEnd"
          >
            <CmkIcon name="drag" size="small" style="pointer-events: none" />
          </CmkButton>
          <CmkSpace v-if="props.spec.editable_order" direction="vertical" />
          <!-- TODO: move this delete text to the backend to make it translatable (CMK-19020) -->
          <CmkButton
            variant="transparent"
            title="Delete this entry"
            @click.prevent="() => removeElement(backendIndex)"
          >
            <CmkIcon name="close" size="small" />
          </CmkButton>
        </td>
        <td class="vlof_content">
          <FormEdit
            v-model:data="data[backendIndex]"
            :spec="spec.element_template"
            :backend-validation="elementValidation[backendIndex]!"
            @update:data="(new_value: unknown) => updateElementData(new_value, backendIndex)"
          ></FormEdit>
        </td>
      </tr>
    </template>
  </table>
  <CmkButton variant="minimal" size="small" @click.prevent="addElement">
    <CmkIcon name="plus" />
    <CmkSpace size="small" />
    {{ spec.add_element_label }}
  </CmkButton>
  <FormValidation :validation="validation"></FormValidation>
</template>

<style scoped>
.valuespec_listof {
  border-collapse: collapse;
  margin-bottom: var(--spacing);

  > tbody > .listof_element,
  > .listof_element {
    --button-padding-top: 4px;

    > .vlof_buttons,
    > .vlof_content {
      vertical-align: top;
      padding: var(--spacing) 0;
    }

    > .vlof_content {
      padding-top: calc(var(--spacing) - var(--button-padding-top));
      padding-left: 8px;
    }

    &:first-child > .vlof_buttons {
      padding-top: var(--button-padding-top);
    }

    &:first-child > .vlof_content {
      padding-top: 0;
    }
  }
}
.vlof_buttons > * {
  display: flex;
}
</style>
