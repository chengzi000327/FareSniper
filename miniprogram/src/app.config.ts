export default defineAppConfig({
  pages: [
    'pages/explore/index',
    'pages/chat/index',
    'pages/alerts/index',
    'pages/profile/index',
    'pages/alert-detail/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#FFFBF7',
    navigationBarTitleText: 'FareSniper',
    navigationBarTextStyle: 'black',
    backgroundColor: '#FFFBF7',
  },
  tabBar: {
    color: '#8C7B6E',
    selectedColor: '#FF7A2F',
    backgroundColor: '#FFFFFF',
    borderStyle: 'white',
    list: [
      {
        pagePath: 'pages/explore/index',
        text: '探索',
      },
      {
        pagePath: 'pages/chat/index',
        text: '对话',
      },
      {
        pagePath: 'pages/alerts/index',
        text: '监控',
      },
      {
        pagePath: 'pages/profile/index',
        text: '我的',
      },
    ],
  },
})
