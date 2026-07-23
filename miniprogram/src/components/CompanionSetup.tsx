import { Button, Input, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'

import { miniApi } from '../services/api'
import type { CompanionKind, CompanionProfile } from '../types/api'
import {
  COMPANION_CHOICES,
  COMPANION_DEFAULTS,
} from '../utils/companion'
import { Companion } from './Companion'
import './CompanionSetup.scss'

export function CompanionSetup({
  current,
  onSaved,
  onCancel,
}: {
  current?: CompanionProfile | null
  onSaved: (profile: CompanionProfile) => void
  onCancel?: () => void
}) {
  const [kind, setKind] = useState<CompanionKind>(current?.kind || 'cat')
  const [name, setName] = useState(
    current?.name || COMPANION_DEFAULTS[current?.kind || 'cat'],
  )
  const [saving, setSaving] = useState(false)

  const choose = (nextKind: CompanionKind) => {
    setKind(nextKind)
    setName(COMPANION_DEFAULTS[nextKind])
  }

  const save = async () => {
    const companionName = name.trim()
    if (!companionName) {
      await Taro.showToast({ title: '先给旅伴取个名字吧', icon: 'none' })
      return
    }
    setSaving(true)
    try {
      const profile = { kind, name: companionName }
      await miniApi.patchMemory('companion_profile', profile)
      onSaved(profile)
    } catch {
      await Taro.showToast({ title: '旅伴暂时没有保存成功', icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <View className="companion-setup">
      <View className="companion-setup__header">
        <View>
          <Text className="eyebrow">
            {current ? '我的旅伴' : '第一次见面'}
          </Text>
          <Text className="page-title">
            {current ? '重新选择旅伴' : '先选一个旅伴吧'}
          </Text>
        </View>
        {onCancel ? (
          <Button className="companion-setup__close" onClick={onCancel}>
            ×
          </Button>
        ) : null}
      </View>

      <Text className="companion-setup__intro">
        它会陪你查票、记下偏好、发现低价和写旅行手帐，但不会替你做购买决定。
      </Text>

      <View className="companion-setup__choices">
        {COMPANION_CHOICES.map((choice) => (
          <Button
            className={`companion-choice ${choice.kind === kind ? 'is-selected' : ''}`}
            key={choice.kind}
            onClick={() => choose(choice.kind)}
          >
            <Companion kind={choice.kind} />
            <Text className="companion-choice__title">{choice.title}</Text>
            <Text className="companion-choice__detail">{choice.detail}</Text>
          </Button>
        ))}
      </View>

      <View className="companion-setup__name-card">
        <Companion kind={kind} />
        <View className="companion-setup__name-copy">
          <Text>给它取个你喜欢的名字</Text>
          <Text className="companion-setup__label">旅伴名字</Text>
          <Input
            className="companion-setup__input"
            maxlength={12}
            value={name}
            onInput={(event) => setName(event.detail.value)}
          />
        </View>
      </View>

      <Button
        className={`companion-setup__plain ${kind === 'plain' ? 'is-selected' : ''}`}
        onClick={() => choose('plain')}
      >
        <View>
          <Text>暂时不显示宠物</Text>
          <Text>保留账号和记忆，只使用纯净模式</Text>
        </View>
        <Text>{kind === 'plain' ? '✓' : '›'}</Text>
      </Button>

      <Button
        className="companion-setup__submit"
        disabled={saving}
        onClick={() => void save()}
      >
        {saving
          ? '正在保存…'
          : current
            ? '保存新的旅伴'
            : `和${name.trim() || '旅伴'}一起开始`}
      </Button>
    </View>
  )
}
