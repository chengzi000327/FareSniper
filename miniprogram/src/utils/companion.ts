import type {
  CompanionKind,
  CompanionProfile,
  MemoryItem,
} from '../types/api'

export const COMPANION_DEFAULTS: Record<CompanionKind, string> = {
  cat: '云朵',
  corgi: '登登',
  penguin: '小候',
  plain: '旅伴',
}

export const COMPANION_CHOICES: Array<{
  kind: Exclude<CompanionKind, 'plain'>
  title: string
  detail: string
}> = [
  { kind: 'cat', title: '云朵猫', detail: '安静记下每个想法' },
  { kind: 'corgi', title: '登登柯基', detail: '发现低价就来找你' },
  { kind: 'penguin', title: '小候企鹅', detail: '陪你等待出发时机' },
]

export function companionFromMemory(memories: MemoryItem[]): CompanionProfile {
  const raw = memories.find((item) => item.field === 'companion_profile')?.value
  const profile =
    raw && typeof raw === 'object' && !Array.isArray(raw)
      ? (raw as Record<string, unknown>)
      : null
  const rawKind = profile?.kind
  const kind: CompanionKind =
    rawKind === 'corgi' ||
    rawKind === 'penguin' ||
    rawKind === 'plain'
      ? rawKind
      : 'cat'
  const rawName = profile?.name
  const name =
    typeof rawName === 'string' && rawName.trim()
      ? rawName.trim()
      : COMPANION_DEFAULTS[kind]
  return { kind, name }
}

export function hasCompanion(memories: MemoryItem[]) {
  return memories.some((item) => item.field === 'companion_profile')
}

export function preferenceCount(memories: MemoryItem[]) {
  return memories.filter(
    (item) => !['companion_profile', 'travel_ideas'].includes(item.field),
  ).length
}

export function explicitIdeaCount(memories: MemoryItem[]) {
  const value = memories.find((item) => item.field === 'travel_ideas')?.value
  return Array.isArray(value) ? value.length : 0
}
