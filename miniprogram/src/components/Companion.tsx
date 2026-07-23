import { Image, View } from '@tarojs/components'

import catImage from '../assets/companions/cloud-cat-actions.png'
import corgiImage from '../assets/companions/boarding-corgi-actions.png'
import penguinImage from '../assets/companions/migratory-penguin-actions.png'
import type { CompanionKind } from '../types/api'
import './Companion.scss'

const COMPANION_ASSETS: Record<Exclude<CompanionKind, 'plain'>, string> = {
  cat: catImage,
  corgi: corgiImage,
  penguin: penguinImage,
}

export function Companion({
  kind = 'cat',
  pose = 'idle',
  className = '',
}: {
  kind?: CompanionKind
  pose?: 'idle' | 'journal'
  className?: string
}) {
  if (kind === 'plain') {
    return (
      <View className={`mobile-companion mobile-companion--plain ${className}`}>
        ✦
      </View>
    )
  }
  return (
    <View className={`mobile-companion ${className}`}>
      <Image
        className={`mobile-companion__sprite mobile-companion__sprite--${pose}`}
        mode="scaleToFill"
        src={COMPANION_ASSETS[kind]}
      />
    </View>
  )
}
