import { defineConfig, type UserConfigExport } from '@tarojs/cli'

const publicEnv = {
  apiBaseUrl: process.env.TARO_APP_API_BASE_URL || '',
  assetBaseUrl:
    process.env.TARO_APP_ASSET_BASE_URL ||
    'https://frontend-production-9c2c.up.railway.app',
  priceAlertTemplateId:
    process.env.TARO_APP_WECHAT_PRICE_ALERT_TEMPLATE_ID || '',
  useMock: process.env.TARO_APP_USE_MOCK || 'false',
}

const config: UserConfigExport<'webpack5'> = {
  projectName: 'FareSniper',
  date: '2026-07-23',
  designWidth: 375,
  deviceRatio: {
    375: 2,
    640: 1.17,
    750: 1,
    828: 0.905,
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  plugins: ['@tarojs/plugin-framework-react'],
  framework: 'react',
  defineConstants: {
    'process.env.TARO_APP_API_BASE_URL': JSON.stringify(publicEnv.apiBaseUrl),
    'process.env.TARO_APP_ASSET_BASE_URL': JSON.stringify(
      publicEnv.assetBaseUrl,
    ),
    'process.env.TARO_APP_WECHAT_PRICE_ALERT_TEMPLATE_ID': JSON.stringify(
      publicEnv.priceAlertTemplateId,
    ),
    'process.env.TARO_APP_USE_MOCK': JSON.stringify(publicEnv.useMock),
  },
  compiler: {
    type: 'webpack5',
    prebundle: {
      enable: false,
    },
  },
  cache: {
    enable: true,
  },
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {},
      },
      url: {
        enable: true,
        config: {
          limit: 1024,
        },
      },
      cssModules: {
        enable: false,
      },
    },
  },
}

export default defineConfig(config)
