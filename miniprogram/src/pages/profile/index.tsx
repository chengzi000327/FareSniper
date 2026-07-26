import { Button, Image, Input, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { Companion } from '../../components/Companion'
import {
  connectWechatSession,
  ensureWechatSession,
  miniApi,
} from '../../services/api'
import type { AlertItem, MemoryResponse } from '../../types/api'
import {
  companionFromMemory,
  preferenceCount,
} from '../../utils/companion'
import './index.scss'

const WECHAT_PROFILE_KEY = 'fs_wechat_profile'

interface WechatProfile {
  nickname: string
  avatarUrl: string
}

export default function ProfilePage() {
  const [memory, setMemory] = useState<MemoryResponse | null>(null)
  const [userId, setUserId] = useState('')
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [authMode, setAuthMode] = useState('')
  const [wechatConfigured, setWechatConfigured] = useState(false)
  const [connectingWechat, setConnectingWechat] = useState(false)
  const [wechatProfile, setWechatProfile] = useState<WechatProfile>(() => {
    return (
      Taro.getStorageSync<WechatProfile>(WECHAT_PROFILE_KEY) || {
        nickname: '',
        avatarUrl: '',
      }
    )
  })

  useDidShow(() => {
    void (async () => {
      try {
        await ensureWechatSession()
        setUserId(miniApi.userId())
        setAuthMode(miniApi.authMode())
        const [nextMemory, nextAlerts, authStatus] = await Promise.all([
          miniApi.memory(),
          miniApi.alerts(),
          miniApi.wechatAuthStatus(),
        ])
        setMemory(nextMemory)
        setAlerts(nextAlerts)
        setWechatConfigured(authStatus.configured)
      } catch {
        await Taro.showToast({
          title: '用户信息暂时没有加载出来',
          icon: 'none',
        })
      }
    })()
  })

  const companion = companionFromMemory(memory?.memories || [])
  const activeAlerts = alerts.filter((item) => item.status === 'active').length
  const connected = authMode === 'wechat' || authMode === 'mock'

  const saveWechatProfile = (profile: WechatProfile) => {
    setWechatProfile(profile)
    Taro.setStorageSync(WECHAT_PROFILE_KEY, profile)
  }

  const connectWechat = async () => {
    if (connectingWechat || connected) return
    if (!wechatConfigured) {
      await Taro.showToast({
        title: '服务端尚未配置微信登录密钥',
        icon: 'none',
      })
      return
    }
    setConnectingWechat(true)
    try {
      await connectWechatSession()
      setUserId(miniApi.userId())
      setAuthMode(miniApi.authMode())
      const [nextMemory, nextAlerts] = await Promise.all([
        miniApi.memory(),
        miniApi.alerts(),
      ])
      setMemory(nextMemory)
      setAlerts(nextAlerts)
      await Taro.showToast({ title: '微信账号已连接', icon: 'success' })
    } catch (error) {
      await Taro.showToast({
        title:
          error instanceof Error ? error.message : '微信登录没有成功',
        icon: 'none',
      })
    } finally {
      setConnectingWechat(false)
    }
  }

  const chooseAvatar = async (avatarUrl: string) => {
    if (!avatarUrl) return
    try {
      const saved = await Taro.saveFile({ tempFilePath: avatarUrl })
      if (!('savedFilePath' in saved)) throw new Error('头像保存失败')
      saveWechatProfile({
        ...wechatProfile,
        avatarUrl: saved.savedFilePath,
      })
    } catch {
      saveWechatProfile({ ...wechatProfile, avatarUrl })
    }
  }

  return (
    <View className="page-shell profile-page">
      <Text className="eyebrow">我的空间</Text>
      <Text className="page-title">我的</Text>

      <View className="profile-page__identity card">
        <Button
          className="profile-page__avatar-button"
          openType={connected ? 'chooseAvatar' : undefined}
          onChooseAvatar={(event) =>
            void chooseAvatar(String(event.detail.avatarUrl || ''))
          }
          onClick={() => !connected && void connectWechat()}
        >
          {wechatProfile.avatarUrl ? (
            <Image
              className="profile-page__avatar-image"
              mode="aspectFill"
              src={wechatProfile.avatarUrl}
            />
          ) : (
            <Text className="profile-page__avatar">
              {connected ? '微' : '旅'}
            </Text>
          )}
        </Button>
        <View className="profile-page__identity-copy">
          <View className="profile-page__identity-status">
            <View className={connected ? 'is-connected' : ''} />
            <Text className="profile-page__label">
              {authMode === 'wechat'
                ? '微信账号'
                : authMode === 'mock'
                  ? '界面验收'
                  : '游客模式'}
            </Text>
          </View>
          {connected ? (
            <Input
              className="profile-page__name-input"
              type="nickname"
              value={wechatProfile.nickname}
              placeholder="微信旅行者"
              onInput={(event) =>
                setWechatProfile((current) => ({
                  ...current,
                  nickname: event.detail.value,
                }))
              }
              onBlur={() => saveWechatProfile(wechatProfile)}
            />
          ) : (
            <Text className="profile-page__name">FareSniper 旅行者</Text>
          )}
          <Text className="profile-page__connection">
            {authMode === 'wechat'
              ? '已连接微信，偏好、记忆和提醒可跨会话保留'
              : authMode === 'mock'
                ? '当前使用显式演示数据'
                : wechatConfigured
                  ? '连接微信后保留偏好、记忆与价格提醒'
                  : '微信登录待服务端密钥配置'}
          </Text>
        </View>
        <Button
          className={`profile-page__login ${
            connected ? 'is-connected' : ''
          }`}
          disabled={connectingWechat || connected || !wechatConfigured}
          onClick={() => void connectWechat()}
        >
          {connected
            ? '已连接'
            : connectingWechat
              ? '连接中'
              : wechatConfigured
                ? '微信登录'
                : '待配置'}
        </Button>
      </View>

      <View className="profile-page__companion companion-card">
        <Companion kind={companion.kind} className="profile-page__companion-avatar" />
        <View className="profile-page__companion-copy"><Text>当前旅伴</Text><Text className="profile-page__companion-name">{companion.name}</Text><Text>陪你记忆和提醒，不替你做购买决定。</Text></View>
        <Button
          className="profile-page__change-companion"
          onClick={() => {
            Taro.setStorageSync('fs_choose_companion', true)
            Taro.switchTab({ url: '/pages/chat/index' })
          }}
        >
          <Text>更换旅伴</Text>
          <Text className="profile-page__change-arrow">›</Text>
        </Button>
      </View>

      <View className="profile-page__menu">
        <MenuRow icon="preferences" title="管理机票偏好" detail={`${preferenceCount(memory?.memories || [])} 项会参与下次查价和排序`} onClick={() => Taro.switchTab({ url: '/pages/memory/index' })} />
        <MenuRow icon="journal" title="查看旅行手帐" detail="确认成行后才会写入真实旅行" onClick={() => { Taro.setStorageSync('fs_memory_section', 'journal'); Taro.switchTab({ url: '/pages/memory/index' }) }} />
        <MenuRow icon="chat" title="继续查票对话" detail="接着当前上下文补充时间和条件" onClick={() => Taro.switchTab({ url: '/pages/chat/index' })} />
        <MenuRow icon="alert" title="价格提醒" detail={`${activeAlerts} 条监控中 · 查看微信订阅状态`} onClick={() => Taro.navigateTo({ url: '/pages/alerts/index' })} />
      </View>

      <View className="profile-page__notice">
        <Text className="profile-page__notice-title">隐私与记忆</Text>
        <Text className="profile-page__notice-detail">查询只是查询，只有明确关注或真实成行才会进入对应记录。你可以随时查看和管理。</Text>
      </View>
    </View>
  )
}

type ProfileIcon = 'preferences' | 'journal' | 'chat' | 'alert'

function ProfileGlyph({ icon }: { icon: ProfileIcon }) {
  if (icon === 'preferences') {
    return (
      <View className="profile-glyph profile-glyph--preferences">
        <View><Text /></View>
        <View><Text /></View>
        <View><Text /></View>
      </View>
    )
  }

  if (icon === 'journal') {
    return (
      <View className="profile-glyph profile-glyph--journal">
        <View />
        <View />
      </View>
    )
  }

  if (icon === 'chat') {
    return <View className="profile-glyph profile-glyph--chat" />
  }

  return (
    <View className="profile-glyph profile-glyph--alert">
      <View />
      <Text />
    </View>
  )
}

function MenuRow({ icon, title, detail, onClick }: { icon: ProfileIcon; title: string; detail: string; onClick: () => void }) {
  return (
    <View className="profile-row" onClick={onClick}>
      <View className="profile-row__icon">
        <ProfileGlyph icon={icon} />
      </View>
      <View className="profile-row__copy">
        <Text>{title}</Text>
        <Text>{detail}</Text>
      </View>
      <Text className="profile-row__arrow">›</Text>
    </View>
  )
}
