import { Button, Input, Picker, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useCallback, useMemo, useState } from 'react'

import { Companion } from '../../components/Companion'
import { miniApi } from '../../services/api'
import type { MemoryItem, MemoryResponse } from '../../types/api'
import { companionFromMemory } from '../../utils/companion'
import './index.scss'

type Section = 'preferences' | 'ideas' | 'queries' | 'journal'

const PREFERENCE_OPTIONS = [
  { field: 'budget', label: '心理价位' },
  { field: 'frequent_cities', label: '常去城市' },
  { field: 'preferred_airlines', label: '偏好航司' },
  { field: 'constraints', label: '出行习惯' },
  { field: 'travel_scenes', label: '出行场景' },
] as const

const ARRAY_FIELDS = new Set([
  'frequent_cities',
  'preferred_airlines',
  'constraints',
  'travel_scenes',
])

const VALUE_CODES: Record<string, string> = {
  只看直飞: 'direct_only',
  避开红眼航班: 'avoid_redeye',
  偏好上午出发: 'prefer_morning',
  偏好靠窗座位: 'prefer_window',
  不要中转: 'avoid_stopover',
  需要托运行李: 'checked_baggage',
  只带随身行李: 'carry_on_only',
  商务出行: 'business',
  休闲旅行: 'leisure',
  探亲回家: 'family_visit',
  家庭出行: 'with_family',
  亲子出行: 'with_children',
  独自出行: 'solo',
}

const CODE_LABELS = Object.fromEntries(
  Object.entries(VALUE_CODES).map(([label, code]) => [code, label]),
)

function displayValue(item: MemoryItem) {
  if (item.value_display) return item.value_display
  if (Array.isArray(item.value)) {
    return item.value
      .map((value) => CODE_LABELS[String(value)] || String(value))
      .join('、')
  }
  return String(item.value)
}

function draftValue(item: MemoryItem) {
  if (Array.isArray(item.value)) {
    return item.value
      .map((value) => CODE_LABELS[String(value)] || String(value))
      .join('、')
  }
  return String(item.value ?? '')
}

