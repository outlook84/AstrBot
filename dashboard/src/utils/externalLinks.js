export const EXTERNAL_LINKS = {
  siteHome: 'https://astrbot.app',
  docsHome: 'https://docs.astrbot.app',
  cloudApiBase: 'https://cloud.astrbot.app/api/v1',
  githubRepo: 'https://github.com/outlook84/AstrBot',
  githubIssues: 'https://github.com/outlook84/AstrBot/issues',
  pluginCollectionRepo: 'https://github.com/AstrBotDevs/AstrBot_Plugins_Collection',
  pluginDevDocs: 'https://astrbot.app/dev/plugin.html',
  apiDocs: 'https://docs.astrbot.app/dev/openapi.html',
  customRulesDocs: 'https://astrbot.app/use/custom-rules.html',
  knowledgeBaseDocs: 'https://astrbot.app/use/knowledge-base.html',
  watchtowerDocs: 'https://containrrr.dev/watchtower/usage-overview/',
  afdian: 'https://afdian.com/a/astrbot_team',
  supportGroup:
    'https://qm.qq.com/cgi-bin/qm/qr?k=EYGsuUTfe00_iOu9JTXS7_TEpMkXOvwv&jump_from=webapi&authKey=uUEMKCROfsseS+8IzqPjzV3y1tzy4AkykwTib2jNkOFdzezF9s9XknqnIaf3CDft',
  napcatSecurityDocs:
    'https://docs.astrbot.app/deploy/platform/aiocqhttp/napcat.html#%E9%99%84%E5%BD%95-%E5%A2%9E%E5%BC%BA%E8%BF%9E%E6%8E%A5%E5%AE%89%E5%85%A8%E6%80%A7',
};

const PLATFORM_DOC_PATHS = {
  qq_official_webhook: '/platform/qqofficial/webhook.html',
  qq_official: '/platform/qqofficial/websockets.html',
  aiocqhttp: '/platform/aiocqhttp/napcat.html',
  wecom: '/platform/wecom.html',
  wecom_ai_bot: '/platform/wecom_ai_bot.html',
  lark: '/platform/lark.html',
  telegram: '/platform/telegram.html',
  dingtalk: '/platform/dingtalk.html',
  weixin_official_account: '/platform/weixin-official-account.html',
  discord: '/platform/discord.html',
  slack: '/platform/slack.html',
  kook: '/platform/kook.html',
  vocechat: '/platform/vocechat.html',
  satori: '/platform/satori/llonebot.html',
  misskey: '/platform/misskey.html',
  line: '/platform/line.html',
};

export function getFaqUrl(locale) {
  return locale === 'en-US'
    ? `${EXTERNAL_LINKS.docsHome}/en/faq.html`
    : `${EXTERNAL_LINKS.docsHome}/faq.html`;
}

export function getCloudRepoInfoUrl() {
  return `${EXTERNAL_LINKS.cloudApiBase}/github/repo-info`;
}

export function getCloudAnnouncementUrl() {
  return `${EXTERNAL_LINKS.cloudApiBase}/announcement`;
}

export function getPlatformTutorialLink(platformType) {
  const path = PLATFORM_DOC_PATHS[platformType];
  return path ? `${EXTERNAL_LINKS.docsHome}${path}` : EXTERNAL_LINKS.docsHome;
}
