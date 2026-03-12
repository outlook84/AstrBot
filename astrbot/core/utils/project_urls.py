PROJECT_SITE_HOME = "https://astrbot.app"
PROJECT_DOCS_HOME = "https://docs.astrbot.app"
PROJECT_GITHUB_REPO = "https://github.com/outlook84/AstrBot"
PROJECT_GITHUB_ISSUES = "https://github.com/outlook84/AstrBot/issues"
PROJECT_NOTICE_JSON = f"{PROJECT_SITE_HOME}/notice.json"
PROJECT_RELEASES_LATEST = f"{PROJECT_GITHUB_REPO}/releases/latest"
PROJECT_RELEASE_API = "https://api.soulter.top/releases"
PROJECT_GITHUB_RAW_MAIN = f"{PROJECT_GITHUB_REPO}/raw/refs/heads/master"
PLUGIN_COLLECTION_CACHE_URL = (
    "https://github.com/AstrBotDevs/AstrBot_Plugins_Collection/raw/refs/heads/main/"
    "plugin_cache_original.json"
)


def get_faq_url(locale: str | None = None) -> str:
    if locale == "en-US":
        return f"{PROJECT_DOCS_HOME}/en/faq.html"
    return f"{PROJECT_DOCS_HOME}/faq.html"
