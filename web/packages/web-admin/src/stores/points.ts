import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Point3D {
  x: number
  y: number
  z: number
}

export const usePointsStore = defineStore('points', () => {
  const points = ref<Point3D[]>([])
  const progress = ref(0)
  const status = ref<'idle' | 'loading' | 'parsing' | 'ready' | 'error'>('idle')
  const statusText = ref('')
  const is3D = ref(true)
  const totalLines = ref(0)
  const errorMessage = ref('')
  const clickedPoint = ref<Point3D | null>(null)
  const clickedIndex = ref(-1)
  const selectedIndices = ref<Set<number>>(new Set())

  const pointCount = computed(() => points.value.length)
  const selectedPoints = computed(() => {
    const result: { index: number; x: number; y: number; z: number }[] = []
    selectedIndices.value.forEach((i) => {
      if (i < points.value.length) {
        result.push({ index: i, ...points.value[i] })
      }
    })
    return result
  })

  function reset() {
    points.value = []
    progress.value = 0
    status.value = 'idle'
    statusText.value = ''
    is3D.value = true
    totalLines.value = 0
    errorMessage.value = ''
    clickedPoint.value = null
    clickedIndex.value = -1
    selectedIndices.value = new Set()
  }

  function setProgress(p: number, text?: string) {
    progress.value = p
    if (text) statusText.value = text
  }

  function setPoints(data: Point3D[], threeD: boolean) {
    points.value = data
    is3D.value = threeD
    status.value = 'ready'
    progress.value = 100
    statusText.value = `已加载 ${data.length.toLocaleString()} 个点`
  }

  function setError(msg: string) {
    status.value = 'error'
    errorMessage.value = msg
    statusText.value = msg
  }

  function setClickedPoint(index: number, point: Point3D | null) {
    clickedIndex.value = index
    clickedPoint.value = point
  }

  function addToSelection(indices: number[]) {
    indices.forEach((i) => selectedIndices.value.add(i))
  }

  function setSelection(indices: number[]) {
    selectedIndices.value = new Set(indices)
  }

  function clearSelection() {
    selectedIndices.value.clear()
    clickedPoint.value = null
    clickedIndex.value = -1
  }

  return {
    points,
    progress,
    status,
    statusText,
    is3D,
    totalLines,
    errorMessage,
    pointCount,
    clickedPoint,
    clickedIndex,
    selectedIndices,
    selectedPoints,
    reset,
    setProgress,
    setPoints,
    setError,
    setClickedPoint,
    addToSelection,
    setSelection,
    clearSelection,
  }
})