function parseValue(field: string, raw: string) {
  const value = raw.trim()
  if (field === 'budget') {
    const budget = Number(value.replace(/[^\d.]/g, ''))
    if (!Number.isFinite(budget) || budget <= 0) {
      throw new Error('请输入正确的心理价位')
    }
    return Math.round(budget)
  }
  if (ARRAY_FIELDS.has(field)) {
    const values = value
      .split(/[、,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (!values.length) throw new Error('请至少保留一项内容')
    return [...new Set(values.map((item) => VALUE_CODES[item] || item))]
  }
  if (!value) throw new Error('内容不能为空')
  return value
}

function queryText(item: MemoryResponse['query_history'][number]) {
  if (item.query_text) return item.query_text
  if (typeof item.query === 'string') return item.query
  if (item.query?.text) return item.query.text
  return '一次机票查询'
}

export default function MemoryPage() {
  const [memory, setMemory] = useState<MemoryResponse>({
    memories: [],
    query_history: [],
  })
  const [section, setSection] = useState<Section>('preferences')
  const [loading, setLoading] = useState(true)
  const [editingField, setEditingField] = useState('')
  const [draft, setDraft] = useState('')
  const [adding, setAdding] = useState(false)
  const [newFieldIndex, setNewFieldIndex] = useState(0)
  const [newValue, setNewValue] = useState('')
  const [ideaText, setIdeaText] = useState('')
  const [savingField, setSavingField] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setMemory(await miniApi.memory())
    } catch {
      await Taro.showToast({ title: '记忆暂时没有接上', icon: 'none' })
    } finally {
      setLoading(false)
      Taro.stopPullDownRefresh()
    }
  }, [])

  useDidShow(() => {
    const pendingSection = Taro.getStorageSync<Section>('fs_memory_section')
    if (
      pendingSection &&
      ['preferences', 'ideas', 'queries', 'journal'].includes(pendingSection)
    ) {
      setSection(pendingSection)
      Taro.removeStorageSync('fs_memory_section')
    }
    void load()
  })
  usePullDownRefresh(() => void load())

  const companion = companionFromMemory(memory.memories)
  const preferences = useMemo(
    () =>
      memory.memories.filter(
        (item) => !['companion_profile', 'travel_ideas'].includes(item.field),
      ),
    [memory.memories],
  )
  const ideas = useMemo(() => {
    const raw = memory.memories.find(
      (item) => item.field === 'travel_ideas',
    )?.value
    return Array.isArray(raw) ? raw : []
  }, [memory.memories])

  const savePreference = async (field: string, valueDraft: string) => {
    try {
      const value = parseValue(field, valueDraft)
      setSavingField(field)
      await miniApi.patchMemory(field, value)
      setEditingField('')
      setAdding(false)
      setNewValue('')
      await load()
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '保存失败',
        icon: 'none',
      })
    } finally {
      setSavingField('')
    }
  }

  const forgetPreference = async (item: MemoryItem) => {
    const modal = await Taro.showModal({
      title: `忘记“${item.label || item.field}”吗？`,
      content: '删除后，后续查价和排序将不再使用这项偏好。',
      confirmText: '确认忘记',
      confirmColor: '#FF7A2F',
    })
    if (!modal.confirm) return
    setSavingField(item.field)
    try {
      await miniApi.deleteMemory(item.field)
      await load()
    } catch {
      await Taro.showToast({ title: '暂时无法忘记这项偏好', icon: 'none' })
    } finally {
      setSavingField('')
    }
  }

  const ideaValue = (idea: unknown) => {
    if (idea && typeof idea === 'object' && !Array.isArray(idea)) {
      const record = idea as Record<string, unknown>
      return typeof record.text === 'string' ? record.text : String(idea)
    }
    return String(idea)
  }

  const saveIdeas = async (nextIdeas: unknown[]) => {
    setSavingField('travel_ideas')
    try {
      await miniApi.patchMemory('travel_ideas', nextIdeas)
      setIdeaText('')
      await load()
    } catch {
      await Taro.showToast({ title: '关注暂时没有保存成功', icon: 'none' })
    } finally {
      setSavingField('')
    }
  }

  const sections: Array<{ id: Section; label: string; count: number }> = [
    { id: 'preferences', label: '偏好', count: preferences.length },
    { id: 'ideas', label: '关注', count: ideas.length },
    { id: 'queries', label: '查询', count: memory.query_history.length },
    { id: 'journal', label: '手帐', count: 0 },
  ]

  return (
    <View className="page-shell memory-page">
      <View className="memory-page__header">
        <View>
          <Text className="eyebrow">只记真实发生的事</Text>
          <Text className="page-title">我的记忆</Text>
        </View>
        <View
          className={`icon-button ${loading ? 'is-loading' : ''}`}
          onClick={() => void load()}
        >
          ↻
        </View>
      </View>

      <View className="memory-page__hero companion-card">
        <Companion
          kind={companion.kind}
          className="memory-page__companion-avatar"
        />
        <View className="memory-page__hero-copy">
          <Text className="memory-page__hero-kicker">
            {companion.name}的记忆盒
          </Text>
          <Text className="memory-page__hero-title">你说过的，可以修改</Text>
          <Text className="memory-page__hero-detail">
            搜索记录和明确关注分开放，手帐只写真正成行。
          </Text>
        </View>
      </View>

      <View className="memory-tabs">
        {sections.map((item) => (
          <View
            className={`memory-tab ${section === item.id ? 'is-active' : ''}`}
            key={item.id}
            onClick={() => setSection(item.id)}
          >
            <Text>{item.label}</Text>
            <Text className="memory-tab__count">{item.count}</Text>
          </View>
        ))}
      </View>

      {section === 'preferences' ? (
        <View className="memory-section">
          <View className="memory-section__heading">
            <View>
              <Text className="memory-section__title">机票偏好</Text>
              <Text className="memory-section__hint">
                下次查价和排序会使用这些内容
              </Text>
            </View>
            <Button
              className="memory-add"
              onClick={() => setAdding((current) => !current)}
            >
              {adding ? '收起' : '＋ 添加'}
            </Button>
          </View>

          {adding ? (
            <View className="memory-editor card">
              <Picker
                mode="selector"
                range={PREFERENCE_OPTIONS.map((option) => option.label)}
                value={newFieldIndex}
                onChange={(event) => {
                  setNewFieldIndex(Number(event.detail.value))
                  setNewValue('')
                }}
              >
                <View className="memory-editor__picker">
                  {PREFERENCE_OPTIONS[newFieldIndex].label}
                  <Text>⌄</Text>
                </View>
              </Picker>
              <Input
                className="memory-editor__input"
                type={
                  PREFERENCE_OPTIONS[newFieldIndex].field === 'budget'
                    ? 'number'
                    : 'text'
                }
                placeholder={
                  PREFERENCE_OPTIONS[newFieldIndex].field === 'budget'
                    ? '例如：800'
                    : '多项内容用顿号分开'
                }
                value={newValue}
                onInput={(event) => setNewValue(event.detail.value)}
              />
              <Button
                className="primary-button"
                disabled={!newValue.trim()}
                onClick={() =>
                  void savePreference(
                    PREFERENCE_OPTIONS[newFieldIndex].field,
                    newValue,
                  )
                }
              >
                保存偏好
              </Button>
            </View>
          ) : null}

          {preferences.length ? (
            preferences.map((item) => (
              <View className="memory-item card" key={item.field}>
                <View className="memory-item__top">
                  <View>
                    <Text className="memory-item__source">
                      {item.source === 'manual' || item.source === 'user'
                        ? '你亲自确认'
                        : '根据真实行为学习'}
                    </Text>
                    <Text className="memory-item__title">
                      {item.label || item.field}
                    </Text>
                  </View>
                  {!editingField ? (
                    <View className="memory-item__actions">
                      <Button
                        onClick={() => {
                          setEditingField(item.field)
                          setDraft(draftValue(item))
                        }}
                      >
                        编辑
                      </Button>
                      <Button
                        disabled={savingField === item.field}
                        onClick={() => void forgetPreference(item)}
                      >
                        忘记
                      </Button>
                    </View>
                  ) : null}
                </View>
                {editingField === item.field ? (
                  <View className="memory-item__editing">
                    <Input
                      className="memory-editor__input"
                      type={item.field === 'budget' ? 'number' : 'text'}
                      value={draft}
                      onInput={(event) => setDraft(event.detail.value)}
                    />
                    <View>
                      <Button
                        className="primary-button"
                        disabled={savingField === item.field}
                        onClick={() =>
                          void savePreference(item.field, draft)
                        }
                      >
                        保存
                      </Button>
                      <Button onClick={() => setEditingField('')}>取消</Button>
                    </View>
                  </View>
                ) : (
                  <Text className="memory-item__value">
                    {displayValue(item)}
                  </Text>
                )}
              </View>
            ))
          ) : (
            <Empty
              title="还没有机票偏好"
              detail="完成一次查询后，旅伴会逐步理解你的特价定义。"
            />
          )}
        </View>
      ) : section === 'ideas' ? (
        <View className="memory-section">
          <Text className="memory-section__title">你明确说过的关注</Text>
          <Text className="memory-section__hint">
            只有主动保存的想法会出现在这里，系统不会从查询里猜。
          </Text>
          <View className="idea-editor card">
            <Input
              className="memory-editor__input"
              placeholder="例如：今年秋天想去青岛"
              value={ideaText}
              onInput={(event) => setIdeaText(event.detail.value)}
            />
            <Button
              disabled={!ideaText.trim()}
              onClick={() =>
                void saveIdeas([
                  ...ideas,
                  {
                    id: `idea_${Date.now()}`,
                    text: ideaText.trim(),
                    created_at: new Date().toISOString(),
                  },
                ])
              }
            >
              保存关注
            </Button>
          </View>
          {ideas.length ? (
            ideas.map((idea, index) => (
              <View className="memory-item card" key={index}>
                <View className="memory-item__top">
                  <View>
                    <Text className="memory-item__source">你亲自记录</Text>
                    <Text className="memory-item__value">
                      {ideaValue(idea)}
                    </Text>
                  </View>
                  <Button
                    className="idea-delete"
                    onClick={() =>
                      void saveIdeas(ideas.filter((_, itemIndex) => itemIndex !== index))
                    }
                  >
                    删除
                  </Button>
                </View>
              </View>
            ))
          ) : (
            <Empty
              title="还没有明确关注"
              detail="想去的地方仍然只是想法，不会被写成已经去过。"
            />
          )}
        </View>
      ) : section === 'queries' ? (
        <View className="memory-section">
          <Text className="memory-section__title">最近查询</Text>
          <Text className="memory-section__hint">
            这里只说明查过，不代表你明确想去。
          </Text>
          {memory.query_history.length ? (
            memory.query_history.map((item, index) => (
              <View className="query-item card" key={String(item.id || index)}>
                <View className="query-item__icon">⌕</View>
                <View>
                  <Text className="memory-item__source">真实查询</Text>
                  <Text className="query-item__text">{queryText(item)}</Text>
                </View>
              </View>
            ))
          ) : (
            <Empty
              title="还没有查询记录"
              detail="从对话页发起真实机票查询后会出现在这里。"
            />
          )}
        </View>
      ) : (
        <View className="journal">
          <Text className="journal__stamp">尚未成行</Text>
          <Text className="journal__kicker">TRAVEL NOTE · 第一页</Text>
          <Text className="journal__title">把真正出发的那天，留给手帐</Text>
          <View className="journal__middle">
            <Text className="journal__detail">
              确认买票或录入真实行程后，旅伴才会写下日期、目的地和当时的想法。
            </Text>
            <Companion
              kind={companion.kind}
              pose="journal"
              className="journal__companion"
            />
          </View>
          <View className="journal__future">
            <Text>未来的一页会记录</Text>
            <Text className="journal__tags">
              出发日期 · 真实行程 · 你的想法 · 旅伴小记
            </Text>
          </View>
          <Text className="journal__note">
            查询、关注和点击预订仍只保留原本含义，不会被写成已经去过。
          </Text>
        </View>
      )}
    </View>
  )
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <View className="memory-empty">
      <Text className="memory-empty__title">{title}</Text>
      <Text className="memory-empty__detail">{detail}</Text>
    </View>
  )
}
