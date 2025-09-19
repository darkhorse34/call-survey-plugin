from .api import bp as blueprint

class Plugin:
    def load(self, app_or_deps):
        app = app_or_deps.get("app") if isinstance(app_or_deps, dict) else app_or_deps
        app.register_blueprint(blueprint, url_prefix="/api/calld/1.0")
        # expose config to dialplan via env var, picked up by survey.conf
        cfg = app.config.get("wazo_survey", {}) or {}
        webhook = cfg.get("webhook_url") or ""
        if webhook:
            app.config["CHANNEL_VARS"] = app.config.get("CHANNEL_VARS", {})
            app.config["CHANNEL_VARS"]["WAZO_SURVEY_WEBHOOK"] = webhook

    def unload(self, app_or_deps):
        pass
