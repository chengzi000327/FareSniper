export default defineAppConfig({
  pages: [
    'pages/chat/index',
    'pages/explore/index',
    'pages/memory/index',
    'pages/profile/index',
    'pages/alerts/index',
    'pages/alert-detail/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#FFFBF7',
    navigationBarTitleText: '',
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
        pagePath: 'pages/chat/index',
        text: '对话',
        iconPath: 'assets/tabbar/chat.png',
        selectedIconPath: 'assets/tabbar/chat-active.png',
      },
      {
        pagePath: 'pages/explore/index',
        text: '探索',
        iconPath: 'assets/tabbar/explore.png',
        selectedIconPath: 'assets/tabbar/explore-active.png',
      },
      {
        pagePath: 'pages/memory/index',
        text: '记忆',
        iconPath: 'assets/tabbar/memory.png',
        selectedIconPath: 'assets/tabbar/memory-active.png',
      },
      {
        pagePath: 'pages/profile/index',
        text: '我的',
        iconPath: 'assets/tabbar/profile.png',
        selectedIconPath: 'assets/tabbar/profile-active.png',
      },
    ],
  },
})
